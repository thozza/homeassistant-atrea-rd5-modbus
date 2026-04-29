"""Tests for Atrea RD5 select entities."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.atrea_rd5_modbus.select import (
    SELECT_DESCRIPTIONS,
    AtreaSelect,
)


def make_coordinator(data: dict, success: bool = True) -> MagicMock:
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
    return next(d for d in SELECT_DESCRIPTIONS if d.key == key)


def test_select_descriptions_keys():
    assert {d.key for d in SELECT_DESCRIPTIONS} == {"toda_source", "tida_source"}


@pytest.mark.parametrize("key, options", [
    ("toda_source", ["Internal", "BMS"]),
    ("tida_source", ["CP", "T-ETA", "TRKn", "BMS"]),
])
def test_select_descriptions_options(key: str, options: list[str]) -> None:
    desc = get_description(key)
    assert list(desc.options) == options


@pytest.mark.parametrize("key, value", [
    ("toda_source", "BMS"),
    ("tida_source", "CP"),
])
def test_select_current_option(key: str, value: str) -> None:
    coordinator = make_coordinator({key: value})
    select = AtreaSelect(coordinator, get_description(key))
    assert select.current_option == value


@pytest.mark.parametrize("data, success, expected", [
    ({"toda_source": "BMS"},   True,  True),
    ({"toda_source": None},    True,  False),
    ({"toda_source": "BMS"},   False, False),
])
def test_select_available(data: dict, success: bool, expected: bool) -> None:
    coordinator = make_coordinator(data, success)
    select = AtreaSelect(coordinator, get_description("toda_source"))
    assert select.available is expected


async def test_select_async_select_option_calls_async_write():
    coordinator = make_coordinator({"toda_source": "Internal"})
    select = AtreaSelect(coordinator, get_description("toda_source"))

    await select.async_select_option("BMS")

    coordinator.async_write.assert_awaited_once_with("toda_source", "BMS")


def test_select_unique_id():
    coordinator = make_coordinator({"toda_source": "BMS"})
    select = AtreaSelect(coordinator, get_description("toda_source"))
    assert select.unique_id == "test_entry_toda_source"
