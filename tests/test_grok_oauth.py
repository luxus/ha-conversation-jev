"""Jev consumes ha_spacexai_auth (mocked HTTP, no live auth)."""

from __future__ import annotations

import ast
import hashlib
import base64
from pathlib import Path

import pytest
from ha_spacexai_auth import (
    CLIENT_ID,
    DEVICE_AUTHORIZATION_URL,
    DEVICE_GRANT_TYPE,
    PkcePair,
    SCOPES,
    SpaceXaiAuthError,
    TOKEN_URL,
    TokenSet,
    authorization_headers,
    generate_pkce,
    poll_token,
    refresh_access_token,
    start_device_auth,
    token_data_updates,
)

from jev_assist import (
    OAUTH_TRANSPORT_ERRORS,
    ensure_entry_tokens,
    grok_authorization_headers,
)
from jev_assist.const import GROK_OAUTH_CLIENT_ID, GROK_OAUTH_SCOPES

_JEV_ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "jev_assist"


class FakeResponse:
    def __init__(self, status: int, body: object) -> None:
        self.status = status
        self._body = body

    async def json(self) -> object:
        if isinstance(self._body, (dict, list)):
            return self._body
        raise ValueError("not json")

    async def text(self) -> str:
        return str(self._body)

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class FakeSession:
    def __init__(self, script: list[tuple[str, int, object]]) -> None:
        self.script = list(script)
        self.calls: list[tuple[str, dict[str, str]]] = []

    def post(
        self,
        url: str,
        *,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> FakeResponse:
        payload = dict(data or {})
        self.calls.append((url, payload))
        expected_url, status, body = self.script.pop(0)
        assert url == expected_url
        return FakeResponse(status, body)


def _imports_from(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


def test_jev_imports_ha_spacexai_auth_not_inline_oauth() -> None:
    assert not (_JEV_ROOT / "grok_oauth.py").exists()
    init_mods = _imports_from(_JEV_ROOT / "__init__.py")
    flow_mods = _imports_from(_JEV_ROOT / "config_flow.py")
    const_mods = _imports_from(_JEV_ROOT / "const.py")
    assert "ha_spacexai_auth" in init_mods
    assert "ha_spacexai_auth" in flow_mods
    assert "ha_spacexai_auth" in const_mods
    init_src = (_JEV_ROOT / "__init__.py").read_text()
    assert "ensure_fresh" in init_src
    assert "from_entry_data" in init_src
    assert "authorization_headers" in init_src
    flow_src = (_JEV_ROOT / "config_flow.py").read_text()
    assert "request_device_code" in flow_src or "start_device_auth" in flow_src
    assert "poll_device_token" in flow_src or "poll_token" in flow_src
    assert "token_data_updates" in flow_src


def test_public_surface_and_const_reexports() -> None:
    assert GROK_OAUTH_CLIENT_ID == CLIENT_ID
    assert GROK_OAUTH_SCOPES == SCOPES
    assert "offline_access" in SCOPES
    assert "grok-cli:access" in SCOPES
    headers = grok_authorization_headers({"access_token": "tok"})
    assert headers == authorization_headers("tok") == {"Authorization": "Bearer tok"}
    tokens = TokenSet(
        access_token="at",
        refresh_token="rt",
        expires_at=99.0,
        scope="openid",
    )
    roundtrip = TokenSet.from_entry_data(tokens.to_entry_data())
    assert roundtrip.access_token == "at"
    assert roundtrip.refresh_token == "rt"
    assert roundtrip.expires_at == 99.0
    assert isinstance(TimeoutError("auth.x.ai unreachable"), OAUTH_TRANSPORT_ERRORS)
    assert not isinstance(
        SpaceXaiAuthError("invalid_grant", error="invalid_grant"),
        OAUTH_TRANSPORT_ERRORS,
    )


def test_pkce_s256_shape() -> None:
    pair = generate_pkce()
    digest = hashlib.sha256(pair.verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    assert pair.method == "S256"
    assert pair.challenge == expected
    assert len(pair.verifier) >= 43


@pytest.mark.asyncio
async def test_device_code_sends_pkce_and_cli_client() -> None:
    pkce = PkcePair(verifier="abc", challenge="challenge", method="S256")
    session = FakeSession(
        [
            (
                DEVICE_AUTHORIZATION_URL,
                200,
                {
                    "device_code": "dev",
                    "user_code": "WDJB-MJHT",
                    "verification_uri": "https://auth.x.ai/device",
                    "interval": 1,
                    "expires_in": 60,
                },
            )
        ]
    )
    auth = await start_device_auth(session, pkce=pkce)
    assert auth.user_code == "WDJB-MJHT"
    assert session.calls[0][1]["client_id"] == CLIENT_ID
    assert session.calls[0][1]["code_challenge"] == "challenge"
    assert session.calls[0][1]["code_challenge_method"] == "S256"
    assert "offline_access" in session.calls[0][1]["scope"]
    assert "grok-cli:access" in session.calls[0][1]["scope"]
    assert "api:access" in session.calls[0][1]["scope"]


@pytest.mark.asyncio
async def test_poll_pending_then_tokens() -> None:
    pkce = PkcePair(verifier="ver", challenge="ch")
    session = FakeSession(
        [
            (
                DEVICE_AUTHORIZATION_URL,
                200,
                {
                    "device_code": "dev",
                    "user_code": "CODE",
                    "verification_uri": "https://auth.x.ai/device",
                    "interval": 1,
                    "expires_in": 30,
                },
            ),
            (
                TOKEN_URL,
                400,
                {"error": "authorization_pending"},
            ),
            (
                TOKEN_URL,
                200,
                {
                    "access_token": "at-1",
                    "refresh_token": "rt-1",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            ),
        ]
    )
    auth = await start_device_auth(session, pkce=pkce, time_fn=lambda: 0.0)

    async def no_sleep(_: float) -> None:
        return None

    clock = {"t": 0.0}

    def now() -> float:
        clock["t"] += 0.01
        return clock["t"]

    tokens = await poll_token(session, auth, sleep=no_sleep, time_fn=now)
    assert tokens.access_token == "at-1"
    assert tokens.refresh_token == "rt-1"
    grant = session.calls[2][1]
    assert grant["grant_type"] == DEVICE_GRANT_TYPE
    assert grant["code_verifier"] == "ver"


@pytest.mark.asyncio
async def test_refresh_persists_rotated_refresh_token() -> None:
    session = FakeSession(
        [
            (
                TOKEN_URL,
                200,
                {
                    "access_token": "at-2",
                    "refresh_token": "rt-rotated",
                    "expires_in": 100,
                },
            )
        ]
    )
    previous = TokenSet(
        access_token="at-old",
        refresh_token="rt-old",
        expires_at=1.0,
    )
    tokens = await refresh_access_token(session, previous, time_fn=lambda: 1_000.0)
    updates = token_data_updates(tokens)
    assert updates["access_token"] == "at-2"
    assert updates["refresh_token"] == "rt-rotated"
    assert updates["expires_at"] == 1_100.0


@pytest.mark.asyncio
async def test_refresh_keeps_old_rt_when_omitted() -> None:
    session = FakeSession(
        [
            (
                TOKEN_URL,
                200,
                {"access_token": "at-3", "expires_in": 10},
            )
        ]
    )
    previous = TokenSet(
        access_token="at-old",
        refresh_token="rt-keep",
        expires_at=1.0,
    )
    tokens = await refresh_access_token(session, previous, time_fn=lambda: 50.0)
    assert tokens.refresh_token == "rt-keep"


@pytest.mark.asyncio
async def test_poll_access_denied() -> None:
    session = FakeSession(
        [
            (
                DEVICE_AUTHORIZATION_URL,
                200,
                {
                    "device_code": "dev",
                    "user_code": "CODE",
                    "verification_uri": "https://auth.x.ai/device",
                    "interval": 1,
                    "expires_in": 30,
                },
            ),
            (TOKEN_URL, 400, {"error": "access_denied"}),
        ]
    )
    auth = await start_device_auth(session, time_fn=lambda: 0.0)

    async def no_sleep(_: float) -> None:
        return None

    with pytest.raises(SpaceXaiAuthError) as exc:
        await poll_token(session, auth, sleep=no_sleep, time_fn=lambda: 0.0)
    assert exc.value.error == "access_denied"


@pytest.mark.asyncio
async def test_ensure_entry_tokens_skips_fresh_access_token() -> None:
    session = FakeSession([])
    data = {
        "access_token": "at-live",
        "refresh_token": "rt-live",
        "expires_at": 10_000.0,
        "token_type": "Bearer",
        "scope": "openid",
    }
    assert await ensure_entry_tokens(session, data, time_fn=lambda: 1_000.0) is None
    assert session.calls == []


@pytest.mark.asyncio
async def test_ensure_entry_tokens_refreshes_near_expiry() -> None:
    session = FakeSession(
        [
            (
                TOKEN_URL,
                200,
                {
                    "access_token": "at-new",
                    "refresh_token": "rt-new",
                    "expires_in": 3600,
                },
            )
        ]
    )
    data = {
        "access_token": "at-old",
        "refresh_token": "rt-old",
        "expires_at": 1_030.0,
        "token_type": "Bearer",
    }
    updates = await ensure_entry_tokens(session, data, time_fn=lambda: 1_000.0)
    assert updates is not None
    assert updates["access_token"] == "at-new"
    assert updates["refresh_token"] == "rt-new"


@pytest.mark.asyncio
async def test_ensure_entry_tokens_skips_missing_expires_at() -> None:
    session = FakeSession([])
    data = {"access_token": "at-live", "refresh_token": "rt-live"}
    assert await ensure_entry_tokens(session, data, time_fn=lambda: 1_000.0) is None
    assert session.calls == []


@pytest.mark.asyncio
async def test_ensure_entry_tokens_requires_access_token() -> None:
    session = FakeSession([])
    with pytest.raises(SpaceXaiAuthError):
        await ensure_entry_tokens(session, {"refresh_token": "rt"}, time_fn=lambda: 0.0)
