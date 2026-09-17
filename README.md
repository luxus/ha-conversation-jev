# Jev Assist

Home Assistant custom conversation agent: **Jev** (TypeSafe System One, `jev-latest`) classifies an utterance, then either calls a **light** service (v0 fast path) or marks the **Grok** fallback.

## Install (HACS)

1. [HACS](https://hacs.xyz/) → **⋯** → **Custom repositories**
2. URL: `https://github.com/luxus/ha-conversation-jev` — category **Integration**
3. Download **Jev Assist**, then restart Home Assistant
4. **Settings → Devices & services → Add integration → Jev Assist**

Manual install: copy `custom_components/jev_assist/` into your HA `config/custom_components/` folder and restart.

## Configuration

1. **TypeSafe API key** (required) — stored on the config entry, not in `configuration.yaml`.
2. **Grok (primary): Sign in with Grok (uses Grok CLI OAuth client)**  
   Device-code + PKCE against `https://auth.x.ai` using the public Grok CLI `client_id`. Home Assistant shows a URL and user code, polls the token endpoint, and stores **access + refresh** tokens. If the IdP rotates the refresh token, the new one is persisted.
3. **Grok (optional fallback): API key** for `https://api.x.ai` when OAuth entitlement is missing or you bill via console.x.ai.

This integration does **not** use Home Assistant Application Credentials.

After setup, pick **Jev Assist** as the conversation agent in an Assist pipeline.

## What v0 does

- Jev questions (DE/EN) live in `criteria.py` and are sent via the official `typesafe-sdk` (`AsyncTypeSafeClient.system_one`, model `jev-latest`).
- Router kinds: `fast_service` | `grok` | `reject` (see `const.py` for confidence / Noul thresholds).
- Fast path maps light `turn_on` / `turn_off` / `toggle` / `set_brightness` (brightness regex in `light_map.py`).
- The Grok path is a stub in v1 (it is marked, not fully generated).

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Router tests mock Jev; no live API keys are required.
