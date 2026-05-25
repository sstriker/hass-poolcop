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

        equip = data.device.equipments_info

        if key == "ph_control" or key.startswith("ph_") or key == "pH":
            return equip.has_ph_sensor

        if key == "orp_control" or key.startswith("orp_") or key.startswith("disinfection_"):
            return equip.has_orp_sensor

        if key in {"ioniser", "ioniser_control"} or key.startswith("ioniser_"):
            return False  # Not exposed by client API

        if key == "autochlor_control" or key.startswith("autochlor_"):
            return False  # Not exposed by client API

        if key.startswith("waterlevel_") or key == "water_level":
            return equip.has_water_level_sensor

        if key == "temperature_air":
            return equip.has_air_temperature_sensor

        if key.startswith("pool_cover"):
            return equip.has_pool_cover

        if key.startswith("jet_stream"):
            return equip.has_jet_stream

        if key == "free_chlorine":
            return equip.has_fc_sensor

        if key == "total_chlorine":
            return equip.has_tc_sensor

        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this PoolCop instance."""
        poolcop_id: str = cast(str, self.coordinator.config_entry.unique_id)
        device = self.coordinator.data.device

        name = f"PoolCop {poolcop_id}"
        sw_version = device.version_info.poolcop_version or None
        model = device.version_info.model or None

        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, poolcop_id)},
            configuration_url="https://my.poolcop.com",
            manufacturer="PCFR",
            name=name,
            sw_version=sw_version,
            model=model,
        )
