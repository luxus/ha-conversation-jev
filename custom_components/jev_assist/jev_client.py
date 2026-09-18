"""TypeSafe SDK wrapper: AsyncTypeSafeClient + jev-latest system_one."""

from __future__ import annotations

import json
from typing import Any, Sequence

from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, SystemOneResponse

from . import criteria
from .const import (
    EXPOSED_ENTITY_CAP,
    TARGET_NONE,
    TARGET_UNKNOWN,
    TYPESAFE_MODEL,
)
from .jev_router import (
    ChoiceView,
    ExposedEntity,
    JevClassification,
    NoulView,
    normalize_language,
)


def localized_options(options: dict[str, dict[str, str]], language: str) -> dict[str, str]:
    """Pick the language string for each option key."""
    return {key: value[language] for key, value in options.items()}


def unique_areas(exposed: Sequence[ExposedEntity]) -> list[str]:
    """Stable unique area names from exposed entities."""
    seen: list[str] = []
    for item in exposed:
        if not item.area:
            continue
        area = str(item.area)
        if area not in seen:
            seen.append(area)
    return seen


def _plain_text(value: object) -> str:
    return str(value)


def _plain_optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


def build_state(
    utterance: str,
    exposed: Sequence[ExposedEntity],
    language: str,
) -> str:
    """JSON-string state for system_one (preferred over a raw dict)."""
    capped = list(exposed)[:EXPOSED_ENTITY_CAP]
    payload: dict[str, Any] = {
        "text": _plain_text(utterance),
        "language": _plain_text(language),
        "exposed_entities": [
            {
                "entity_id": _plain_text(item.entity_id),
                "domain": _plain_text(item.domain),
                "name": _plain_text(item.name),
                "area": _plain_optional_text(item.area),
                "aliases": [_plain_text(alias) for alias in item.aliases],
            }
            for item in capped
        ],
        "areas": unique_areas(capped),
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


def build_questions(language: str, areas: Sequence[str]) -> dict[str, Choice | Noul]:
    """Fan-out Choice/Noul questions from criteria.py."""
    # Area names may be HA ComputedNameType Enums; Choice criteria must stay JSON-safe.
    area_criteria: dict[str, str] = {
        _plain_text(area): _plain_text(area) for area in areas
    }
    area_criteria[TARGET_NONE] = criteria.TARGET_AREA_NONE[language]
    area_criteria[TARGET_UNKNOWN] = criteria.TARGET_AREA_UNKNOWN[language]
    return {
        "category": Choice(
            instructions=criteria.CATEGORY_INSTRUCTIONS[language],
            criteria=localized_options(criteria.CATEGORY_OPTIONS, language),
        ),
        "domain": Choice(
            instructions=criteria.DOMAIN_INSTRUCTIONS[language],
            criteria=localized_options(criteria.DOMAIN_OPTIONS, language),
        ),
        "action": Choice(
            instructions=criteria.ACTION_INSTRUCTIONS[language],
            criteria=localized_options(criteria.ACTION_OPTIONS, language),
        ),
        "target_area": Choice(
            instructions=criteria.TARGET_AREA_INSTRUCTIONS[language],
            criteria=area_criteria,
        ),
        "needs_llm": Noul(instructions=criteria.NOUL_NEEDS_LLM[language]),
        "is_compound": Noul(instructions=criteria.NOUL_IS_COMPOUND[language]),
    }


def _choice_view(result: SystemOneResponse, name: str) -> ChoiceView:
    answer = None
    answers = getattr(result, "answers", None)
    if isinstance(answers, dict):
        answer = answers.get(name)
    if answer is None:
        choices = getattr(result, "choices", None)
        if isinstance(choices, dict):
            answer = choices.get(name)
    if answer is None:
        raise KeyError(name)
    return ChoiceView(
        choice=str(answer.choice),
        confidence=float(answer.confidence),
        probabilities=dict(getattr(answer, "probabilities", {}) or {}),
    )


def _noul_view(result: SystemOneResponse, name: str) -> NoulView:
    answer = None
    answers = getattr(result, "answers", None)
    if isinstance(answers, dict):
        answer = answers.get(name)
    if answer is None:
        nouls = getattr(result, "nouls", None)
        if isinstance(nouls, dict):
            answer = nouls.get(name)
    if answer is None:
        raise KeyError(name)
    return NoulView(noul=float(answer.noul))


def classification_from_sdk(result: SystemOneResponse) -> JevClassification:
    """Normalize SDK SystemOneResponse (answers or choices/nouls)."""
    return JevClassification(
        category=_choice_view(result, "category"),
        domain=_choice_view(result, "domain"),
        action=_choice_view(result, "action"),
        target_area=_choice_view(result, "target_area"),
        needs_llm=_noul_view(result, "needs_llm"),
        is_compound=_noul_view(result, "is_compound"),
    )


class TypeSafeJevClient:
    """Thin async wrapper around ``AsyncTypeSafeClient``."""

    def __init__(self, api_key: str, *, model: str = TYPESAFE_MODEL) -> None:
        self._api_key = api_key
        self._model = model

    async def classify(
        self,
        utterance: str,
        exposed: Sequence[ExposedEntity],
        *,
        language: str,
    ) -> JevClassification:
        lang = normalize_language(language)
        capped = list(exposed)[:EXPOSED_ENTITY_CAP]
        state = build_state(utterance, capped, lang)
        questions = build_questions(lang, unique_areas(capped))
        async with AsyncTypeSafeClient(
            api_key=self._api_key,
            model=self._model,
        ) as client:
            result = await client.system_one(state, questions)
        return classification_from_sdk(result)
