# Jev Assist contract (v1)

Blessed decisions for the HACS `jev_assist` conversation agent. Fast-path
domains are **light**, **climate**, and **cover**. Other domains stay Grok.

## Router kinds

`jev_router.route(...)` returns one of:

| kind | meaning |
|------|---------|
| `fast_service` | Deterministic Home Assistant light / climate / cover service call |
| `grok` | Hand off to `conversation.spacexai_grok` via HA `conversation.async_converse` (compound, needs LLM, low confidence, unmapped domain/action, ambiguous target) |
| `reject` | Do not act (unsafe / out of scope / no matching exposed entity for an explicit area) |

## Categories

Choice keys are frozen at **`command | conversation | reject`**.

| Jev category | Route |
|--------------|--------|
| `command` | Fast path if gates + domain map + target resolution pass; otherwise Grok |
| `conversation` | Grok (includes former `home_query` — questions / info, not a device service) |
| `reject` | Reject when confidence ≥ `REJECT_MIN_CONFIDENCE` (includes `out_of_scope`) |

Compound utterances are **not** a fourth category: they are the `is_compound` Noul.
When that Noul is yes, route **Grok** (split / generate) **except** the multi-area
same-action case below.

Do not add categories. Switch / lock / scene / other remain Grok.

## Gates (blessed)

| constant | value | use |
|----------|-------|-----|
| `FAST_MIN_CONFIDENCE` | **0.80** | Minimum Choice confidence for command / domain / action / target_area on the fast path |
| `NOUL_YES_THRESHOLD` | **0.55** | `needs_llm` or `is_compound` `.noul` (P(yes)) at or above this → Grok (unless multi-area same-action) |
| `REJECT_MIN_CONFIDENCE` | 0.80 | `category=reject` at or above this → reject |

## Target resolution (whole-home safety)

`target_area=none` **must not** fire every Assist-exposed entity of a domain when
more than one of that domain is exposed.

Fast path requires **one of**:

1. an **explicit area** (not `none` / `unknown`), scoped to entities of the
   classified domain in that area,
2. **two or more named areas** in the utterance (see multi-area), scoped to the
   union of that domain’s Assist-exposed entities in **only those rooms**,
3. a **name-token** match against entity name / aliases / object id (generic
   words like “light”/“lamp”/“thermostat”/“blinds” do not count), or
4. **exactly one** Assist-exposed entity of that domain, and the action is a
   simple on/off-style action (no name or area needed):
   - light: `turn_on` / `turn_off` / `toggle`
   - climate: `turn_on` / `turn_off`
   - cover: `open` / `close` / `stop` (and `turn_on` / `turn_off` aliases)
   `set_brightness`, `set_temperature`, `set_hvac_mode`, and `set_position`
   still need a name or area.

If none of those → **`grok`** with reason `no_named_or_area_target`. Never fire
all lights / climates / covers.

`unknown` area → Grok (unless two or more named areas were recovered from the
utterance). Explicit area with no matching exposed entity of that domain →
reject (`no_exposed_light` / `no_exposed_climate` / `no_exposed_cover`).

Grok handoff (`conversation.async_converse` / agent lookup) must **never** raise
into the Assist pipeline. Any failure speaks `GROK_HANDOFF_UNAVAILABLE_SPEECH`
and logs route `kind` + `reason` at INFO.

Jev classify / `route()` / exposed-entity collection / `fast_service` `async_call`
must **never** raise into the Assist pipeline. Unexpected exceptions are logged at
ERROR with traceback and Assist speaks `ROUTE_FAILURE_SPEECH`.

## Multi-area same action

`target_area` remains a **single** Choice. The router also matches area **names**
from exposed entities as phrases in the utterance.

**Same domain + same action + two or more named areas** stays **`fast_service`**:
call the mapped service for every Assist-exposed entity of that domain in the
named rooms (union only — not whole-home, not unnamed rooms). This applies even
when `is_compound` is yes (Noul often treats “Schlafzimmer und Flur” as
compound). Low-confidence / `none` / `unknown` `target_area` is allowed for this
recovery path; command / domain / action still need `FAST_MIN_CONFIDENCE`.

