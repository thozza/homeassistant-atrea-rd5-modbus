"""Select platform for Atrea RD5 Modbus integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, TIDA_SOURCE_OPTIONS, TODA_SOURCE_OPTIONS
from .coordinator import AtreaCoordinator


@dataclass(frozen=True, kw_only=True)
class AtreaSelectEntityDescription(SelectEntityDescription):
    """Select entity description that names the WRITE_REGISTER_MAP key."""

    write_key: str


SELECT_DESCRIPTIONS: tuple[AtreaSelectEntityDescription, ...] = (
    AtreaSelectEntityDescription(
        key="toda_source",
        name="T-ODA Source",
        write_key="toda_source",
        options=TODA_SOURCE_OPTIONS,
        entity_category=EntityCategory.CONFIG,
    ),
    AtreaSelectEntityDescription(
        key="tida_source",
        name="T-IDA Source",
        write_key="tida_source",
        options=TIDA_SOURCE_OPTIONS,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AtreaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(AtreaSelect(coordinator, desc) for desc in SELECT_DESCRIPTIONS)


class AtreaSelect(CoordinatorEntity[AtreaCoordinator], SelectEntity):
    """Select entity backed by a value in coordinator.data."""

    entity_description: AtreaSelectEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AtreaCoordinator,
        description: AtreaSelectEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.data.get(self.entity_description.key) is not None
        )

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_write(self.entity_description.write_key, option)
