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

    pool = coordinator.data.pool
    if pool is None:
        return

    if pool.latitude is None or pool.longitude is None:
        return

    nickname = pool.nickname
    async_add_entities([PoolCopTracker(coordinator, nickname)])


class PoolCopTracker(PoolCopEntity, TrackerEntity):  # type: ignore[misc]
    """Representation of a PoolCop pool location."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PoolCopDataUpdateCoordinator,
        nickname: str | None = None,
    ) -> None:
        """Initialize the pool tracker."""
        super().__init__(
            coordinator=coordinator,
            description=EntityDescription(key="pool_location", name="Pool"),
        )
        if nickname:
            self._attr_name = nickname

    @property
    def suggested_object_id(self) -> str:
        """Return a stable object id independent of the display name."""
        return "pool"

    @property
    def latitude(self) -> float | None:
        """Return latitude of the pool."""
        pool = self.coordinator.data.pool
        return pool.latitude if pool else None

    @property
    def longitude(self) -> float | None:
        """Return longitude of the pool."""
        pool = self.coordinator.data.pool
        return pool.longitude if pool else None

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
        pool = self.coordinator.data.pool
        if not pool:
            return {}
        attrs: dict[str, str | None] = {}
        if pool.timezone:
            attrs["timezone"] = pool.timezone
        if pool.nickname:
            attrs["nickname"] = pool.nickname
        if pool.city:
            attrs["city"] = pool.city
        return attrs
