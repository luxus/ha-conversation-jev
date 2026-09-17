"""Fail-closed expose helper and lights-first ordering."""

from __future__ import annotations

import json

import pytest

from jev_assist.const import EXPOSED_ENTITY_CAP
from jev_assist.exposure import should_expose_compat, sort_lights_first
from jev_assist.jev_client import build_state
from jev_assist.jev_router import ExposedEntity


def test_should_expose_true() -> None:
    assert should_expose_compat(lambda: True) is True


def test_should_expose_false() -> None:
    assert should_expose_compat(lambda: False) is False


def test_should_expose_typeerror_fails_closed() -> None:
    def boom() -> bool:
        raise TypeError("unexpected keyword argument")

    assert should_expose_compat(boom) is False


def test_should_expose_unexpected_error_reraise() -> None:
    def boom() -> bool:
        raise RuntimeError("hass exploded")

    with pytest.raises(RuntimeError, match="hass exploded"):
        should_expose_compat(boom)


def test_sort_lights_first_before_cap() -> None:
    sensors = [
        ExposedEntity(
            entity_id=f"sensor.s{i:03d}",
            domain="sensor",
            name=f"Sensor {i}",
        )
        for i in range(EXPOSED_ENTITY_CAP)
    ]
    light = ExposedEntity(
        entity_id="light.kitchen",
        domain="light",
        name="Kitchen",
        area="Kitchen",
    )
    ordered = sort_lights_first([*sensors, light])
    assert ordered[0].entity_id == "light.kitchen"
    capped = ordered[:EXPOSED_ENTITY_CAP]
    assert any(item.domain == "light" for item in capped)
    payload = json.loads(build_state("turn off kitchen", capped, "en"))
    ids = [item["entity_id"] for item in payload["exposed_entities"]]
    assert "light.kitchen" in ids
