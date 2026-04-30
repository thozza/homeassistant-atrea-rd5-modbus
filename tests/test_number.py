"""Tests for Atrea RD5 BMS setpoint number entities."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.device_registry import DeviceInfo
from pymodbus.exceptions import ModbusException

from custom_components.atrea_rd5_modbus.number import (
    COORDINATOR_NUMBER_DESCRIPTIONS,
    AtreaNumber,
    NUMBER_DESCRIPTIONS,
    AtreaBmsNumber,
)


def make_coordinator(data: dict | None = None, success: bool = True) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.last_update_success = success
    coordinator.config_entry.entry_id = "test_entry"
    coordinator.config_entry.data = {"host": "192.168.1.100"}
    coordinator.device_info = DeviceInfo(
        identifiers={("atrea_rd5_modbus", "test_entry")},
        name="Atrea RD5 @ 192.168.1.100",
        manufacturer="Atrea",
        model="RD5",
    )
    coordinator.async_write = AsyncMock()
    return coordinator


def get_description(key: str):
    return next(d for d in NUMBER_DESCRIPTIONS if d.key == key)


def test_number_descriptions_keys():
    assert {d.key for d in NUMBER_DESCRIPTIONS} == {"bms_toda", "bms_tida"}


@pytest.mark.parametrize("key", ["bms_toda", "bms_tida"])
def test_number_description_range(key: str) -> None:
    desc = get_description(key)
    assert desc.native_min_value == -50.0
    assert desc.native_max_value == 130.0
    assert desc.native_step == 0.1


async def test_async_set_native_value_writes_and_updates_state():
    coordinator = make_coordinator()
    number = AtreaBmsNumber(coordinator, get_description("bms_toda"))
    number.async_write_ha_state = MagicMock()

    await number.async_set_native_value(21.5)

    coordinator.async_write.assert_awaited_once_with("bms_toda", 21.5)
    assert number.native_value == 21.5
    number.async_write_ha_state.assert_called_once()


async def test_async_added_to_hass_pushes_restored_value():
    coordinator = make_coordinator()
    number = AtreaBmsNumber(coordinator, get_description("bms_toda"))

    last = MagicMock()
    last.native_value = 19.7
    with patch.object(
        AtreaBmsNumber, "async_get_last_number_data", AsyncMock(return_value=last)
    ), patch(
        "custom_components.atrea_rd5_modbus.number.RestoreNumber.async_added_to_hass",
        AsyncMock(),
    ):
        await number.async_added_to_hass()

    coordinator.async_write.assert_awaited_once_with("bms_toda", 19.7)
    assert number.native_value == 19.7


async def test_async_added_to_hass_no_restored_value_does_nothing():
    coordinator = make_coordinator()
    number = AtreaBmsNumber(coordinator, get_description("bms_toda"))

    with patch.object(
        AtreaBmsNumber, "async_get_last_number_data", AsyncMock(return_value=None)
    ), patch(
        "custom_components.atrea_rd5_modbus.number.RestoreNumber.async_added_to_hass",
        AsyncMock(),
    ):
        await number.async_added_to_hass()

    coordinator.async_write.assert_not_called()
    assert number.native_value is None


async def test_async_added_to_hass_swallows_modbus_error():
    coordinator = make_coordinator()
    coordinator.async_write = AsyncMock(side_effect=ModbusException("offline"))
    number = AtreaBmsNumber(coordinator, get_description("bms_toda"))

    last = MagicMock()
    last.native_value = 18.0
    with patch.object(
        AtreaBmsNumber, "async_get_last_number_data", AsyncMock(return_value=last)
    ), patch(
        "custom_components.atrea_rd5_modbus.number.RestoreNumber.async_added_to_hass",
        AsyncMock(),
    ):
        # Must not raise even though async_write blew up.
        await number.async_added_to_hass()

    assert number.native_value == 18.0


def test_number_unique_id():
    coordinator = make_coordinator()
    number = AtreaBmsNumber(coordinator, get_description("bms_toda"))
    assert number.unique_id == "test_entry_bms_toda"


async def test_async_set_native_value_raises_on_write_failure():
    coordinator = make_coordinator()
    coordinator.async_write = AsyncMock(side_effect=ModbusException("timeout"))
    number = AtreaBmsNumber(coordinator, get_description("bms_toda"))

    with pytest.raises(ModbusException):
        await number.async_set_native_value(21.5)

    assert number.native_value is None


def get_coordinator_number_description(key: str):
    return next(d for d in COORDINATOR_NUMBER_DESCRIPTIONS if d.key == key)


def test_coordinator_number_descriptions_keys():
    assert {d.key for d in COORDINATOR_NUMBER_DESCRIPTIONS} == {"season_temp_thr"}


def test_coordinator_number_description_range():
    desc = get_coordinator_number_description("season_temp_thr")
    assert desc.native_min_value == 0.0
    assert desc.native_max_value == 30.0
    assert desc.native_step == 0.1


def test_atrea_number_native_value():
    coordinator = make_coordinator({"season_temp_thr": 15.0})
    number = AtreaNumber(coordinator, get_coordinator_number_description("season_temp_thr"))
    assert number.native_value == 15.0


def test_atrea_number_native_value_none_when_data_is_none():
    coordinator = make_coordinator({"season_temp_thr": 15.0})
    coordinator.data = None
    number = AtreaNumber(coordinator, get_coordinator_number_description("season_temp_thr"))
    assert number.native_value is None


@pytest.mark.parametrize("data, success, expected", [
    ({"season_temp_thr": 15.0}, True,  True),
    ({"season_temp_thr": None}, True,  False),
    ({"season_temp_thr": 15.0}, False, False),
])
def test_atrea_number_available(data: dict, success: bool, expected: bool) -> None:
    coordinator = make_coordinator(data, success)
    number = AtreaNumber(coordinator, get_coordinator_number_description("season_temp_thr"))
    assert number.available is expected


def test_atrea_number_available_when_coordinator_data_is_none():
    coordinator = make_coordinator(None)
    number = AtreaNumber(coordinator, get_coordinator_number_description("season_temp_thr"))
    assert number.available is False


async def test_atrea_number_set_native_value():
    coordinator = make_coordinator({"season_temp_thr": 15.0})
    number = AtreaNumber(coordinator, get_coordinator_number_description("season_temp_thr"))
    number.async_write_ha_state = MagicMock()

    await number.async_set_native_value(20.0)

    coordinator.async_write.assert_awaited_once_with("season_temp_thr", 20.0)
    number.async_write_ha_state.assert_called_once()


def test_atrea_number_unique_id():
    coordinator = make_coordinator({"season_temp_thr": 15.0})
    number = AtreaNumber(coordinator, get_coordinator_number_description("season_temp_thr"))
    assert number.unique_id == "test_entry_season_temp_thr"
