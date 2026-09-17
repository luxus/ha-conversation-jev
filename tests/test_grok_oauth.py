"""Grok device-code + PKCE client (mocked HTTP, no live auth)."""

from __future__ import annotations

import hashlib
import base64

import pytest

from jev_assist.const import (
    GROK_DEVICE_GRANT,
    GROK_OAUTH_CLIENT_ID,
    GROK_OAUTH_DEVICE_URL,
    GROK_OAUTH_TOKEN_URL,
)
from jev_assist.grok_oauth import (
    GrokOAuthError,
    PkcePair,
    generate_pkce,
    poll_device_token,
    refresh_access_token,
    request_device_code,
    token_data_updates,
)


class FakeResponse:
    def __init__(self, status: int, body: object) -> None:
        self.status = status
        self._body = body

    async def json(self, content_type: str | None = None) -> object:
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

    def post(self, url: str, data: dict[str, str], headers: dict[str, str] | None = None) -> FakeResponse:
        self.calls.append((url, dict(data)))
        expected_url, status, body = self.script.pop(0)
        assert url == expected_url
        return FakeResponse(status, body)


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
                GROK_OAUTH_DEVICE_URL,
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
    auth = await request_device_code(session, pkce=pkce)
    assert auth.user_code == "WDJB-MJHT"
    assert session.calls[0][1]["client_id"] == GROK_OAUTH_CLIENT_ID
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
                GROK_OAUTH_DEVICE_URL,
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
                GROK_OAUTH_TOKEN_URL,
                400,
                {"error": "authorization_pending"},
            ),
            (
                GROK_OAUTH_TOKEN_URL,
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
    auth = await request_device_code(session, pkce=pkce)

    async def no_sleep(_: float) -> None:
        return None

    clock = {"t": 0.0}

    def mono() -> float:
        clock["t"] += 0.01
        return clock["t"]

    tokens = await poll_device_token(session, auth, sleep=no_sleep, monotonic=mono)
    assert tokens.access_token == "at-1"
    assert tokens.refresh_token == "rt-1"
    grant = session.calls[2][1]
    assert grant["grant_type"] == GROK_DEVICE_GRANT
    assert grant["code_verifier"] == "ver"


@pytest.mark.asyncio
async def test_refresh_persists_rotated_refresh_token() -> None:
    session = FakeSession(
        [
            (
                GROK_OAUTH_TOKEN_URL,
                200,
                {
                    "access_token": "at-2",
                    "refresh_token": "rt-rotated",
                    "expires_in": 100,
                },
            )
        ]
    )
    tokens = await refresh_access_token(session, "rt-old")
    updates = token_data_updates(tokens, now=1_000.0)
    assert updates["access_token"] == "at-2"
    assert updates["refresh_token"] == "rt-rotated"
    assert updates["expires_at"] == 1_100.0


@pytest.mark.asyncio
async def test_refresh_keeps_old_rt_when_omitted() -> None:
    session = FakeSession(
        [
            (
                GROK_OAUTH_TOKEN_URL,
                200,
                {"access_token": "at-3", "expires_in": 10},
            )
        ]
    )
    tokens = await refresh_access_token(session, "rt-keep")
    assert tokens.refresh_token == "rt-keep"


@pytest.mark.asyncio
async def test_poll_access_denied() -> None:
    session = FakeSession(
        [
            (
                GROK_OAUTH_DEVICE_URL,
                200,
                {
                    "device_code": "dev",
                    "user_code": "CODE",
                    "verification_uri": "https://auth.x.ai/device",
                    "interval": 1,
                    "expires_in": 30,
                },
            ),
            (GROK_OAUTH_TOKEN_URL, 400, {"error": "access_denied"}),
        ]
    )
    auth = await request_device_code(session)

    async def no_sleep(_: float) -> None:
        return None

    with pytest.raises(GrokOAuthError) as exc:
        await poll_device_token(session, auth, sleep=no_sleep, monotonic=lambda: 0.0)
    assert exc.value.error == "access_denied"
