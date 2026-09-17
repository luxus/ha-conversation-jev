# Jev Assist contract (v0)

Blessed decisions for the HACS `jev_assist` conversation agent. Do not expand
fast-path domains until climate/cover land.

## Router kinds

`jev_router.route(...)` returns one of:

| kind | meaning |
|------|---------|
| `fast_service` | Deterministic Home Assistant light service call |
| `grok` | Hand off to Grok (compound, needs LLM, low confidence, non-light, ambiguous target) |
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

`target_area=none` **must not** fire every Assist-exposed light.

Fast path requires **either**:

1. an **explicit area** (not `none` / `unknown`), scoped to lights in that area, or
2. a **name-token** match against entity name / aliases / object id (generic words like “light”/“lamp” do not count).

If neither → **`grok`** with reason `no_named_or_area_target`. Never blind whole-home.

`unknown` area → Grok. Explicit area with no matching exposed light → reject.

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
