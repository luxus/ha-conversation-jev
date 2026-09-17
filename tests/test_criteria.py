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


def test_action_keys_align_with_light_map() -> None:
    """Freeze v0 action keys vs the light service map."""
    from jev_assist.light_map import LIGHT_ACTION_MAP

    frozen = {"turn_on", "turn_off", "toggle", "set_brightness", "other"}
    assert set(criteria.ACTION_OPTIONS) == frozen
    assert set(LIGHT_ACTION_MAP) == frozen - {"other"}
    assert set(LIGHT_ACTION_MAP) <= set(criteria.ACTION_OPTIONS)
    assert set(LIGHT_ACTION_MAP) & set(criteria.ACTION_OPTIONS) == {
        "turn_on",
        "turn_off",
        "toggle",
        "set_brightness",
    }


def test_blessed_gate_constants() -> None:
    from jev_assist.const import FAST_MIN_CONFIDENCE, NOUL_YES_THRESHOLD

    assert FAST_MIN_CONFIDENCE == 0.80
    assert NOUL_YES_THRESHOLD == 0.55
