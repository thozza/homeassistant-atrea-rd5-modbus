"""Config flow for Atrea RD5 Modbus integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import NumberSelector, NumberSelectorConfig, NumberSelectorMode
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
        vol.Optional(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): NumberSelector(
            NumberSelectorConfig(min=1, max=247, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(int, vol.Range(min=5)),
    }
)


async def validate_connection(host: str, port: int, slave_id: int) -> None:
    """Attempt a Modbus TCP connection and read one register to validate the device."""
    _LOGGER.debug("Validating connection to %s:%d (slave_id=%d)", host, port, slave_id)
    client = AsyncModbusTcpClient(host=host, port=port)
    try:
        await client.connect()
        if not client.connected:
            _LOGGER.debug("TCP connection to %s:%d failed — client not connected after connect()", host, port)
            raise CannotConnect("Could not establish TCP connection to device")
        _LOGGER.debug("TCP connection established; reading holding register %d", REGISTER_MAP["mode"].address)
        result = await client.read_holding_registers(address=REGISTER_MAP["mode"].address, count=1, device_id=slave_id)
        if result.isError():
            _LOGGER.debug(
                "Modbus error response from %s:%d (slave_id=%d) at address %d: %s",
                host,
                port,
                slave_id,
                REGISTER_MAP["mode"].address,
                result,
            )
            raise CannotConnect("Device connected but returned a Modbus error")
        _LOGGER.debug("Validation successful — device responded with register value %s", result.registers)
    except CannotConnect:
        raise
    except Exception as err:
        _LOGGER.debug("Unexpected exception during validation of %s:%d: %s", host, port, err, exc_info=True)
        raise CannotConnect(f"Unexpected error: {err}") from err
    finally:
        client.close()


class AtreaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Atrea RD5 Modbus."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> AtreaOptionsFlow:
        return AtreaOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.FlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_SLAVE_ID] = int(user_input[CONF_SLAVE_ID])
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()
            try:
                await validate_connection(
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_SLAVE_ID],
                )
            except CannotConnect as err:
                _LOGGER.warning("Connection validation failed for %s: %s", user_input[CONF_HOST], err)
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


class AtreaOptionsFlow(config_entries.OptionsFlow):
    """Edit post-setup options without re-validating the connection."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(int, vol.Range(min=5, max=300)),
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Raised when we cannot connect to the Atrea device."""
