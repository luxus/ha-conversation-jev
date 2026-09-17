"""Config flow: TypeSafe API key + Grok CLI OAuth (device code) first."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    AUTH_API_KEY,
    AUTH_OAUTH,
    CONF_GROK_API_KEY,
    CONF_GROK_AUTH_METHOD,
    CONF_OAUTH_RECOVERY,
    CONF_TYPESAFE_API_KEY,
    DEFAULT_NAME,
    DOMAIN,
    OAUTH_RECOVERY_ABORT,
    OAUTH_RECOVERY_API_KEY,
    OAUTH_RECOVERY_RETRY,
)
from .grok_oauth import (
    DeviceAuthorization,
    GrokOAuthError,
    OAUTH_TRANSPORT_ERRORS,
    TokenSet,
    poll_device_token,
    request_device_code,
    token_data_updates,
)

_LOGGER = logging.getLogger(__name__)

PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

AUTH_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[AUTH_OAUTH, AUTH_API_KEY],
        mode=SelectSelectorMode.LIST,
        translation_key="grok_auth_method",
    )
)

OAUTH_RECOVERY_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[OAUTH_RECOVERY_RETRY, OAUTH_RECOVERY_API_KEY, OAUTH_RECOVERY_ABORT],
        mode=SelectSelectorMode.LIST,
        translation_key="oauth_recovery",
    )
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TYPESAFE_API_KEY): PASSWORD,
        vol.Required(CONF_GROK_AUTH_METHOD, default=AUTH_OAUTH): AUTH_SELECTOR,
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_GROK_AUTH_METHOD, default=AUTH_OAUTH): AUTH_SELECTOR,
    }
)

API_KEY_SCHEMA = vol.Schema({vol.Required(CONF_GROK_API_KEY): PASSWORD})

OAUTH_FAILED_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OAUTH_RECOVERY, default=OAUTH_RECOVERY_RETRY): OAUTH_RECOVERY_SELECTOR,
    }
)


class JevAssistConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """OAuth-first setup. Not Application Credentials. API key is fallback only."""

    VERSION = 1

    def __init__(self) -> None:
        self._typesafe_api_key: str | None = None
        self._device: DeviceAuthorization | None = None
        self._oauth_task: asyncio.Task[TokenSet] | None = None
        self._tokens: TokenSet | None = None
        self._oauth_error: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect TypeSafe API key; Grok OAuth is the default next step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            key = str(user_input[CONF_TYPESAFE_API_KEY]).strip()
            if not key:
                errors[CONF_TYPESAFE_API_KEY] = "invalid_api_key"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                self._typesafe_api_key = key
                method = user_input.get(CONF_GROK_AUTH_METHOD, AUTH_OAUTH)
                if method == AUTH_API_KEY:
                    return await self.async_step_api_key()
                return await self.async_step_oauth()

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def async_step_oauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show Grok device-code URL + user code and poll the token endpoint."""
        session = async_get_clientsession(self.hass)

        if self._oauth_task is None:
            try:
                self._device = await request_device_code(session)
            except GrokOAuthError as err:
                _LOGGER.warning("Grok device-code start failed: %s", err)
                self._oauth_error = err.error or "oauth_failed"
                return await self.async_step_oauth_failed()
            except OAUTH_TRANSPORT_ERRORS as err:
                _LOGGER.warning("Grok device-code start cannot connect: %s", err)
                self._oauth_error = "cannot_connect"
                return await self.async_step_oauth_failed()
            self._oauth_task = self.hass.async_create_task(
                poll_device_token(session, self._device)
            )
            return self._show_oauth_progress()

        if not self._oauth_task.done():
            return self._show_oauth_progress()

        try:
            self._tokens = self._oauth_task.result()
        except GrokOAuthError as err:
            _LOGGER.warning("Grok OAuth poll failed: %s", err)
            self._oauth_error = err.error or "oauth_failed"
            return self.async_show_progress_done(next_step_id="oauth_failed")
        except OAUTH_TRANSPORT_ERRORS as err:
            _LOGGER.warning("Grok OAuth poll cannot connect: %s", err)
            self._oauth_error = "cannot_connect"
            return self.async_show_progress_done(next_step_id="oauth_failed")
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Grok OAuth poll crashed")
            self._oauth_error = "oauth_failed"
            return self.async_show_progress_done(next_step_id="oauth_failed")
        return self.async_show_progress_done(next_step_id="oauth_done")

    def _show_oauth_progress(self) -> FlowResult:
        device = self._device
        assert device is not None
        return self.async_show_progress(
            step_id="oauth",
            progress_action="oauth_wait",
            description_placeholders={
                "url": device.verification_uri,
                "user_code": device.user_code,
            },
            progress_task=self._oauth_task,
        )

    async def async_step_oauth_done(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Persist access + refresh tokens in the config entry."""
        assert self._typesafe_api_key is not None
        assert self._tokens is not None
        return self._create(
            {
                CONF_TYPESAFE_API_KEY: self._typesafe_api_key,
                CONF_GROK_AUTH_METHOD: AUTH_OAUTH,
                **token_data_updates(self._tokens),
            }
        )

    def _reset_oauth(self) -> None:
        task = self._oauth_task
        if task is not None and not task.done():
            task.cancel()
        self._oauth_task = None
        self._device = None
        self._tokens = None
        self._oauth_error = None

    async def async_step_oauth_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """OAuth failed: retry OAuth, fall back to API key, or abort."""
        if user_input is not None:
            action = user_input.get(CONF_OAUTH_RECOVERY, OAUTH_RECOVERY_RETRY)
            if action == OAUTH_RECOVERY_API_KEY:
                return await self.async_step_api_key()
            if action == OAUTH_RECOVERY_ABORT:
                return self.async_abort(reason="oauth_failed")
            self._reset_oauth()
            return await self.async_step_oauth()
        errors: dict[str, str] = {}
        if self._oauth_error == "cannot_connect":
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="oauth_failed",
            data_schema=OAUTH_FAILED_SCHEMA,
            errors=errors,
            description_placeholders={"error": self._oauth_error or "oauth_failed"},
        )

    async def async_step_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Optional Grok API key when OAuth is unavailable (console.x.ai billing)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            grok_key = str(user_input[CONF_GROK_API_KEY]).strip()
            if not grok_key:
                errors[CONF_GROK_API_KEY] = "invalid_api_key"
            elif self._typesafe_api_key:
                return self._create(
                    {
                        CONF_TYPESAFE_API_KEY: self._typesafe_api_key,
                        CONF_GROK_AUTH_METHOD: AUTH_API_KEY,
                        CONF_GROK_API_KEY: grok_key,
                    }
                )
        return self.async_show_form(
            step_id="api_key",
            data_schema=API_KEY_SCHEMA,
            errors=errors,
        )

    def _create(self, data: dict[str, Any]) -> FlowResult:
        if self.source == config_entries.SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates=data,
            )
        return self.async_create_entry(title=DEFAULT_NAME, data=data)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Re-run Grok OAuth (or API-key fallback) when tokens fail."""
        self._typesafe_api_key = entry_data.get(CONF_TYPESAFE_API_KEY)
        await self.async_set_unique_id(DOMAIN)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=REAUTH_SCHEMA,
            )
        method = user_input.get(CONF_GROK_AUTH_METHOD, AUTH_OAUTH)
        if method == AUTH_API_KEY:
            return await self.async_step_api_key()
        self._reset_oauth()
        return await self.async_step_oauth()
