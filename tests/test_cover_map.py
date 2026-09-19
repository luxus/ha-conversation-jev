"""Cover service map and position parsing."""

from jev_assist.cover_map import cover_service_call, parse_position_pct


def test_parse_position_percent_en() -> None:
    assert parse_position_pct("set blinds to 50%") == 50
    assert parse_position_pct("80 percent please") == 80


def test_parse_position_percent_de() -> None:
    assert parse_position_pct("Jalousie auf 25%") == 25
    assert parse_position_pct("auf 10 Prozent") == 10
    assert parse_position_pct("Position 40") is None


def test_parse_rejects_over_100() -> None:
    assert parse_position_pct("150%") is None


def test_open_close_stop() -> None:
    assert cover_service_call("open", ["cover.a"], "open") == (
        "cover",
        "open_cover",
        {"entity_id": "cover.a"},
    )
    assert cover_service_call("close", ["cover.a", "cover.b"], "close")[2]["entity_id"] == [
        "cover.a",
        "cover.b",
    ]
    assert cover_service_call("stop", ["cover.a"], "stop")[1] == "stop_cover"


def test_turn_on_off_aliases() -> None:
    assert cover_service_call("turn_on", ["cover.a"], "on")[1] == "open_cover"
    assert cover_service_call("turn_off", ["cover.a"], "off")[1] == "close_cover"


def test_set_position_requires_percent() -> None:
    assert cover_service_call("set_position", ["cover.a"], "halfway") is None
    assert cover_service_call("set_position", ["cover.a"], "position 12") is None
    mapped = cover_service_call("set_position", ["cover.a"], "auf 12%")
    assert mapped is not None
    assert mapped[2]["position"] == 12


def test_unmapped_action() -> None:
    assert cover_service_call("toggle", ["cover.a"], "toggle") is None
    assert cover_service_call("other", ["cover.a"], "hello") is None
