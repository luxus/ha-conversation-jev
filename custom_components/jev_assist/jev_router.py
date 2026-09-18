"""Jev routing: fast HA light service, Grok fallback, or reject."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, Sequence

from .const import (
    CATEGORY_COMMAND,
    CATEGORY_REJECT,
    DEFAULT_LANGUAGE,
    DOMAIN_LIGHT,
    FAST_MIN_CONFIDENCE,
    NOUL_YES_THRESHOLD,
    REJECT_MIN_CONFIDENCE,
    TARGET_NONE,
    TARGET_UNKNOWN,
)
from .light_map import LIGHT_ACTION_MAP, light_service_call

_TOKEN_RE = re.compile(r"[a-z0-9äöüß]+", re.IGNORECASE)
_STOP_TOKENS = frozenset(
    {
        "the",
        "a",
        "an",
        "to",
        "on",
        "off",
        "turn",
        "set",
        "please",
        "all",
        "make",
        "it",
        "and",
        "in",
        "of",
        "my",
        "me",
        "das",
        "die",
        "der",
        "den",
        "dem",
        "ein",
        "eine",
        "einen",
        "auf",
        "aus",
        "bitte",
        "schalte",
        "mach",
        "machen",
    }
)
_GENERIC_LIGHT_TOKENS = frozenset(
    {
        "light",
        "lights",
        "lamp",
        "lamps",
        "licht",
        "lichter",
        "lampe",
        "lampen",
        "bulb",
        "bulbs",
        "led",
        "dimmer",
    }
)

RouteKind = Literal["fast_service", "grok", "reject"]


@dataclass(frozen=True)
class ExposedEntity:
    """An Assist-exposed entity passed into Jev state."""

    entity_id: str
    domain: str
    name: str
    area: str | None = None
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # HA entity_registry aliases are AliasEntry = str | ComputedNameType.
        object.__setattr__(self, "entity_id", str(self.entity_id))
        object.__setattr__(self, "domain", str(self.domain))
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(
            self, "area", None if self.area is None else str(self.area)
        )
        object.__setattr__(
            self, "aliases", tuple(str(alias) for alias in self.aliases)
        )


@dataclass(frozen=True)
class ChoiceView:
    """SDK-agnostic Choice answer."""

    choice: str
    confidence: float
    probabilities: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class NoulView:
    """SDK-agnostic Noul answer. ``noul`` is P(yes) in [0, 1]."""

    noul: float


@dataclass(frozen=True)
class JevClassification:
    """Normalized Jev answers used by the gate."""

    category: ChoiceView
    domain: ChoiceView
    action: ChoiceView
    target_area: ChoiceView
    needs_llm: NoulView
    is_compound: NoulView


@dataclass(frozen=True)
class RouteResult:
    """Result of ``route``."""

    kind: RouteKind
    reason: str
    domain: str | None = None
    service: str | None = None
    service_data: dict[str, Any] | None = None
    classification: JevClassification | None = None


class JevClientProtocol(Protocol):
    """Mockable Jev classifier (real SDK or test double)."""

    async def classify(
        self,
        utterance: str,
        exposed: Sequence[ExposedEntity],
        *,
        language: str,
    ) -> JevClassification: ...


def normalize_language(language: str | None) -> str:
    """Map HA language tags to ``en`` / ``de``."""
    if not language:
        return DEFAULT_LANGUAGE
    tag = language.lower().replace("_", "-")
    if tag == "de" or tag.startswith("de-"):
        return "de"
    return DEFAULT_LANGUAGE


def _choice_ok(view: ChoiceView, expected: str | None = None) -> bool:
    if view.confidence < FAST_MIN_CONFIDENCE:
        return False
    if expected is not None and view.choice != expected:
        return False
    return True


def _noul_yes(view: NoulView) -> bool:
    return view.noul >= NOUL_YES_THRESHOLD


def _words(text: str) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN_RE.finditer(text)}


def _entity_name_tokens(entity: ExposedEntity) -> set[str]:
    """Distinctive name tokens (not domain generics / stopwords)."""
    blob = " ".join(
        (entity.name, entity.entity_id.split(".", 1)[-1].replace("_", " "), *entity.aliases)
    )
    return {
        token
        for token in _words(blob)
        if len(token) >= 3 and token not in _STOP_TOKENS and token not in _GENERIC_LIGHT_TOKENS
    }


def _name_matched_lights(
    utterance: str, lights: Sequence[ExposedEntity]
) -> list[ExposedEntity]:
    uttered = _words(utterance)
    return [item for item in lights if _entity_name_tokens(item) & uttered]


_SOLE_LIGHT_FAST_ACTIONS = frozenset({"turn_on", "turn_off", "toggle"})


def _resolve_lights(
    utterance: str,
    exposed: Sequence[ExposedEntity],
    target_area: str,
    *,
    action: str | None = None,
) -> tuple[list[ExposedEntity], str | None]:
    """Resolve light targets. Never fire all exposed lights on ``none`` alone.

    Fast path requires an explicit area (not none/unknown), a name-token
    match, or exactly one Assist-exposed light for ``turn_on`` / ``turn_off`` /
    ``toggle``. Otherwise the caller should Grok, not whole-home.
    """
    lights = [item for item in exposed if item.domain == DOMAIN_LIGHT]
    if target_area == TARGET_UNKNOWN:
        return [], "target_area_unknown"
    if target_area and target_area != TARGET_NONE:
        wanted = target_area.casefold()
        scoped = [item for item in lights if (item.area or "").casefold() == wanted]
        if not scoped:
            return [], "no_exposed_light"
        return scoped, None
    named = _name_matched_lights(utterance, lights)
    if named:
        return named, None
    if action in _SOLE_LIGHT_FAST_ACTIONS and len(lights) == 1:
        return lights, None
    return [], "no_named_or_area_target"


def apply_gates(
    utterance: str,
    exposed: Sequence[ExposedEntity],
    classification: JevClassification,
) -> RouteResult:
    """Apply CONTRACT.md v0 gates to a Jev classification."""
    cat = classification.category
    if cat.choice == CATEGORY_REJECT and cat.confidence >= REJECT_MIN_CONFIDENCE:
        return RouteResult(
            kind="reject",
            reason="category_reject",
            classification=classification,
        )

    if _noul_yes(classification.is_compound):
        return RouteResult(
            kind="grok",
            reason="is_compound",
            classification=classification,
        )
    if _noul_yes(classification.needs_llm):
        return RouteResult(
            kind="grok",
            reason="needs_llm",
            classification=classification,
        )

    if not _choice_ok(cat, CATEGORY_COMMAND):
        return RouteResult(
            kind="grok",
            reason="not_fast_command",
            classification=classification,
        )
    if not _choice_ok(classification.domain, DOMAIN_LIGHT):
        return RouteResult(
            kind="grok",
            reason="domain_not_light_v0",
            classification=classification,
        )
    if (
        classification.action.choice not in LIGHT_ACTION_MAP
        or classification.action.confidence < FAST_MIN_CONFIDENCE
    ):
        return RouteResult(
            kind="grok",
            reason="action_unmapped",
            classification=classification,
        )
    if classification.target_area.confidence < FAST_MIN_CONFIDENCE:
        return RouteResult(
            kind="grok",
            reason="target_area_low_confidence",
            classification=classification,
        )

    lights, target_reason = _resolve_lights(
        utterance,
        exposed,
        classification.target_area.choice,
        action=classification.action.choice,
    )
    if not lights:
        kind: RouteKind = (
            "reject" if target_reason == "no_exposed_light" else "grok"
        )
        return RouteResult(
            kind=kind,
            reason=target_reason or "no_named_or_area_target",
            classification=classification,
        )

    mapped = light_service_call(
        classification.action.choice,
        [item.entity_id for item in lights],
        utterance,
    )
    if mapped is None:
        return RouteResult(
            kind="grok",
            reason="brightness_unparsed",
            classification=classification,
        )
    domain, service, data = mapped
    return RouteResult(
        kind="fast_service",
        reason="light_v0",
        domain=domain,
        service=service,
        service_data=data,
        classification=classification,
    )


async def route(
    utterance: str,
    exposed: Sequence[ExposedEntity],
    *,
    language: str,
    client: JevClientProtocol,
) -> RouteResult:
    """Classify with Jev and route to ``fast_service``, ``grok``, or ``reject``."""
    classification = await client.classify(
        utterance,
        exposed,
        language=normalize_language(language),
    )
    return apply_gates(utterance, exposed, classification)
