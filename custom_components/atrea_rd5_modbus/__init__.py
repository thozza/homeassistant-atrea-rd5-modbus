"""Atrea RD5 Modbus — Home Assistant integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from pymodbus.client import AsyncModbusTcpClient

from .const import DOMAIN
from .coordinator import AtreaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SELECT, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Atrea RD5 Modbus from a config entry."""
    client = AsyncModbusTcpClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
    )

    try:
        await client.connect()
        if not client.connected:
            client.close()
            raise ConfigEntryNotReady(f"Could not connect to Atrea device at {entry.data[CONF_HOST]}")
    except ConfigEntryNotReady:
        raise
    except Exception as err:
        client.close()
        raise ConfigEntryNotReady(f"Failed to connect to Atrea device: {err}") from err

    coordinator = AtreaCoordinator(hass, entry, client)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        client.close()
        raise ConfigEntryNotReady(f"Initial data fetch failed: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if entry.entry_id in hass.data.get(DOMAIN, {}):
        coordinator: AtreaCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.client.close()
    return unload_ok
