"""Constants for the Jev Assist integration."""

from typing import Final, Literal

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

# Grok CLI public client (grok-build / auth.x.ai). No Application Credentials.
# Verified byte-for-byte against xai-org/grok-build
# crates/codegen/xai-grok-login/src/config.rs
#   obfstr!("b1a00492-073a-47ea-816f-4c329264a828")
GROK_OAUTH_ISSUER: Final = "https://auth.x.ai"
GROK_OAUTH_CLIENT_ID: Final = "b1a00492-073a-47ea-816f-4c329264a828"
GROK_OAUTH_DEVICE_URL: Final = f"{GROK_OAUTH_ISSUER}/oauth2/device/code"
GROK_OAUTH_TOKEN_URL: Final = f"{GROK_OAUTH_ISSUER}/oauth2/token"
GROK_OAUTH_SCOPES: Final = (
    "openid profile email offline_access "
    "grok-cli:access api:access "
    "conversations:read conversations:write"
)
GROK_DEVICE_GRANT: Final = "urn:ietf:params:oauth:grant-type:device_code"
GROK_OAUTH_REFERRER: Final = "grok-build"
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
