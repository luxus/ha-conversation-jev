"""Jev Assist: Jev fast-path conversation agent with Grok fallback."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from ha_spacexai_auth import (
    SpaceXaiAuthError,
    SpaceXaiAuthExpired,
    SpaceXaiEntitlementError,
    TokenSet,
    authorization_headers,
    ensure_fresh,
    token_data_updates,
)

from .const import (
    AUTH_OAUTH,
    CONF_ACCESS_TOKEN,
    CONF_GROK_AUTH_METHOD,
    CONF_TYPESAFE_API_KEY,
    DOMAIN,
    TOKEN_EXPIRY_SKEW_SECONDS,
)
from .jev_client import TypeSafeJevClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ("conversation",)

TimeFn = Callable[[], float]

try:
    from aiohttp import ClientError as _AiohttpClientError
except ImportError:  # pragma: no cover - aiohttp is provided by Home Assistant
    _AiohttpClientError = None

OAUTH_TRANSPORT_ERRORS: tuple[type[BaseException], ...]
if _AiohttpClientError is not None:
    OAUTH_TRANSPORT_ERRORS = (_AiohttpClientError, TimeoutError)
else:
    OAUTH_TRANSPORT_ERRORS = (TimeoutError, ConnectionError, OSError)


@dataclass
class JevAssistRuntime:
    """Per-entry runtime: TypeSafe client + config entry."""

    jev: TypeSafeJevClient
    entry: Any


async def async_setup_entry(hass: Any, entry: Any) -> bool:
    """Set up Jev Assist from a config entry."""
    from homeassistant.exceptions import ConfigEntryAuthFailed

    typesafe_key = entry.data.get(CONF_TYPESAFE_API_KEY)
    if not typesafe_key:
        raise ConfigEntryAuthFailed("TypeSafe API key missing")

    if entry.data.get(CONF_GROK_AUTH_METHOD, AUTH_OAUTH) == AUTH_OAUTH:
        await _async_refresh_grok_tokens(hass, entry)

    runtime = JevAssistRuntime(
        jev=TypeSafeJevClient(typesafe_key),
        entry=entry,
    )
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: Any, entry: Any) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded


async def _async_reload(hass: Any, entry: Any) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def ensure_entry_tokens(
    session: Any,
    entry_data: Mapping[str, Any],
    *,
    time_fn: TimeFn | None = None,
) -> dict[str, Any] | None:
    """Run ``ensure_fresh``; return token-field updates or ``None``.

    Missing ``access_token`` is an auth failure. Missing/invalid
    ``expires_at`` skips refresh (package ``ensure_fresh`` contract).
    """
    if not entry_data.get(CONF_ACCESS_TOKEN):
        raise SpaceXaiAuthError("Grok OAuth tokens missing")
    try:
        tokens = TokenSet.from_entry_data(entry_data)
    except SpaceXaiAuthError:
        return None
    fresh = await ensure_fresh(
        session,
        tokens,
        skew_seconds=TOKEN_EXPIRY_SKEW_SECONDS,
        time_fn=time_fn,
    )
    updates = token_data_updates(fresh)
    if all(entry_data.get(key) == value for key, value in updates.items()):
        return None
    return updates


async def _async_refresh_grok_tokens(hass: Any, entry: Any) -> None:
    """ensure_fresh on setup/reload; persist rotated refresh tokens."""
    from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    session = async_get_clientsession(hass)
    try:
        updates = await ensure_entry_tokens(session, entry.data)
    except SpaceXaiAuthExpired as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SpaceXaiEntitlementError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SpaceXaiAuthError as err:
        if not entry.data.get(CONF_ACCESS_TOKEN):
            raise ConfigEntryAuthFailed(str(err)) from err
        raise ConfigEntryNotReady(str(err)) from err
    except OAUTH_TRANSPORT_ERRORS as err:
        raise ConfigEntryNotReady("Could not refresh Grok OAuth tokens") from err
    if updates:
        hass.config_entries.async_update_entry(entry, data={**entry.data, **updates})
        _LOGGER.debug("Persisted Grok token refresh")


def grok_authorization_headers(entry_data: Mapping[str, Any]) -> dict[str, str]:
    """Bearer headers for Grok API calls from stored entry tokens."""
    token = entry_data.get(CONF_ACCESS_TOKEN)
    if not token:
        raise SpaceXaiAuthError("Grok OAuth tokens missing")
    return authorization_headers(str(token))
