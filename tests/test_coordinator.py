"""Tests for AtreaCoordinator batch read logic."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.atrea_rd5_modbus.coordinator import AtreaCoordinator


def make_mock_entry(data: dict | None = None):
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = data or {
        "host": "192.168.1.100",
        "port": 502,
        "slave_id": 1,
        "scan_interval": 30,
    }
    return entry


async def test_update_data_success(mock_modbus_client):
    hass = MagicMock()
    coordinator = AtreaCoordinator(hass, make_mock_entry(), mock_modbus_client)

    data = await coordinator._async_update_data()

    assert data["temp_oda"] == 20.0   # 200 / 10
    assert data["temp_sup"] == 18.0   # 180 / 10
    assert data["temp_eta"] == 19.0   # 190 / 10
    assert data["temp_eha"] == 15.0   # 150 / 10
    assert data["temp_ida"] == 21.0   # 210 / 10
    assert data["power"] == 75.0
    assert data["mode"] == "Automatic"  # mode index 1


async def test_update_data_negative_temperature(mock_modbus_client):
    mock_modbus_client.read_input_registers.return_value.registers = [
        65436,  # -10.0°C
        180, 190, 150, 210,
    ]
    hass = MagicMock()
    coordinator = AtreaCoordinator(hass, make_mock_entry(), mock_modbus_client)

    data = await coordinator._async_update_data()

    assert data["temp_oda"] == pytest.approx(-10.0)  # (65436 - 65536) / 10


@pytest.mark.parametrize("failing_method, none_keys, ok_key", [
    (
        "read_input_registers",
        ["temp_oda", "temp_sup", "temp_eta", "temp_eha", "temp_ida"],
        "power",
    ),
    (
        "read_holding_registers",
        ["power", "mode"],
        "temp_oda",
    ),
])
async def test_update_data_batch_failure_isolates_affected_keys(
    mock_modbus_client, failing_method: str, none_keys: list[str], ok_key: str
):
    """A failure in one batch sets only its keys to None; the other batch still updates."""
    setattr(mock_modbus_client, failing_method, AsyncMock(side_effect=Exception("timeout")))
    hass = MagicMock()
    coordinator = AtreaCoordinator(hass, make_mock_entry(), mock_modbus_client)
    data = await coordinator._async_update_data()
    for k in none_keys:
        assert data[k] is None, f"Expected {k} to be None after {failing_method} failure"
    assert data[ok_key] is not None


async def test_update_data_all_batches_fail_raises_update_failed(mock_modbus_client):
    mock_modbus_client.read_input_registers = AsyncMock(side_effect=Exception("timeout"))
    mock_modbus_client.read_holding_registers = AsyncMock(side_effect=Exception("timeout"))
    hass = MagicMock()
    coordinator = AtreaCoordinator(hass, make_mock_entry(), mock_modbus_client)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_update_data_modbus_error_response(mock_modbus_client):
    """A Modbus error response (isError=True) counts as a batch failure."""
    error_response = MagicMock()
    error_response.isError.return_value = True
    mock_modbus_client.read_input_registers = AsyncMock(return_value=error_response)
    hass = MagicMock()
    coordinator = AtreaCoordinator(hass, make_mock_entry(), mock_modbus_client)

    data = await coordinator._async_update_data()

    assert data["temp_oda"] is None
    assert data["power"] == 75.0  # holding still OK


async def test_coordinator_stores_config_entry(mock_modbus_client):
    hass = MagicMock()
    entry = make_mock_entry()
    coordinator = AtreaCoordinator(hass, entry, mock_modbus_client)

    assert coordinator.config_entry is entry


async def test_coordinator_client_is_accessible(mock_modbus_client):
    hass = MagicMock()
    coordinator = AtreaCoordinator(hass, make_mock_entry(), mock_modbus_client)

    assert coordinator.client is mock_modbus_client
