"""Shared fixtures for Atrea RD5 Modbus integration tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the tests directory."""
    yield


@pytest.fixture
def mock_modbus_client():
    """Return a mocked AsyncModbusTcpClient."""
    client = MagicMock()
    client.connected = True
    client.connect = AsyncMock(return_value=True)
    client.close = MagicMock()

    input_response = MagicMock()
    input_response.isError.return_value = False
    # T-ODA=20.0, T-SUP=18.0, T-ETA=19.0, T-EHA=15.0, T-IDA=21.0
    input_response.registers = [200, 180, 190, 150, 210]

    holding_response = MagicMock()
    holding_response.isError.return_value = False
    # power=75, mode=1 (Automatic)
    holding_response.registers = [75, 1]

    client.read_input_registers = AsyncMock(return_value=input_response)
    client.read_holding_registers = AsyncMock(return_value=holding_response)

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
