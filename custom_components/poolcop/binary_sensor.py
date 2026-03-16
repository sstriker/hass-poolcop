"""Support for PoolCop binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import AUX_LABEL_ICONS, DOMAIN
from .coordinator import PoolCopData, PoolCopDataUpdateCoordinator
from .entity import PoolCopEntity


@dataclass(frozen=True)
class PoolCopBinarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    is_on_fn: Callable[[PoolCopData], bool]
    on_off_icons: tuple[str, str]


@dataclass(frozen=True)
class PoolCopBinarySensorEntityDescription(
    BinarySensorEntityDescription, PoolCopBinarySensorEntityDescriptionMixin
):
    """A class that describes PoolCop binary sensor entities."""

    extra_attrs_fn: Callable[[PoolCopData], dict[str, Any]] | None = None


def _alarm_attrs(data: PoolCopData) -> dict[str, Any]:
    """Return alarm attributes for active alarms."""
    active = [a for a in data.alarms if a.is_active]
    if not active:
        return {"alarm_count": 0, "alarms": []}
    resolved = [
        {
            "code": a.code,
            "description": a.label or a.description or a.code,
            "severity": a.severity,
            "start_date": a.start_date,
        }
        for a in active
    ]
    return {
        "alarm_count": len(resolved),
        **resolved[0],
        "alarms": resolved,
    }


PUMP_ICONS = ("mdi:pump", "mdi:pump-off")
VALVE_ICONS = ("mdi:valve-open", "mdi:valve-closed")
INSTALLED_ICONS = ("mdi:check-circle-outline", "mdi:close-circle-outline")

BINARY_SENSORS = (
    PoolCopBinarySensorEntityDescription(
        key="pump",
        name="Pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda data: data.pump.pump_state if data.pump else False,
        on_off_icons=PUMP_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="mains_power",
        name="Mains Power",
        device_class=BinarySensorDeviceClass.POWER,
        is_on_fn=lambda data: not data.state.mains_power_lost,
        on_off_icons=("mdi:power-plug", "mdi:power-plug-off"),
    ),
    # Equipment installation status
    PoolCopBinarySensorEntityDescription(
        key="waterlevel_installed",
        name="Waterlevel control installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda data: data.state.water_level.installed,
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Active alarm
    PoolCopBinarySensorEntityDescription(
        key="active_alarm",
        name="Active Alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda data: data.has_active_alarms(),
        on_off_icons=("mdi:alert-circle", "mdi:check-circle"),
        extra_attrs_fn=_alarm_attrs,
    ),
    # Device connectivity
    PoolCopBinarySensorEntityDescription(
        key="device_connected",
        name="Device Connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda data: data.device.is_connected,
        on_off_icons=("mdi:cloud-check", "mdi:cloud-off-outline"),
        entity_category=EntityCategory.DIAGNOSTIC,
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

    # Dynamic aux binary sensors from auxiliaries list
    for aux in coordinator.data.auxiliaries:
        if aux.is_reserved:
            continue
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
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if self.entity_description.extra_attrs_fn:
            return self.entity_description.extra_attrs_fn(self.coordinator.data)
        return None

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        icons = self.entity_description.on_off_icons
        return icons[0] if self.is_on else icons[1]


class PoolCopAuxBinarySensor(PoolCopEntity, BinarySensorEntity):  # type: ignore[misc]
    """Binary sensor for a PoolCop auxiliary."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        coordinator: PoolCopDataUpdateCoordinator,
        aux,
    ) -> None:
        """Initialize the aux binary sensor."""
        self._module_id = aux.module_id
        self._aux_channel = aux.aux_channel
        label = (
            aux.friendly_name or aux.label or f"Aux {aux.module_id}/{aux.aux_channel}"
        )
        self._label = aux.label

        super().__init__(
            coordinator=coordinator,
            description=EntityDescription(
                key=f"aux_{aux.module_id}_{aux.aux_channel}",
                name=label,
            ),
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the aux is active."""
        # Check auxiliaries dict in state
        state_auxes = self.coordinator.data.state.auxiliaries
        module_key = f"AuxModule{self._module_id}"
        aux_key = f"Aux{self._aux_channel}"
        if module_key in state_auxes and aux_key in state_auxes[module_key]:
            return state_auxes[module_key][aux_key]
        # Fall back to the aux config status
        for aux in self.coordinator.data.auxiliaries:
            if (
                aux.module_id == self._module_id
                and aux.aux_channel == self._aux_channel
            ):
                return aux.status
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        for aux in self.coordinator.data.auxiliaries:
            if (
                aux.module_id == self._module_id
                and aux.aux_channel == self._aux_channel
            ):
                attrs: dict[str, Any] = {}
                if aux.mode:
                    attrs["mode"] = aux.mode
                if aux.label:
                    attrs["label"] = aux.label
                if aux.has_timer:
                    attrs["has_timer"] = aux.has_timer
                if aux.is_heating:
                    attrs["is_heating"] = aux.is_heating
                    if aux.heating_set_point is not None:
                        attrs["heating_set_point"] = aux.heating_set_point
                return attrs
        return {}

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        icons = AUX_LABEL_ICONS.get(self._label or "")
        if icons:
            return icons[0] if self.is_on else icons[1]
        return "mdi:toggle-switch" if self.is_on else "mdi:toggle-switch-off"
