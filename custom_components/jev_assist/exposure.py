"""Assist exposure helpers: fail-closed evaluation and lights-first order."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .const import DOMAIN_LIGHT
from .jev_router import ExposedEntity


def should_expose_compat(call: Callable[[], bool]) -> bool:
    """Evaluate an expose helper.

    ``TypeError`` is the known compatibility case (HA signature mismatch) and
    fails closed. Unexpected errors are re-raised so they are not treated as
    "exposed".
    """
    try:
        return bool(call())
    except TypeError:
        return False


def sort_lights_first(items: Iterable[ExposedEntity]) -> list[ExposedEntity]:
    """Stable-ish order with ``light`` entities ahead of other domains."""
    return sorted(items, key=lambda item: (item.domain != DOMAIN_LIGHT, item.entity_id))
