"""Assert installed typesafe-sdk exports the documented call shape."""

from __future__ import annotations

import json

from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul

from jev_assist.jev_client import build_questions, build_state
from jev_assist.jev_router import ExposedEntity


def test_sdk_exports() -> None:
    assert AsyncTypeSafeClient is not None
    assert Choice is not None
    assert Noul is not None
    noul = Noul(instructions="yes?")
    assert hasattr(noul, "instructions")


def test_questions_use_choice_and_noul() -> None:
    questions = build_questions("en", ["Living room"])
    assert isinstance(questions["category"], Choice)
    assert isinstance(questions["domain"], Choice)
    assert isinstance(questions["action"], Choice)
    assert isinstance(questions["target_area"], Choice)
    assert isinstance(questions["needs_llm"], Noul)
    assert isinstance(questions["is_compound"], Noul)
    assert "none" in questions["target_area"].criteria
    assert "unknown" in questions["target_area"].criteria
    assert "Living room" in questions["target_area"].criteria


def test_state_is_json_string() -> None:
    state = build_state(
        "Licht aus",
        [
            ExposedEntity(
                entity_id="light.a",
                domain="light",
                name="A",
                area="Küche",
            )
        ],
        "de",
    )
    payload = json.loads(state)
    assert payload["text"] == "Licht aus"
    assert payload["language"] == "de"
    assert payload["areas"] == ["Küche"]
    assert payload["exposed_entities"][0]["entity_id"] == "light.a"
