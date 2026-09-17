# Jev Assist

Home Assistant custom conversation agent: **Jev** (TypeSafe System One, `jev-latest`) classifies an utterance, then either calls a **light** service (v0 fast path) or hands off to the **SpaceXAI Grok** conversation agent.

## Install (HACS)

1. [HACS](https://hacs.xyz/) → **⋯** → **Custom repositories**
2. URL: `https://github.com/luxus/ha-conversation-jev` — category **Integration**
3. Download **Jev Assist**, then restart Home Assistant
4. **Settings → Devices & services → Add integration → Jev Assist**

Manual install: copy `custom_components/jev_assist/` into your HA `config/custom_components/` folder and restart.

## Configuration

1. **TypeSafe / Jev API key** (required, from [typesafe.ai](https://typesafe.ai); the same key if issued via Vercel) — stored on the config entry, not in `configuration.yaml`.
2. **Grok (primary): Sign in with Grok (uses Grok CLI OAuth client)**  
   Device-code + PKCE against `https://auth.x.ai` via shared package
   [`ha_spacexai_auth`](https://github.com/luxus/ha-spacexai-auth)
   (`start_device_auth` / `poll_token` / `ensure_fresh`) using the public Grok CLI `client_id`
   `b1a00492-073a-47ea-816f-4c329264a828`
   (verified against `xai-org/grok-build` `crates/codegen/xai-grok-login/src/config.rs`).
   Home Assistant shows a URL and user code, polls the token endpoint, and stores **access + refresh** tokens. Setup/reload calls `ensure_fresh` (refresh only near expiry). If the IdP rotates the refresh token, the new one is persisted.
3. **Grok (optional fallback): API key** for `https://api.x.ai` when OAuth entitlement is missing or you bill via console.x.ai.

This integration does **not** use Home Assistant Application Credentials.

After setup, pick **Jev Assist** as the conversation agent in an Assist pipeline.

## What v0 does

- Jev questions (DE/EN) live in `criteria.py` and are sent via the official `typesafe-sdk` (`AsyncTypeSafeClient.system_one`, model `jev-latest`).
- Router kinds: `fast_service` | `grok` | `reject` (gates in `CONTRACT.md` / `const.py`: `FAST_MIN_CONFIDENCE=0.80`, `NOUL_YES_THRESHOLD=0.55`).
- Fast path maps light `turn_on` / `turn_off` / `toggle` / `set_brightness` (brightness regex in `light_map.py`).
- Whole-home safety: `target_area=none` never fires all exposed lights. Needs a name-token match, an explicit area, or exactly one Assist-exposed light for `turn_on` / `turn_off` / `toggle`.
- Grok path: `conversation.async_converse` to `conversation.spacexai_grok` (`GROK_HANDOFF_AGENT_ID`; override with config-entry `grok_handoff_agent_id`). No TTS/STT/chat stack inside Jev.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Router tests mock Jev; no live API keys are required.
