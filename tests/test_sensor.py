"""Tests for Atrea RD5 sensor entities."""
from __future__ import annotations

import pytest

from tests.conftest import make_coordinator
from custom_components.atrea_rd5_modbus.sensor import (
    SENSOR_DESCRIPTIONS,
    AtreaSensor,
)


def get_description(key: str):
    return next(d for d in SENSOR_DESCRIPTIONS if d.key == key)


def test_sensor_descriptions_count():
    assert len(SENSOR_DESCRIPTIONS) == 8


def test_sensor_descriptions_keys():
    keys = {d.key for d in SENSOR_DESCRIPTIONS}
    assert keys == {
        "temp_oda", "temp_sup", "temp_eta", "temp_eha", "temp_ida",
        "power", "mode", "season",
    }


@pytest.mark.parametrize("key, data, expected", [
    ("temp_oda", {"temp_oda": 20.5},          20.5),
    ("power",    {"power": 75.0},             75.0),
    ("mode",     {"mode": "Automatic"},       "Automatic"),
    ("season",   {"season": "Heating"},       "Heating"),
    ("season",   {"season": "Non-heating"},   "Non-heating"),
    ("temp_oda", None,                        None),   # coordinator.data is None → None
])
def test_sensor_native_value(key: str, data, expected) -> None:
    coordinator = make_coordinator(data)
    sensor = AtreaSensor(coordinator, get_description(key))
    assert sensor.native_value == expected


@pytest.mark.parametrize("key, data, success, expected_available", [
    ("temp_oda", {"temp_oda": 20.5}, True,  True),   # normal: data present, coordinator healthy
    ("temp_oda", {"temp_oda": None}, True,  False),  # value is None (batch failed)
    ("temp_oda", {"temp_oda": 20.5}, False, False),  # coordinator refresh failed
    ("temp_oda", None,               True,  False),  # coordinator.data itself is None
    ("season",   {"season": None},   True,  False),  # season value is None
])
def test_sensor_available(
    key: str, data, success: bool, expected_available: bool
) -> None:
    coordinator = make_coordinator(data, success)
    sensor = AtreaSensor(coordinator, get_description(key))
    assert sensor.available is expected_available


def test_sensor_unique_id():
    coordinator = make_coordinator({"temp_oda": 20.0})
    sensor = AtreaSensor(coordinator, get_description("temp_oda"))
    assert sensor.unique_id == "test_entry_temp_oda"


def test_mode_sensor_options():
    from custom_components.atrea_rd5_modbus.const import OPERATION_MODE_OPTIONS
    desc = get_description("mode")
    assert desc.options == OPERATION_MODE_OPTIONS


def test_sensor_device_info():
    coordinator = make_coordinator({"temp_oda": 20.0})
    sensor = AtreaSensor(coordinator, get_description("temp_oda"))
    info = sensor.device_info
    assert info["manufacturer"] == "Atrea"
    assert info["model"] == "RD5"
    assert info["name"] == "Atrea RD5 @ 192.168.1.100"


def test_season_sensor_options() -> None:
    from custom_components.atrea_rd5_modbus.const import SEASON_STATE_OPTIONS
    desc = get_description("season")
    assert list(desc.options) == SEASON_STATE_OPTIONS


def test_season_sensor_entity_category() -> None:
    from homeassistant.const import EntityCategory
    desc = get_description("season")
    assert desc.entity_category == EntityCategory.DIAGNOSTIC


