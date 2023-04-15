"""Support for PoolCop binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PoolCopData, PoolCopDataUpdateCoordinator
from .entity import PoolCopEntity


@dataclass
class PoolCopBinarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    is_on_fn: Callable[[PoolCopData], bool]
    on_off_icons: tuple[str, str]


@dataclass
class PoolCopBinarySensorEntityDescription(
    BinarySensorEntityDescription, PoolCopBinarySensorEntityDescriptionMixin
):
    """A class that describes PoolCop binary sensor entities."""


def _is_on_fn(path: str) -> Callable[[PoolCopData], bool]:
    """Return an is_on function for data at path."""

    def is_on_fn(data: PoolCopData) -> bool:
        return bool(data.status_value(path))

    return is_on_fn


FILTER_CYCLE_ICONS = ("mdi:sync", "mdi:sync-off")
PUMP_ICONS = ("mdi:pump", "mdi:pump-off")
VALVE_ICONS = ("mdi:valve-open", "mdi:valve-closed")
BINARY_SENSORS = (
    PoolCopBinarySensorEntityDescription(
        key="pump",
        name="Pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("status.pump"),
        on_off_icons=PUMP_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="watervalve",
        name="Watervalve",
        device_class=BinarySensorDeviceClass.OPENING,
        is_on_fn=_is_on_fn("status.watervalve"),
        on_off_icons=VALVE_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="ph_control",
        name="pH Pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("status.ph_control"),
        on_off_icons=PUMP_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="orp_control",
        name="Cl Pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("status.orp_control"),
        on_off_icons=PUMP_ICONS,
    ),
    #   "autochlor": 0,
    #   "ioniser": 0,
    PoolCopBinarySensorEntityDescription(
        key="aux1",
        name="aux 1",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("status.aux1"),
        on_off_icons=FILTER_CYCLE_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="aux2",
        name="aux 2",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("status.aux2"),
        on_off_icons=FILTER_CYCLE_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="aux3",
        name="aux 3",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("status.aux3"),
        on_off_icons=FILTER_CYCLE_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="aux4",
        name="aux 4",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("status.aux4"),
        on_off_icons=FILTER_CYCLE_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="aux5",
        name="aux 5",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("status.aux5"),
        on_off_icons=FILTER_CYCLE_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="aux6",
        name="aux 6",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("status.aux6"),
        on_off_icons=FILTER_CYCLE_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="orp_installed",
        name="ORP control installed",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("conf.orp"),
        on_off_icons=FILTER_CYCLE_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="pH_installed",
        name="pH control installed",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("conf.pH"),
        on_off_icons=FILTER_CYCLE_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="waterlevel_installed",
        name="Waterlevel control installed",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("conf.waterlevel"),
        on_off_icons=FILTER_CYCLE_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="ioniser_installed",
        name="Ioniser installed",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("conf.ioniser"),
        on_off_icons=FILTER_CYCLE_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="autochlor_installed",
        name="Autochlor installed",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("conf.autochlor"),
        on_off_icons=FILTER_CYCLE_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="air_installed",
        name="Air installed",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("conf.air"),
        on_off_icons=FILTER_CYCLE_ICONS,
    ),
    # PoolCopBinarySensorEntityDescription(
    #     key="filter_cycle_2",
    #     name="Filter2",
    #     device_class=BinarySensorDeviceClass.RUNNING,
    #     is_on_fn=lambda data: data.filter_cycle_2_running,
    #     on_off_icons=FILTER_CYCLE_ICONS,
    # ),
)

# "status": {

#   "forced": {
#   }


# CIRCULATION_PUMP_DESCRIPTION = PoolCopBinarySensorEntityDescription(
#     key="circulation_pump",
#     name="Circ Pump",
#     device_class=BinarySensorDeviceClass.RUNNING,
#     is_on_fn=lambda spa: (pump := spa.circulation_pump) is not None and pump.state > 0,
#     on_off_icons=("mdi:pump", "mdi:pump-off"),
# )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PoolCop sensors based on a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PoolCopBinarySensorEntity(coordinator=coordinator, description=description)
        for description in BINARY_SENSORS
    )


class PoolCopBinarySensorEntity(PoolCopEntity, BinarySensorEntity):
    """Representation of a PoolCop binary sensor entity."""

    entity_description: PoolCopBinarySensorEntityDescription

    def __init__(
        self,
        *,
        coordinator: PoolCopDataUpdateCoordinator,
        description: PoolCopBinarySensorEntityDescription,
    ) -> None:
        """Initialize a PoolCop binary sensor."""
        super().__init__(coordinator=coordinator, description=description)
        self.entity_id = f"{BINARY_SENSOR_DOMAIN}.{self._attr_unique_id}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        icons = self.entity_description.on_off_icons
        return icons[0] if self.is_on else icons[1]
