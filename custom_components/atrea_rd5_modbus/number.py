"""Number platform for Atrea RD5 BMS temperature setpoints."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pymodbus.exceptions import ModbusException

from .const import DOMAIN
from .coordinator import AtreaCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AtreaNumberEntityDescription(NumberEntityDescription):
    """Number entity description that names the WRITE_REGISTER_MAP key."""

    write_key: str


NUMBER_DESCRIPTIONS: tuple[AtreaNumberEntityDescription, ...] = (
    AtreaNumberEntityDescription(
        key="bms_toda",
        name="BMS T-ODA Setpoint",
        write_key="bms_toda",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=-50.0,
        native_max_value=130.0,
        native_step=0.1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    AtreaNumberEntityDescription(
        key="bms_tida",
        name="BMS T-IDA Setpoint",
        write_key="bms_tida",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=-50.0,
        native_max_value=130.0,
        native_step=0.1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AtreaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(AtreaBmsNumber(coordinator, desc) for desc in NUMBER_DESCRIPTIONS)


class AtreaBmsNumber(RestoreNumber):
    """Write-only number entity that pushes the current value to the HVAC.

    The HVAC declares a sensor fault if a BMS-sourced temperature is not
    refreshed within 90 seconds. The user's automation is responsible for
    that cadence; this entity persists the last value so HA restarts don't
    open a gap longer than the watchdog.

    RestoreNumber is used instead of CoordinatorEntity because there is no
    read-back register for these setpoints — the HVAC treats them as
    write-only inputs. The coordinator reference is stored as _coordinator
    (private name prefix) because this class does not inherit the
    .coordinator property from CoordinatorEntity.
    """

    entity_description: AtreaNumberEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AtreaCoordinator,
        description: AtreaNumberEntityDescription,
    ) -> None:
        # Private name: RestoreNumber has no .coordinator property from CoordinatorEntity.
        self._coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info
        self._attr_native_value: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is None or last.native_value is None:
            return
        self._attr_native_value = float(last.native_value)
        try:
            await self._coordinator.async_write(self.entity_description.write_key, self._attr_native_value)
        except ModbusException as err:
            # Only swallow Modbus network errors — other errors (e.g. ValueError
            # from a corrupt restore value) should propagate.
            _LOGGER.warning(
                "Failed to push restored %s value %.1f °C on startup: %s",
                self.entity_description.key,
                self._attr_native_value,
                err,
            )

    async def async_set_native_value(self, value: float) -> None:
        await self._coordinator.async_write(self.entity_description.write_key, value)
        self._attr_native_value = value
        self.async_write_ha_state()
