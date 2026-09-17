"""Grok CLI OAuth: device-code + PKCE against auth.x.ai."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping

from .const import (
    GROK_DEVICE_GRANT,
    GROK_OAUTH_CLIENT_ID,
    GROK_OAUTH_DEVICE_URL,
    GROK_OAUTH_REFERRER,
    GROK_OAUTH_SCOPES,
    GROK_OAUTH_TOKEN_URL,
)

Sleep = Callable[[float], Awaitable[None]]


class GrokOAuthError(Exception):
    """Device-code or token request failed."""

    def __init__(self, message: str, *, error: str | None = None) -> None:
        super().__init__(message)
        self.error = error


@dataclass(frozen=True)
class PkcePair:
    verifier: str
    challenge: str
    method: str = "S256"


@dataclass(frozen=True)
class DeviceAuthorization:
    device_code: str
    user_code: str
    verification_uri: str
    interval: int
    expires_in: int
    verification_uri_complete: str | None = None
    pkce: PkcePair | None = None


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_in: int | None
    token_type: str = "Bearer"
    scope: str | None = None

    def expires_at(self, *, now: float | None = None) -> float | None:
        if self.expires_in is None:
            return None
        return (now if now is not None else time.time()) + int(self.expires_in)


def generate_pkce() -> PkcePair:
    """RFC 7636 S256 PKCE for the public Grok CLI client."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return PkcePair(verifier=verifier, challenge=challenge)


async def _post_form(session: Any, url: str, data: Mapping[str, str]) -> tuple[int, Any]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    request = session.post(url, data=dict(data), headers=headers)
    if hasattr(request, "__aenter__"):
        async with request as response:
            status = int(response.status)
            try:
                body: Any = await response.json(content_type=None)
            except Exception:
                body = await response.text()
            return status, body
    return await request


def _error_code(body: Any) -> str | None:
    if isinstance(body, dict):
        error = body.get("error")
        return str(error) if error is not None else None
    return None


def _parse_tokens(body: Any) -> TokenSet:
    if not isinstance(body, dict) or not body.get("access_token"):
        raise GrokOAuthError("token response missing access_token")
    expires_in = body.get("expires_in")
    return TokenSet(
        access_token=str(body["access_token"]),
        refresh_token=str(body["refresh_token"]) if body.get("refresh_token") else None,
        expires_in=int(expires_in) if expires_in is not None else None,
        token_type=str(body.get("token_type") or "Bearer"),
        scope=str(body["scope"]) if body.get("scope") else None,
    )


async def request_device_code(
    session: Any,
    *,
    client_id: str = GROK_OAUTH_CLIENT_ID,
    scopes: str = GROK_OAUTH_SCOPES,
    pkce: PkcePair | None = None,
) -> DeviceAuthorization:
    """Start RFC 8628 device authorization (PKCE S256)."""
    pair = pkce or generate_pkce()
    data = {
        "client_id": client_id,
        "scope": scopes,
        "referrer": GROK_OAUTH_REFERRER,
        "code_challenge": pair.challenge,
        "code_challenge_method": pair.method,
    }
    status, body = await _post_form(session, GROK_OAUTH_DEVICE_URL, data)
    if status >= 400 or not isinstance(body, dict) or not body.get("device_code"):
        raise GrokOAuthError(
            f"device code request failed ({status}): {body}",
            error=_error_code(body),
        )
    uri = (
        body.get("verification_uri")
        or body.get("verification_url")
        or body.get("verification_uri_complete")
    )
    if not uri or not body.get("user_code"):
        raise GrokOAuthError("device code response missing user_code/verification_uri")
    return DeviceAuthorization(
        device_code=str(body["device_code"]),
        user_code=str(body["user_code"]),
        verification_uri=str(uri),
        interval=max(1, int(body.get("interval") or 5)),
        expires_in=max(1, int(body.get("expires_in") or 600)),
        verification_uri_complete=(
            str(body["verification_uri_complete"])
            if body.get("verification_uri_complete")
            else None
        ),
        pkce=pair,
    )


async def poll_device_token(
    session: Any,
    authorization: DeviceAuthorization,
    *,
    client_id: str = GROK_OAUTH_CLIENT_ID,
    sleep: Sleep = asyncio.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> TokenSet:
    """Poll the token endpoint until authorized, expired, or denied."""
    interval = float(authorization.interval)
    deadline = monotonic() + float(authorization.expires_in)
    while True:
        await sleep(interval)
        if monotonic() >= deadline:
            raise GrokOAuthError("device authorization expired", error="expired_token")
        data = {
            "grant_type": GROK_DEVICE_GRANT,
            "device_code": authorization.device_code,
            "client_id": client_id,
        }
        if authorization.pkce is not None:
            data["code_verifier"] = authorization.pkce.verifier
        status, body = await _post_form(session, GROK_OAUTH_TOKEN_URL, data)
        if status < 400 and isinstance(body, dict) and body.get("access_token"):
            return _parse_tokens(body)
        error = _error_code(body) or ""
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        raise GrokOAuthError(
            f"device token poll failed ({status}): {body}",
            error=error or None,
        )


async def refresh_access_token(
    session: Any,
    refresh_token: str,
    *,
    client_id: str = GROK_OAUTH_CLIENT_ID,
) -> TokenSet:
    """Refresh tokens; persist a rotated refresh_token when present."""
    status, body = await _post_form(
        session,
        GROK_OAUTH_TOKEN_URL,
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        },
    )
    if status >= 400:
        raise GrokOAuthError(
            f"refresh failed ({status}): {body}",
            error=_error_code(body),
        )
    tokens = _parse_tokens(body)
    if tokens.refresh_token is None:
        tokens = TokenSet(
            access_token=tokens.access_token,
            refresh_token=refresh_token,
            expires_in=tokens.expires_in,
            token_type=tokens.token_type,
            scope=tokens.scope,
        )
    return tokens


def token_data_updates(
    tokens: TokenSet,
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Config-entry fields to persist (including rotated refresh tokens)."""
    data: dict[str, Any] = {
        "access_token": tokens.access_token,
        "token_type": tokens.token_type,
    }
    if tokens.refresh_token:
        data["refresh_token"] = tokens.refresh_token
    expires_at = tokens.expires_at(now=now)
    if expires_at is not None:
        data["expires_at"] = expires_at
    if tokens.scope:
        data["scope"] = tokens.scope
    return data
