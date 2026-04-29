"""Tests for Atrea RD5 config flow."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.atrea_rd5_modbus.config_flow import CannotConnect
from custom_components.atrea_rd5_modbus.const import DOMAIN


@pytest.fixture
def user_input():
    return {
        "host": "192.168.1.100",
        "port": 502,
        "unit_id": 1,
        "scan_interval": 30,
    }


async def test_config_flow_success(hass, user_input):
    with patch(
        "custom_components.atrea_rd5_modbus.config_flow.validate_connection",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            "atrea_rd5_modbus", context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Atrea RD5 (192.168.1.100)"
    assert result["data"] == user_input


async def test_config_flow_cannot_connect(hass, user_input):
    with patch(
        "custom_components.atrea_rd5_modbus.config_flow.validate_connection",
        side_effect=CannotConnect("timeout"),
    ):
        result = await hass.config_entries.flow.async_init(
            "atrea_rd5_modbus", context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"


async def test_config_flow_unknown_error(hass, user_input):
    """An unexpected exception maps to the 'unknown' error key."""
    with patch(
        "custom_components.atrea_rd5_modbus.config_flow.validate_connection",
        side_effect=RuntimeError("unexpected"),
    ):
        result = await hass.config_entries.flow.async_init(
            "atrea_rd5_modbus", context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "unknown"


async def test_config_flow_shows_form_on_init(hass):
    result = await hass.config_entries.flow.async_init(
        "atrea_rd5_modbus", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert "host" in result["data_schema"].schema


async def test_config_flow_aborts_on_duplicate(hass, user_input):
    """Test that adding the same host twice is rejected gracefully."""
    with patch(
        "custom_components.atrea_rd5_modbus.config_flow.validate_connection",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            "atrea_rd5_modbus", context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )

        result2 = await hass.config_entries.flow.async_init(
            "atrea_rd5_modbus", context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], user_input=user_input
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"


async def test_options_flow_shows_form_with_current_value(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.1.100", "port": 502, "unit_id": 1, "scan_interval": 30},
        options={"scan_interval": 45},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"


async def test_options_flow_saves_new_value(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.1.100", "port": 502, "unit_id": 1, "scan_interval": 30},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"scan_interval": 60}
    )

    assert result["type"] == "create_entry"
    assert entry.options == {"scan_interval": 60}


@pytest.mark.parametrize("invalid", [4, 0, -1, 301, 1000])
async def test_options_flow_rejects_out_of_range(hass, invalid: int):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.1.100", "port": 502, "unit_id": 1, "scan_interval": 30},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"scan_interval": invalid}
        )
