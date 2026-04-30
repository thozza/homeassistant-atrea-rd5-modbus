"""Tests for Atrea RD5 select entities."""
from __future__ import annotations

import pytest

from tests.conftest import make_coordinator
from custom_components.atrea_rd5_modbus.select import (
    SELECT_DESCRIPTIONS,
    AtreaSelect,
)


def get_description(key: str):
    return next(d for d in SELECT_DESCRIPTIONS if d.key == key)


def test_select_descriptions_keys():
    assert {d.key for d in SELECT_DESCRIPTIONS} == {
        "toda_source", "tida_source", "season_switch",
    }


@pytest.mark.parametrize("key, options", [
    ("toda_source", ["Internal", "BMS"]),
    ("tida_source", ["CP", "T-ETA", "TRKn", "BMS"]),
    ("season_switch", ["TS", "NTS", "T-TODA", "T-TODA+"]),
])
def test_select_descriptions_options(key: str, options: list[str]) -> None:
    desc = get_description(key)
    assert list(desc.options) == options


@pytest.mark.parametrize("key, value", [
    ("toda_source", "BMS"),
    ("tida_source", "CP"),
    ("season_switch", "TS"),
])
def test_select_current_option(key: str, value: str) -> None:
    coordinator = make_coordinator({key: value})
    select = AtreaSelect(coordinator, get_description(key))
    assert select.current_option == value


@pytest.mark.parametrize("data, success, expected", [
    ({"toda_source": "BMS"},     True,  True),
    ({"toda_source": None},      True,  False),
    ({"toda_source": "BMS"},     False, False),
    ({"season_switch": "NTS"},   True,  True),
    ({"season_switch": None},    True,  False),
])
def test_select_available(data: dict, success: bool, expected: bool) -> None:
    key = next(iter(data))
    coordinator = make_coordinator(data, success)
    select = AtreaSelect(coordinator, get_description(key))
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


@pytest.mark.parametrize("option", ["TS", "NTS", "T-TODA", "T-TODA+"])
async def test_season_switch_select_option(option: str) -> None:
    coordinator = make_coordinator({"season_switch": "TS"})
    select = AtreaSelect(coordinator, get_description("season_switch"))

    await select.async_select_option(option)

    coordinator.async_write.assert_awaited_once_with("season_switch", option)
