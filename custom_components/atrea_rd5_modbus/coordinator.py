"""Data update coordinator for Atrea RD5 Modbus integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymodbus.exceptions import ModbusException

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SLAVE_ID,
    DOMAIN,
    REGISTER_MAP,
    BatchGroup,
    RegisterType,
    build_batch_groups,
)

if TYPE_CHECKING:
    from pymodbus.client import AsyncModbusTcpClient

_LOGGER = logging.getLogger(__name__)


class AtreaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches data from the Atrea RD5 via batched Modbus TCP reads."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: AsyncModbusTcpClient,
    ) -> None:
        self.client = client
        self._slave_id: int = entry.data[CONF_SLAVE_ID]
        self._batch_groups: list[BatchGroup] = build_batch_groups(REGISTER_MAP)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=entry.data[CONF_SCAN_INTERVAL]),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Atrea device using batched Modbus reads."""
        data: dict[str, Any] = {}
        failed = 0

        for group in self._batch_groups:
            try:
                if group.register_type == RegisterType.INPUT:
                    result = await self.client.read_input_registers(
                        address=group.start_address,
                        count=group.count,
                        device_id=self._slave_id,
                    )
                else:
                    result = await self.client.read_holding_registers(
                        address=group.start_address,
                        count=group.count,
                        device_id=self._slave_id,
                    )

                if result.isError():
                    raise ModbusException(f"Error response for batch at address {group.start_address}")

                for i, key in enumerate(group.keys):
                    data[key] = REGISTER_MAP[key].convert(result.registers[i])

            except Exception as err:
                _LOGGER.warning(
                    "Failed to read Modbus batch (type=%s, addr=%d, count=%d): %s",
                    group.register_type.value,
                    group.start_address,
                    group.count,
                    err,
                )
                failed += 1
                for key in group.keys:
                    data[key] = None

        if failed == len(self._batch_groups):
            raise UpdateFailed("All Modbus read batches failed — device unreachable")

        return data
