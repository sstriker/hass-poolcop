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
        self._attr_entity_registry_enabled_default = self._is_component_enabled()

    def _is_component_enabled(self) -> bool:
        """Check if this entity's component is installed/enabled in PoolCop."""
        # Default to enabled
        key = self.entity_description.key

        # Check for specific components that might not be installed
        if key == "ph_control" or key.startswith("ph_") or key == "pH":
            return bool(self.coordinator.data.status_value("conf.pH"))

        if key == "orp_control" or key.startswith("orp_"):
            return bool(self.coordinator.data.status_value("conf.orp"))

        if key in {"ioniser", "ioniser_control"} or key.startswith("ioniser_"):
            return bool(self.coordinator.data.status_value("conf.ioniser"))

        if key == "autochlor_control" or key.startswith("autochlor_"):
            return bool(self.coordinator.data.status_value("conf.autochlor"))

        if key.startswith("waterlevel_") or key == "water_level":
            return bool(self.coordinator.data.status_value("conf.waterlevel"))

        # Check for temperature sensors
        if key == "temperature_air":
            return bool(self.coordinator.data.status_value("conf.airtemp"))

        if key == "temperature_water":
            return bool(self.coordinator.data.status_value("conf.watertemp"))

        if key in {"temperature_solar", "solar_temperature"}:
            return bool(self.coordinator.data.status_value("conf.solartemp"))

        # Pressure sensor
        if key == "pressure":
            return bool(self.coordinator.data.status_value("conf.pressure"))

        # Lighting control
        if key.startswith("light_") or key == "lighting_control":
            return bool(self.coordinator.data.status_value("conf.lighting"))

        # Auxiliary controls
        if key.startswith("aux_") or key == "auxiliary_control":
            aux_num = key.split("_")[1] if "_" in key else None
            if aux_num and aux_num.isdigit():
                return bool(self.coordinator.data.status_value(f"conf.aux{aux_num}"))

        # Solar heating
        if key.startswith("solar_") or key == "solar_control":
            return bool(self.coordinator.data.status_value("conf.solar"))

        # Enable all other entities by default
        return True

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
