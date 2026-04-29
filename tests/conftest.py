"""Shared fixtures for Atrea RD5 Modbus integration tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymodbus.client import AsyncModbusTcpClient

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Prevent async_setup_entry from making real network calls during tests."""
    with patch(
        "custom_components.atrea_rd5_modbus.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the tests directory."""
    yield


@pytest.fixture
def mock_modbus_client():
    """Return a mocked AsyncModbusTcpClient with read + write defaults."""
    client = MagicMock()
    client.connected = True
    client.connect = AsyncMock(return_value=True)
    client.close = MagicMock()

    input_response = MagicMock()
    input_response.isError.return_value = False
    # T-ODA=20.0, T-SUP=18.0, T-ETA=19.0, T-EHA=15.0, T-IDA=21.0
    input_response.registers = [200, 180, 190, 150, 210]

    holding_response_main = MagicMock()
    holding_response_main.isError.return_value = False
    # power=75, mode=1 (Automatic)
    holding_response_main.registers = [75, 1]

    holding_response_tida_source = MagicMock()
    holding_response_tida_source.isError.return_value = False
    # tida_source=3 (BMS)
    holding_response_tida_source.registers = [3]

    coil_response = MagicMock()
    coil_response.isError.return_value = False
    # toda_source=1 (BMS); pymodbus pads bits to a multiple of 8
    coil_response.bits = [True, False, False, False, False, False, False, False]

    def read_holding_side_effect(*, address: int, count: int, **_kw):
        if address == 10704:
            return holding_response_main
        if address == 10514:
            return holding_response_tida_source
        raise AssertionError(f"Unexpected holding read at {address}")

    write_response = MagicMock()
    write_response.isError.return_value = False

    # spec= enforces the real pymodbus signature so wrong kwargs raise TypeError in tests just as in production.
    client.read_input_registers = AsyncMock(
        spec=AsyncModbusTcpClient.read_input_registers,
        return_value=input_response,
    )
    client.read_holding_registers = AsyncMock(
        spec=AsyncModbusTcpClient.read_holding_registers,
        side_effect=read_holding_side_effect,
    )
    client.read_coils = AsyncMock(
        spec=AsyncModbusTcpClient.read_coils,
        return_value=coil_response,
    )
    # Write mocks intentionally omit spec=: on Python 3.14, unittest.mock's
    # _call_matcher raises "missing a required argument: 'self'" against an
    # unbound-method spec when assert_awaited_once_with checks pass-through
    # kwargs. Read mocks above are unaffected because their tests don't use
    # assert_awaited_once_with.
    client.write_register = AsyncMock(return_value=write_response)
    client.write_coil = AsyncMock(return_value=write_response)

    return client


@pytest.fixture
def mock_config_entry_data():
    """Return standard config entry data."""
    return {
        "host": "192.168.1.100",
        "port": 502,
        "slave_id": 1,
        "scan_interval": 30,
    }
