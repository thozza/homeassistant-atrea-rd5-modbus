"""Sensor platform for Atrea RD5 Modbus integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OPERATION_MODE_OPTIONS
from .coordinator import AtreaCoordinator


@dataclass(frozen=True)
class AtreaSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description for Atrea RD5."""


SENSOR_DESCRIPTIONS: tuple[AtreaSensorEntityDescription, ...] = (
    AtreaSensorEntityDescription(
        key="temp_oda",
        name="T-ODA Outdoor Air",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AtreaSensorEntityDescription(
        key="temp_sup",
        name="T-SUP Supply Air",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AtreaSensorEntityDescription(
        key="temp_eta",
        name="T-ETA Extract Air",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AtreaSensorEntityDescription(
        key="temp_eha",
        name="T-EHA Exhaust Air",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AtreaSensorEntityDescription(
        key="temp_ida",
        name="T-IDA Indoor Air",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AtreaSensorEntityDescription(
        key="power",
        name="Ventilation Power",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AtreaSensorEntityDescription(
        key="mode",
        name="Ventilation Mode",
        device_class=SensorDeviceClass.ENUM,
        options=OPERATION_MODE_OPTIONS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Atrea RD5 sensor entities from a config entry."""
    coordinator: AtreaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(AtreaSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS)


class AtreaSensor(CoordinatorEntity[AtreaCoordinator], SensorEntity):
    """A sensor entity backed by the Atrea coordinator."""

    entity_description: AtreaSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AtreaCoordinator,
        description: AtreaSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": f"Atrea RD5 @ {coordinator.config_entry.data['host']}",
            "manufacturer": "Atrea",
            "model": "RD5",
        }

    @property
    def native_value(self) -> float | str | None:
        """Return the current sensor value from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def available(self) -> bool:
        """Return True if the entity has a valid value."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.data.get(self.entity_description.key) is not None
        )
