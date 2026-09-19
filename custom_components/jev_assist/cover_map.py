"""Cover service map and position parsing."""

from __future__ import annotations

import re
from typing import Any, Final

# Jev actions that map to a Home Assistant cover service.
# turn_on / turn_off are aliases when Jev reuses those action keys.
COVER_ACTION_MAP: Final[dict[str, tuple[str, str]]] = {
    "open": ("cover", "open_cover"),
    "close": ("cover", "close_cover"),
    "stop": ("cover", "stop_cover"),
    "set_position": ("cover", "set_cover_position"),
    "turn_on": ("cover", "open_cover"),
    "turn_off": ("cover", "close_cover"),
}

POSITION_RE: Final[re.Pattern[str]] = re.compile(
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


def parse_position_pct(utterance: str) -> int | None:
    """Return a 0–100 cover position if the utterance contains a percent."""
    match = POSITION_RE.search(utterance)
    if match is None:
        return None
    value = int(match.group("value"))
    if value > 100:
        return None
    return max(0, min(100, value))


def cover_service_call(
    action: str,
    entity_ids: list[str],
    utterance: str,
) -> tuple[str, str, dict[str, Any]] | None:
    """Map a Jev cover action to (domain, service, data), or None if unmapped."""
    mapped = COVER_ACTION_MAP.get(action)
    if mapped is None or not entity_ids:
        return None
    domain, service = mapped
    data: dict[str, Any] = {
        "entity_id": entity_ids[0] if len(entity_ids) == 1 else entity_ids,
    }
    if action == "set_position":
        position = parse_position_pct(utterance)
        if position is None:
            return None
        data["position"] = position
    return domain, service, data
