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
        """Check if this entity's component is installed/enabled in PoolCop.

        Used by platform setup functions to skip entity creation entirely
        for uninstalled components.
        """
        if key == "ph_control" or key.startswith("ph_") or key == "pH":
            return bool(coordinator.data.status_value("conf.pH"))

        if key == "orp_control" or key.startswith("orp_"):
            return bool(coordinator.data.status_value("conf.orp"))

        if key in {"ioniser", "ioniser_control"} or key.startswith("ioniser_"):
            return bool(coordinator.data.status_value("conf.ioniser"))

        if key == "autochlor_control" or key.startswith("autochlor_"):
            return bool(coordinator.data.status_value("conf.autochlor"))

        if key.startswith("waterlevel_") or key == "water_level":
            return bool(coordinator.data.status_value("conf.waterlevel"))

        if key == "temperature_air":
            return bool(coordinator.data.status_value("conf.air"))

        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this PoolCop instance."""
        poolcop_id: str = cast(str, self.coordinator.config_entry.unique_id)

        # Use Pool nickname if available, fall back to "PoolCop"
        pool_data = self.coordinator.data.status_value("", prefix="Pool") or {}
        nickname = pool_data.get("nickname") if isinstance(pool_data, dict) else None
        name = nickname or "PoolCop"

        info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    poolcop_id,
                )
            },
            configuration_url=f"https://poolcopilot.com/mypoolcop/select/{poolcop_id}",
            manufacturer="PCFR",
            name=name,
            sw_version=self.coordinator.data.status_value("network.version"),
        )

        return info
