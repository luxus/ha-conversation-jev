# Jev Assist contract (v0)

Blessed decisions for the HACS `jev_assist` conversation agent. Do not expand
fast-path domains until climate/cover land.

## Router kinds

`jev_router.route(...)` returns one of:

| kind | meaning |
|------|---------|
| `fast_service` | Deterministic Home Assistant light service call |
| `grok` | Hand off to `conversation.spacexai_grok` via HA `conversation.async_converse` (compound, needs LLM, low confidence, non-light, ambiguous target) |
| `reject` | Do not act (unsafe / out of scope / no matching exposed entity for an explicit area) |

## Categories

Choice keys are frozen at **`command | conversation | reject`**.

| Jev category | Route |
|--------------|--------|
| `command` | Fast path if gates + light map + target resolution pass; otherwise Grok |
| `conversation` | Grok (includes former `home_query` — questions / info, not a device service) |
| `reject` | Reject when confidence ≥ `REJECT_MIN_CONFIDENCE` (includes `out_of_scope`) |

Compound utterances are **not** a fourth category: they are the `is_compound` Noul.
When that Noul is yes, route **Grok** (split / generate) even if category is `command`.

Do not add categories until climate/cover get a `fast_service` map.

## Gates (blessed)

| constant | value | use |
|----------|-------|-----|
| `FAST_MIN_CONFIDENCE` | **0.80** | Minimum Choice confidence for command / domain / action / target_area on the fast path |
| `NOUL_YES_THRESHOLD` | **0.55** | `needs_llm` or `is_compound` `.noul` (P(yes)) at or above this → Grok |
| `REJECT_MIN_CONFIDENCE` | 0.80 | `category=reject` at or above this → reject |

## Target resolution (whole-home safety)

`target_area=none` **must not** fire every Assist-exposed light when more than
one light is exposed.

Fast path requires **one of**:

1. an **explicit area** (not `none` / `unknown`), scoped to lights in that area,
2. a **name-token** match against entity name / aliases / object id (generic words like “light”/“lamp” do not count), or
3. **exactly one** Assist-exposed light, and the action is `turn_on` / `turn_off` / `toggle` (no name or area needed). `set_brightness` still needs a name or area.

If none of those → **`grok`** with reason `no_named_or_area_target`. Never fire all lights.

`unknown` area → Grok. Explicit area with no matching exposed light → reject.

Grok handoff (`conversation.async_converse` / agent lookup) must **never** raise
into the Assist pipeline. Any failure speaks `GROK_HANDOFF_UNAVAILABLE_SPEECH`
and logs route `kind` + `reason` at INFO.

Jev classify / `route()` / exposed-entity collection / `fast_service` `async_call`
must **never** raise into the Assist pipeline. Unexpected exceptions are logged at
ERROR with traceback and Assist speaks `ROUTE_FAILURE_SPEECH`.

## Light map v0

Action keys: `turn_on | turn_off | toggle | set_brightness | other`.
Only the first four map to HA `light` services. Brightness percent is parsed in
`light_map.py`. Climate/cover may appear in classification `domain` but are Grok.

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
