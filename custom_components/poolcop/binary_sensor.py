"""Support for PoolCop binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import AUX_FIXED_FUNCTION_LABELS, DOMAIN, aux_display_name, aux_label_id
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


def _watervalve_is_on(data: PoolCopData) -> bool:
    """Return true if the water valve is open."""
    return data.status_value("status.watervalve") == 1  # Refill


FILTER_CYCLE_ICONS = ("mdi:sync", "mdi:sync-off")
PUMP_ICONS = ("mdi:pump", "mdi:pump-off")
VALVE_ICONS = ("mdi:valve-open", "mdi:valve-closed")
INSTALLED_ICONS = ("mdi:check-circle-outline", "mdi:close-circle-outline")
BINARY_SENSORS = (
    # These binary sensors represent components that are always running when active
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
        is_on_fn=_watervalve_is_on,
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
    PoolCopBinarySensorEntityDescription(
        key="autochlor_control",
        name="Autochlor",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("status.autochlor"),
        on_off_icons=PUMP_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="ioniser_control",
        name="Ioniser",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_on_fn("status.ioniser"),
        on_off_icons=PUMP_ICONS,
    ),
    # These binary sensors represent equipment installation status (connectivity)
    PoolCopBinarySensorEntityDescription(
        key="orp_installed",
        name="ORP control installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=_is_on_fn("conf.orp"),
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PoolCopBinarySensorEntityDescription(
        key="pH_installed",
        name="pH control installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=_is_on_fn("conf.pH"),
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PoolCopBinarySensorEntityDescription(
        key="waterlevel_installed",
        name="Waterlevel control installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=_is_on_fn("conf.waterlevel"),
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PoolCopBinarySensorEntityDescription(
        key="ioniser_installed",
        name="Ioniser installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=_is_on_fn("conf.ioniser"),
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PoolCopBinarySensorEntityDescription(
        key="autochlor_installed",
        name="Autochlor installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=_is_on_fn("conf.autochlor"),
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PoolCopBinarySensorEntityDescription(
        key="air_installed",
        name="Air installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=_is_on_fn("conf.air"),
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Special binary sensors
    PoolCopBinarySensorEntityDescription(
        key="active_alarm",
        name="Active Alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda data: data.has_active_alarms(),
        on_off_icons=("mdi:alert-circle", "mdi:check-circle"),
    ),
    # These binary sensors represent settings control states
    PoolCopBinarySensorEntityDescription(
        key="pool_freeze_protection",
        name="Freeze Protection",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_on_fn("settings.pool.freeze_protection"),
        on_off_icons=("mdi:snowflake-alert", "mdi:snowflake-off"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="pool_service_mode",
        name="Service Mode",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_on_fn("settings.pool.service"),
        on_off_icons=("mdi:tools", "mdi:tools-off"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="pump_protect",
        name="Pump Protection",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_on_fn("settings.pump.protect"),
        on_off_icons=("mdi:shield", "mdi:shield-off"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="filter_waste_valve",
        name="Waste Valve",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_on_fn("settings.filter.waste_valve"),
        on_off_icons=("mdi:valve-open", "mdi:valve-closed"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="orp_control_enabled",
        name="ORP Control",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_on_fn("settings.orp.control"),
        on_off_icons=("mdi:toggle-switch", "mdi:toggle-switch-off"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="waterlevel_auto_add",
        name="Auto Water Add",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_on_fn("settings.waterlevel.auto_add"),
        on_off_icons=("mdi:water-plus", "mdi:water-off"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="waterlevel_continuous",
        name="Continuous Water Level",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_on_fn("settings.waterlevel.continuous"),
        on_off_icons=("mdi:water-sync", "mdi:water-off"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="waterlevel_auto_reduce",
        name="Auto Water Reduce",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_on_fn("settings.waterlevel.auto_reduce"),
        on_off_icons=("mdi:water-minus", "mdi:water-off"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="autochlor_auto",
        name="Autochlor Auto",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_on_fn("settings.autochlor.auto"),
        on_off_icons=("mdi:auto-fix", "mdi:auto-fix-off"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="autochlor_acid",
        name="Autochlor Acid",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_on_fn("settings.autochlor.acid"),
        on_off_icons=("mdi:flask", "mdi:flask-empty"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="ioniser_mode",
        name="Ioniser Mode",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_on_fn("settings.ioniser.mode"),
        on_off_icons=("mdi:lightning-bolt", "mdi:lightning-bolt-off"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PoolCop binary sensors based on a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BinarySensorEntity] = [
        PoolCopBinarySensorEntity(coordinator=coordinator, description=description)
        for description in BINARY_SENSORS
        if PoolCopEntity.is_component_installed(coordinator, description.key)
    ]

    # Dynamic aux binary sensors for non-switchable or slaved aux ports
    aux_list = coordinator.data.status_value("aux") or []
    for aux in aux_list:
        if not aux.get("switchable") or aux.get("slave"):
            entities.append(PoolCopAuxBinarySensor(coordinator, aux))

    async_add_entities(entities)


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

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        icons = self.entity_description.on_off_icons
        return icons[0] if self.is_on else icons[1]


class PoolCopAuxBinarySensor(PoolCopEntity, BinarySensorEntity):
    """Binary sensor for a non-switchable PoolCop auxiliary input."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        coordinator: PoolCopDataUpdateCoordinator,
        aux_data: dict,
    ) -> None:
        """Initialize the aux binary sensor."""
        from homeassistant.helpers.entity import EntityDescription

        self._aux_id: int = aux_data["id"]
        api_label = aux_data.get("label", "")
        label = aux_display_name(api_label, self._aux_id)
        lid = aux_label_id(api_label)

        super().__init__(
            coordinator=coordinator,
            description=EntityDescription(
                key=f"aux_{self._aux_id}",
                name=label,
            ),
        )

        # Fixed-function aux ports (Speed Control, Waste Valve, ORP Control)
        # have first-class entity counterparts — mark as diagnostic
        if lid is not None and lid in AUX_FIXED_FUNCTION_LABELS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool | None:
        """Return true if the aux input is active."""
        aux_list = self.coordinator.data.status_value("aux") or []
        for aux in aux_list:
            if aux.get("id") == self._aux_id:
                return bool(aux.get("status"))
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        aux_list = self.coordinator.data.status_value("aux") or []
        for aux in aux_list:
            if aux.get("id") == self._aux_id:
                attrs = {}
                if "slave" in aux:
                    attrs["slave"] = aux["slave"]
                if "days" in aux:
                    attrs["days"] = aux["days"]
                if "label" in aux:
                    attrs["label"] = aux["label"]
                return attrs
        return {}

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        return "mdi:toggle-switch" if self.is_on else "mdi:toggle-switch-off"
