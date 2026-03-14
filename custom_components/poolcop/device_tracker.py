"""Support for PoolCop device tracker."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PoolCopDataUpdateCoordinator
from .entity import PoolCopEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PoolCop device tracker based on a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    pool_data = coordinator.data.status_value("", prefix="Pool") or {}
    if not isinstance(pool_data, dict):
        return

    lat = pool_data.get("latitude")
    lon = pool_data.get("longitude")
    if lat is None or lon is None:
        return

    try:
        float(lat)
        float(lon)
    except ValueError, TypeError:
        return

    async_add_entities([PoolCopTracker(coordinator, pool_data)])


class PoolCopTracker(PoolCopEntity, TrackerEntity):  # type: ignore[misc]
    """Representation of a PoolCop pool location."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PoolCopDataUpdateCoordinator,
        pool_data: dict,
    ) -> None:
        """Initialize the pool tracker."""
        super().__init__(
            coordinator=coordinator,
            description=EntityDescription(key="pool_location", name="Pool"),
        )
        self._latitude = float(pool_data["latitude"])
        self._longitude = float(pool_data["longitude"])

        image = pool_data.get("image")
        if image:
            self._attr_entity_picture = image

    @property
    def latitude(self) -> float:
        """Return latitude of the pool."""
        return self._latitude

    @property
    def longitude(self) -> float:
        """Return longitude of the pool."""
        return self._longitude

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:pool"

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return extra state attributes."""
        pool_data = self.coordinator.data.status_value("", prefix="Pool") or {}
        if not isinstance(pool_data, dict):
            return {}
        attrs = {}
        if pool_data.get("timezone"):
            attrs["timezone"] = pool_data["timezone"]
        if pool_data.get("nickname"):
            attrs["nickname"] = pool_data["nickname"]
        return attrs
