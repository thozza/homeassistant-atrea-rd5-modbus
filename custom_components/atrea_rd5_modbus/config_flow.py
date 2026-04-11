"""Config flow for Atrea RD5 Modbus integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import HomeAssistantError
from pymodbus.client import AsyncModbusTcpClient

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SLAVE_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DOMAIN,
    REGISTER_MAP,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(int, vol.Range(min=1, max=65535)),
        vol.Optional(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): vol.All(int, vol.Range(min=1, max=247)),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(int, vol.Range(min=5)),
    }
)


async def validate_connection(host: str, port: int, slave_id: int) -> None:
    """Attempt a Modbus TCP connection and read one register to validate the device."""
    client = AsyncModbusTcpClient(host=host, port=port)
    try:
        await client.connect()
        if not client.connected:
            raise CannotConnect("Could not establish TCP connection to device")
        result = await client.read_holding_registers(address=REGISTER_MAP["mode"].address, count=1, slave=slave_id)
        if result.isError():
            raise CannotConnect("Device connected but returned a Modbus error")
    except CannotConnect:
        raise
    except Exception as err:
        raise CannotConnect(f"Unexpected error: {err}") from err
    finally:
        client.close()


class AtreaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Atrea RD5 Modbus."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.FlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()
            try:
                await validate_connection(
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_SLAVE_ID],
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during config flow validation")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Atrea RD5 ({user_input[CONF_HOST]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Raised when we cannot connect to the Atrea device."""
