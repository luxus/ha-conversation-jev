"""criteria.py is bilingual DE/EN for every option."""

from jev_assist import criteria

_LANGS = ("en", "de")


def _assert_lang_map(name: str, value: dict[str, str]) -> None:
    assert set(value) >= set(_LANGS), name


def test_instruction_maps_are_bilingual() -> None:
    for name in (
        "CATEGORY_INSTRUCTIONS",
        "DOMAIN_INSTRUCTIONS",
        "ACTION_INSTRUCTIONS",
        "TARGET_AREA_INSTRUCTIONS",
        "TARGET_AREA_NONE",
        "TARGET_AREA_UNKNOWN",
        "NOUL_NEEDS_LLM",
        "NOUL_IS_COMPOUND",
    ):
        _assert_lang_map(name, getattr(criteria, name))


def test_option_maps_are_bilingual() -> None:
    for name in ("CATEGORY_OPTIONS", "DOMAIN_OPTIONS", "ACTION_OPTIONS"):
        options = getattr(criteria, name)
        assert options
        for key, langs in options.items():
            _assert_lang_map(f"{name}.{key}", langs)


def test_action_keys_align_with_fast_maps() -> None:
    """Action keys include light/climate/cover maps; ``other`` stays unmapped."""
    from jev_assist.climate_map import CLIMATE_ACTION_MAP
    from jev_assist.cover_map import COVER_ACTION_MAP
    from jev_assist.light_map import LIGHT_ACTION_MAP

    frozen = {
        "turn_on",
        "turn_off",
        "toggle",
        "set_brightness",
        "set_temperature",
        "set_hvac_mode",
        "open",
        "close",
        "stop",
        "set_position",
        "other",
    }
    assert set(criteria.ACTION_OPTIONS) == frozen
    assert set(LIGHT_ACTION_MAP) == {
        "turn_on",
        "turn_off",
        "toggle",
        "set_brightness",
    }
    assert set(CLIMATE_ACTION_MAP) == {
        "set_temperature",
        "turn_on",
        "turn_off",
        "set_hvac_mode",
    }
    assert "open" in COVER_ACTION_MAP
    assert "close" in COVER_ACTION_MAP
    assert "stop" in COVER_ACTION_MAP
    assert "set_position" in COVER_ACTION_MAP
    assert set(LIGHT_ACTION_MAP) <= frozen
    assert set(CLIMATE_ACTION_MAP) <= frozen
    assert set(COVER_ACTION_MAP) <= frozen
    assert "other" not in LIGHT_ACTION_MAP
    assert "other" not in CLIMATE_ACTION_MAP
    assert "other" not in COVER_ACTION_MAP


def test_blessed_gate_constants() -> None:
    from jev_assist.const import (
        FAST_MIN_CONFIDENCE,
        NOUL_YES_THRESHOLD,
        REJECT_MIN_CONFIDENCE,
    )

    assert FAST_MIN_CONFIDENCE == 0.80
    assert NOUL_YES_THRESHOLD == 0.55
    assert REJECT_MIN_CONFIDENCE == 0.80


def test_instructions_backtick_state_paths() -> None:
    """Questions point at named state fields so Jev can resolve nested paths."""
    for lang in _LANGS:
        assert "`text`" in criteria.CATEGORY_INSTRUCTIONS[lang]
        assert "`text`" in criteria.DOMAIN_INSTRUCTIONS[lang]
        assert "`exposed_entities`" in criteria.DOMAIN_INSTRUCTIONS[lang]
        assert "`text`" in criteria.ACTION_INSTRUCTIONS[lang]
        assert "`text`" in criteria.TARGET_AREA_INSTRUCTIONS[lang]
        assert "`areas`" in criteria.TARGET_AREA_INSTRUCTIONS[lang]
        assert "`text`" in criteria.NOUL_NEEDS_LLM[lang]
        assert "`text`" in criteria.NOUL_IS_COMPOUND[lang]
        assert "`areas`" in criteria.NOUL_IS_COMPOUND[lang]
