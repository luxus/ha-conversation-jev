"""Jev Assist: Jev fast-path conversation agent with Grok fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .const import (
    AUTH_OAUTH,
    CONF_ACCESS_TOKEN,
    CONF_GROK_AUTH_METHOD,
    CONF_REFRESH_TOKEN,
    CONF_TYPESAFE_API_KEY,
    DOMAIN,
)
from .grok_oauth import (
    GrokOAuthError,
    OAUTH_TRANSPORT_ERRORS,
    access_token_needs_refresh,
    refresh_access_token,
    token_data_updates,
)
from .jev_client import TypeSafeJevClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ("conversation",)


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


async def _async_refresh_grok_tokens(hass: Any, entry: Any) -> None:
    """Refresh Grok OAuth tokens only when missing or near expiry."""
    from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    refresh_token = entry.data.get(CONF_REFRESH_TOKEN)
    if not refresh_token:
        if not entry.data.get(CONF_ACCESS_TOKEN):
            raise ConfigEntryAuthFailed("Grok OAuth tokens missing")
        return
    if not access_token_needs_refresh(entry.data):
        return
    session = async_get_clientsession(hass)
    try:
        tokens = await refresh_access_token(session, refresh_token)
    except GrokOAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except OAUTH_TRANSPORT_ERRORS as err:
        raise ConfigEntryNotReady("Could not refresh Grok OAuth tokens") from err
    updates = token_data_updates(tokens)
    if any(entry.data.get(key) != value for key, value in updates.items()):
        hass.config_entries.async_update_entry(entry, data={**entry.data, **updates})
        _LOGGER.debug("Persisted Grok token refresh")