Examples that must stay fast (lights on/off):

- DE: „alle Lichter in Schlafzimmer und Flur“
- EN: „all lights in bedroom and hallway“

**Different actions or different domains** in one utterance still go **Grok**
(`is_compound` or `mixed_ops`): e.g. lights on in one room and off in another,
or lights plus blinds. Conflicting on/off or open/close tokens, or generic
tokens from another fast domain, block the multi-area bypass.

## Light map

Action keys: `turn_on | turn_off | toggle | set_brightness | other` (plus
climate/cover keys below). Brightness percent is parsed in `light_map.py`.
Unparsed brightness → Grok (`brightness_unparsed`).

## Climate map

HA services (verified against climate integration actions):
`climate.set_temperature` (`temperature` setpoint), `climate.turn_on`,
`climate.turn_off`, `climate.set_hvac_mode` (`hvac_mode`).

| Jev action | HA service | Extra data |
|------------|------------|------------|
| `set_temperature` | `climate.set_temperature` | `temperature` °C parsed from the utterance (unit or “to/auf N”). Indoor range **5–35**. Percent values and relative “warmer” → Grok (`temperature_unparsed`) |
| `turn_on` / `turn_off` | `climate.turn_on` / `climate.turn_off` | entity ids only |
| `set_hvac_mode` | `climate.set_hvac_mode` | `hvac_mode` in `heat \| cool \| auto \| off \| dry \| fan_only \| heat_cool` when clearly named; else Grok (`hvac_mode_unparsed`) |

`toggle`, humidity, presets, fan/swing, and heat/cool **ranges** (`target_temp_high` /
`target_temp_low`) are underspecified → Grok. Prefer explicit area or name-token;
same whole-home safety as lights.

## Cover map

HA services (verified against cover integration actions):
`cover.open_cover`, `cover.close_cover`, `cover.stop_cover`,
`cover.set_cover_position` (`position` 0–100).

| Jev action | HA service | Extra data |
|------------|------------|------------|
| `open` | `cover.open_cover` | entity ids only |
| `close` | `cover.close_cover` | entity ids only |
| `stop` | `cover.stop_cover` | entity ids only |
| `set_position` | `cover.set_cover_position` | `position` when a **percent** is clear (`%` / percent / Prozent); else Grok (`position_unparsed`) |
| `turn_on` / `turn_off` | aliases for open / close | when Jev reuses those keys |

Tilt services, `toggle`, and relative “halfway” without a percent → Grok.
Prefer explicit area or name-token; same whole-home safety as lights.

## Grok OAuth client

Device-code + PKCE is implemented by shared package
[`ha_spacexai_auth`](https://github.com/luxus/ha-spacexai-auth)
(`start_device_auth` / `poll_token` / `ensure_fresh` / `TokenSet`).
Config Flow UI stays in this integration.

Public Grok CLI `client_id` (leave unchanged; re-exported from the package):

`b1a00492-073a-47ea-816f-4c329264a828`

Verified byte-for-byte against `xai-org/grok-build`
`crates/codegen/xai-grok-login/src/config.rs`
(`obfstr!("b1a00492-073a-47ea-816f-4c329264a828")`).

Device-code + PKCE at `https://auth.x.ai`. Not HA Application Credentials.
API key for `https://api.x.ai` is fallback only.

TypeSafe/Jev remains an API key (`jev-latest` via `typesafe-sdk`).

## Grok handoff

When the router returns `kind=grok`, the conversation entity calls Home Assistant
`conversation.async_converse` with `agent_id=GROK_HANDOFF_AGENT_ID` (default
`conversation.spacexai_grok`, the SpaceXAI umbrella conversation entity). The
same `text`, `conversation_id`, `context`, `language`, `device_id`,
`satellite_id`, and `extra_system_prompt` are forwarded.

Jev does **not** run TTS, STT, or a Grok chat stack. Override the target with
config-entry option/data key `grok_handoff_agent_id`. If the agent is missing,
the target is this agent, or handoff raises any exception, Assist gets
`Grok is not available.` — never an uncaught error in the pipeline.
