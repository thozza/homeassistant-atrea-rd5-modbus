"""Tests for Atrea RD5 integration setup/teardown lifecycle."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.atrea_rd5_modbus import async_setup_entry, async_unload_entry
from custom_components.atrea_rd5_modbus.const import DOMAIN


def make_entry(data: dict | None = None) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data=data or {
            "host": "192.168.1.100",
            "port": 502,
            "slave_id": 1,
            "scan_interval": 30,
        },
    )


@pytest.mark.parametrize("connected", [False])
async def test_setup_entry_raises_when_not_connected(hass, connected: bool) -> None:
    """ConfigEntryNotReady is raised when the TCP connection fails."""
    client = MagicMock()
    client.connect = AsyncMock()
    client.connected = connected
    client.close = MagicMock()

    entry = make_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.atrea_rd5_modbus.AsyncModbusTcpClient",
        return_value=client,
    ):
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)

    client.close.assert_called_once()


async def test_setup_entry_raises_on_connect_exception(hass) -> None:
    """ConfigEntryNotReady is raised when connect() throws."""
    client = MagicMock()
    client.connect = AsyncMock(side_effect=OSError("connection refused"))
    client.close = MagicMock()

    entry = make_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.atrea_rd5_modbus.AsyncModbusTcpClient",
        return_value=client,
    ):
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)

    client.close.assert_called_once()


async def test_unload_entry_closes_client(hass, mock_modbus_client) -> None:
    """async_unload_entry closes the Modbus client and removes hass.data entry."""
    coordinator = MagicMock()
    coordinator.client = mock_modbus_client

    entry = make_entry()
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=True,
    ):
        result = await async_unload_entry(hass, entry)

    assert result is True
    mock_modbus_client.close.assert_called_once()
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


def test_platforms_includes_select_and_number():
    from homeassistant.const import Platform

    from custom_components.atrea_rd5_modbus import PLATFORMS

    assert Platform.SENSOR in PLATFORMS
    assert Platform.SELECT in PLATFORMS
    assert Platform.NUMBER in PLATFORMS


async def test_options_update_listener_reloads_entry(hass):
    """Changing options reloads the config entry so the coordinator picks up the new interval."""
    from custom_components.atrea_rd5_modbus import _async_options_update_listener

    entry = make_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload",
        new=AsyncMock(return_value=True),
    ) as mock_reload:
        await _async_options_update_listener(hass, entry)

    mock_reload.assert_awaited_once_with(entry.entry_id)
