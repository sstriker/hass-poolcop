"""PoolCop base entity."""
from __future__ import annotations

from typing import cast

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PoolCopDataUpdateCoordinator


class PoolCopEntity(CoordinatorEntity[PoolCopDataUpdateCoordinator]):
    """Defines a base PoolCop Home entity."""

    _attr_has_entity_name = True
    _attr_available = True
    entity_description: EntityDescription

    def __init__(
        self,
        *,
        coordinator: PoolCopDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the PoolCop entity."""
        super().__init__(coordinator=coordinator)
        poolcop_id = coordinator.config_entry.unique_id
        self._attr_unique_id = f"{DOMAIN}_{poolcop_id}_{description.key}"
        self.entity_description = description

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this PoolCop instance."""
        poolcop_id: str = cast(str, self.coordinator.config_entry.unique_id)

        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    poolcop_id,
                )
            },
            configuration_url=f"https://poolcopilot.com/mypoolcop/select/{poolcop_id}",
            manufacturer="PCFR",
            name="PoolCop",
            sw_version=self.coordinator.data.status_value("network.version"),
        )
