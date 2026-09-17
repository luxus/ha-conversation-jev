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
