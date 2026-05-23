"""Support for PoolCop geo location."""

from __future__ import annotations

import math
from typing import Any, cast

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MAP_MODE, DOMAIN, MAP_MODE_ATTENTION
from .coordinator import PoolCopDataUpdateCoordinator
from .entity import PoolCopEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PoolCop geo location based on a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    pool = coordinator.data.pool
    if pool is None:
        return

    lat = pool.latitude
    lon = pool.longitude
    if lat is None or lon is None:
        return

    try:
        float(lat)
        float(lon)
    except (ValueError, TypeError):
        return

    async_add_entities([PoolCopGeoLocation(coordinator)])


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in km between two points."""
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class PoolCopGeoLocation(PoolCopEntity, GeolocationEvent):
    """Representation of a PoolCop pool location on the map."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PoolCopDataUpdateCoordinator,
    ) -> None:
        """Initialize the pool geo location."""
        super().__init__(
            coordinator=coordinator,
            description=EntityDescription(key="pool_location", name="Pool"),
        )
        pool = coordinator.data.pool
        self._pool_lat = float(pool.latitude)  # type: ignore[arg-type]
        self._pool_lon = float(pool.longitude)  # type: ignore[arg-type]

        if pool.nickname:
            self._attr_name = pool.nickname

    @property
    def source(self) -> str:
        """Return source for geo_location grouping."""
        return "poolcop"

    @property
    def suggested_object_id(self) -> str:
        """Return a stable object id."""
        poolcop_id = cast(str, self.coordinator.config_entry.unique_id)
        return f"poolcop_{poolcop_id}"

    @property
    def _should_show(self) -> bool:
        """Return True if the entity should show on the map."""
        map_mode = self.coordinator.config_entry.options.get(CONF_MAP_MODE, "always")
        if map_mode == MAP_MODE_ATTENTION:
            alarms = self.coordinator.data.device.state.alarms
            return len(alarms) > 0
        return True

    @property
    def latitude(self) -> float | None:
        """Return latitude of the pool."""
        return self._pool_lat if self._should_show else None

    @property
    def longitude(self) -> float | None:
        """Return longitude of the pool."""
        return self._pool_lon if self._should_show else None

    @property
    def distance(self) -> float | None:
        """Return distance from HA home zone in km."""
        if not self._should_show:
            return None
        home_lat = self.hass.config.latitude
        home_lon = self.hass.config.longitude
        if home_lat is None or home_lon is None:
            return None
        return round(
            _haversine_km(home_lat, home_lon, self._pool_lat, self._pool_lon), 1
        )

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:pool"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        pool = self.coordinator.data.pool
        attrs: dict[str, Any] = {}
        if pool is not None:
            if pool.timezone:
                attrs["timezone"] = pool.timezone
            if pool.nickname:
                attrs["nickname"] = pool.nickname
        alarms = self.coordinator.data.device.state.alarms
        attrs["alarm_count"] = len(alarms)
        return attrs
