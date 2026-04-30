"""Tests for AtreaCoordinator batch read logic."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed
from pymodbus.exceptions import ModbusException

from custom_components.atrea_rd5_modbus.coordinator import AtreaCoordinator


def make_mock_entry(data: dict | None = None):
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = data or {
        "host": "192.168.1.100",
        "port": 502,
        "unit_id": 1,
        "scan_interval": 30,
    }
    entry.options = {}
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
    assert data["season"] == "Heating"       # register 0 → "Heating"
    assert data["season_switch"] == "TS"     # register 0 → "TS"
    assert data["season_temp_thr"] == 15.0   # register 150 / 10


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
        ["power", "mode", "tida_source", "season", "season_switch", "season_temp_thr"],
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
    mock_modbus_client.read_coils = AsyncMock(side_effect=Exception("timeout"))
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


async def test_update_data_includes_coil_and_extra_holding(mock_modbus_client):
    """COIL reads expose `result.bits`; the coordinator normalises and converts."""
    hass = MagicMock()
    coordinator = AtreaCoordinator(hass, make_mock_entry(), mock_modbus_client)

    data = await coordinator._async_update_data()

    assert data["toda_source"] == "BMS"   # bits[0] == True -> 1
    assert data["tida_source"] == "BMS"   # holding_response_tida_source.registers == [3]


async def test_update_data_coil_failure_isolated(mock_modbus_client):
    """A coil-batch failure nulls only its keys, leaving other batches intact."""
    mock_modbus_client.read_coils = AsyncMock(side_effect=Exception("timeout"))
    hass = MagicMock()
    coordinator = AtreaCoordinator(hass, make_mock_entry(), mock_modbus_client)

    data = await coordinator._async_update_data()

    assert data["toda_source"] is None
    assert data["temp_oda"] == 20.0
    assert data["tida_source"] == "BMS"
    assert data["power"] == 75.0


async def test_async_write_holding_register(hass, mock_modbus_client):
    """Writing a temperature setpoint encodes via signed10 and uses write_register."""
    coordinator = AtreaCoordinator(hass, make_mock_entry(), mock_modbus_client)
    coordinator.async_request_refresh = AsyncMock()

    await coordinator.async_write("bms_toda", 21.5)

    mock_modbus_client.write_register.assert_awaited_once_with(
        address=10213, value=215, device_id=1,
    )
    mock_modbus_client.write_coil.assert_not_called()


async def test_async_write_coil(hass, mock_modbus_client):
    """Writing the T-ODA source uses write_coil with a bool."""
    coordinator = AtreaCoordinator(hass, make_mock_entry(), mock_modbus_client)
    coordinator.async_request_refresh = AsyncMock()

    await coordinator.async_write("toda_source", "BMS")

    mock_modbus_client.write_coil.assert_awaited_once_with(
        address=10510, value=True, device_id=1,
    )
    mock_modbus_client.write_register.assert_not_called()


async def test_async_write_holding_for_tida_source(hass, mock_modbus_client):
    """Writing T-IDA source uses write_register with the encoded int."""
    coordinator = AtreaCoordinator(hass, make_mock_entry(), mock_modbus_client)
    coordinator.async_request_refresh = AsyncMock()

    await coordinator.async_write("tida_source", "TRKn")

    mock_modbus_client.write_register.assert_awaited_once_with(
        address=10514, value=2, device_id=1,
    )


async def test_async_write_raises_on_error_response(hass, mock_modbus_client):
    error_response = MagicMock()
    error_response.isError.return_value = True
    mock_modbus_client.write_register = AsyncMock(return_value=error_response)
    coordinator = AtreaCoordinator(hass, make_mock_entry(), mock_modbus_client)

    with pytest.raises(ModbusException):
        await coordinator.async_write("bms_toda", 20.0)


async def test_async_write_unknown_key_raises_keyerror(hass, mock_modbus_client):
    coordinator = AtreaCoordinator(hass, make_mock_entry(), mock_modbus_client)

    with pytest.raises(KeyError):
        await coordinator.async_write("does_not_exist", 1)


def test_coordinator_device_info(mock_modbus_client):
    hass = MagicMock()
    coordinator = AtreaCoordinator(hass, make_mock_entry(), mock_modbus_client)

    info = coordinator.device_info
    assert info["manufacturer"] == "Atrea"
    assert info["model"] == "RD5"
    assert info["name"] == "Atrea RD5 @ 192.168.1.100"
    assert info["identifiers"] == {("atrea_rd5_modbus", coordinator.config_entry.entry_id)}


async def test_scan_interval_uses_options_when_set(mock_modbus_client):
    """Options take precedence over entry.data for scan_interval."""
    hass = MagicMock()
    entry = make_mock_entry()
    entry.options = {"scan_interval": 15}
    coordinator = AtreaCoordinator(hass, entry, mock_modbus_client)
    assert coordinator.update_interval.total_seconds() == 15


async def test_scan_interval_falls_back_to_data(mock_modbus_client):
    """When options is empty, scan_interval comes from entry.data."""
    hass = MagicMock()
    entry = make_mock_entry()
    entry.options = {}
    coordinator = AtreaCoordinator(hass, entry, mock_modbus_client)
    assert coordinator.update_interval.total_seconds() == 30


async def test_scan_interval_options_none_falls_back_to_data(mock_modbus_client):
    """A None value in options is treated as absent — falls back to entry.data."""
    hass = MagicMock()
    entry = make_mock_entry()
    entry.options = {"scan_interval": None}
    coordinator = AtreaCoordinator(hass, entry, mock_modbus_client)
    assert coordinator.update_interval.total_seconds() == 30
