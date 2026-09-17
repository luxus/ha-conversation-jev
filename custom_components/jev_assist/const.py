"""Constants for the Jev Assist integration."""

from typing import Final, Literal

from ha_spacexai_auth import (
    CLIENT_ID,
    DEVICE_AUTHORIZATION_URL,
    DEVICE_GRANT_TYPE,
    ISSUER,
    REFERRER,
    SCOPES,
    TOKEN_URL,
)

DOMAIN: Final = "jev_assist"
DEFAULT_NAME: Final = "Jev Assist"

# TypeSafe / Jev
TYPESAFE_MODEL: Final = "jev-latest"
TYPESAFE_BASE_URL: Final = "https://api.typesafe.ai"
EXPOSED_ENTITY_CAP: Final = 80

CONF_TYPESAFE_API_KEY: Final = "typesafe_api_key"
CONF_GROK_API_KEY: Final = "grok_api_key"
CONF_GROK_AUTH_METHOD: Final = "grok_auth_method"
CONF_ACCESS_TOKEN: Final = "access_token"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_EXPIRES_AT: Final = "expires_at"
CONF_TOKEN_TYPE: Final = "token_type"
CONF_SCOPE: Final = "scope"
CONF_OAUTH_RECOVERY: Final = "oauth_recovery"

AUTH_OAUTH: Final = "oauth"
AUTH_API_KEY: Final = "api_key"
AuthMethod = Literal["oauth", "api_key"]

OAUTH_RECOVERY_RETRY: Final = "retry_oauth"
OAUTH_RECOVERY_API_KEY: Final = "api_key"
OAUTH_RECOVERY_ABORT: Final = "abort"

# Refresh access tokens this many seconds before expires_at.
TOKEN_EXPIRY_SKEW_SECONDS: Final = 60

# Grok CLI public client — sourced from ha_spacexai_auth (grok-build config.rs).
GROK_OAUTH_ISSUER: Final = ISSUER
GROK_OAUTH_CLIENT_ID: Final = CLIENT_ID
GROK_OAUTH_DEVICE_URL: Final = DEVICE_AUTHORIZATION_URL
GROK_OAUTH_TOKEN_URL: Final = TOKEN_URL
GROK_OAUTH_SCOPES: Final = SCOPES
GROK_DEVICE_GRANT: Final = DEVICE_GRANT_TYPE
GROK_OAUTH_REFERRER: Final = REFERRER
GROK_API_BASE: Final = "https://api.x.ai"
GROK_CLI_PROXY_BASE: Final = "https://cli-chat-proxy.grok.com"

# Router gates (CONTRACT.md v0, blessed)
FAST_MIN_CONFIDENCE: Final = 0.80
NOUL_YES_THRESHOLD: Final = 0.55
REJECT_MIN_CONFIDENCE: Final = 0.80

CATEGORY_COMMAND: Final = "command"
CATEGORY_CONVERSATION: Final = "conversation"
CATEGORY_REJECT: Final = "reject"
DOMAIN_LIGHT: Final = "light"
TARGET_NONE: Final = "none"
TARGET_UNKNOWN: Final = "unknown"

SUPPORTED_LANGUAGES: Final = ("en", "de")
DEFAULT_LANGUAGE: Final = "en"
