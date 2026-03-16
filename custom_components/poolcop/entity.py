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

    @staticmethod
    def is_component_installed(
        coordinator: PoolCopDataUpdateCoordinator, key: str
    ) -> bool:
        """Check if this entity's component is installed/enabled in PoolCop."""
        data = coordinator.data
        if data is None:
            return True

        equipments = data.equipments or {}

        if key == "ph_control" or key.startswith("ph_") or key == "pH":
            return bool(equipments.get("pH") or equipments.get("ph"))

        if key == "orp_control" or key.startswith("orp_"):
            return bool(equipments.get("orp") or equipments.get("ORP"))

        if key in {"ioniser", "ioniser_control"} or key.startswith("ioniser_"):
            return bool(equipments.get("ioniser"))

        if key == "autochlor_control" or key.startswith("autochlor_"):
            return bool(equipments.get("autochlor"))

        if key.startswith("waterlevel_") or key == "water_level":
            return data.state.water_level.installed

        if key == "temperature_air":
            return bool(equipments.get("air") or equipments.get("airTemperature"))

        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this PoolCop instance."""
        poolcop_id: str = cast(str, self.coordinator.config_entry.unique_id)
        data = self.coordinator.data

        # Use device nickname or pool nickname
        name = "PoolCop"
        if data:
            if data.device and data.device.nickname:
                name = data.device.nickname
            elif data.pool and data.pool.nickname:
                name = data.pool.nickname

        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, poolcop_id)},
            configuration_url="https://cloud.poolcop.net",
            manufacturer="PCFR",
            name=name,
        )
