"""Light service map v0 and brightness parsing."""

from __future__ import annotations

import re
from typing import Any, Final

# v0: only these Jev actions map to a Home Assistant light service.
LIGHT_ACTION_MAP: Final[dict[str, tuple[str, str]]] = {
    "turn_on": ("light", "turn_on"),
    "turn_off": ("light", "turn_off"),
    "toggle": ("light", "toggle"),
    "set_brightness": ("light", "turn_on"),
}

BRIGHTNESS_RE: Final[re.Pattern[str]] = re.compile(
    r"""
    (?P<value>\d{1,3})
    \s*
    (?:
        %
        | (?:percent | procent | prozent)\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# DE/EN "brightness 40" / "Helligkeit 40" without a percent sign.
BRIGHTNESS_WORD_RE: Final[re.Pattern[str]] = re.compile(
    r"""
    (?:
        brightness
        | helligkeit
        | dimm(?:er|en|stufe)?
        | dim(?:\s*to)?
    )
    \s*(?:auf|to|=|:)?\s*
    (?P<value>\d{1,3})
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def parse_brightness_pct(utterance: str) -> int | None:
    """Return a 0–100 brightness percent if the utterance contains one."""
    match = BRIGHTNESS_RE.search(utterance) or BRIGHTNESS_WORD_RE.search(utterance)
    if match is None:
        return None
    value = int(match.group("value"))
    if value > 100:
        return None
    return max(0, min(100, value))


def light_service_call(
    action: str,
    entity_ids: list[str],
    utterance: str,
) -> tuple[str, str, dict[str, Any]] | None:
    """Map a Jev light action to (domain, service, data), or None if unmapped."""
    mapped = LIGHT_ACTION_MAP.get(action)
    if mapped is None or not entity_ids:
        return None
    domain, service = mapped
    data: dict[str, Any] = {
        "entity_id": entity_ids[0] if len(entity_ids) == 1 else entity_ids,
    }
    if action == "set_brightness":
        brightness = parse_brightness_pct(utterance)
        if brightness is None:
            return None
        data["brightness_pct"] = brightness
    return domain, service, data
