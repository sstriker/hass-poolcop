"""Support for PoolCop binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aiopoolcop import AuxSettings
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory, EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ALARM_NAMES,
    AUX_FIXED_FUNCTION_LABELS,
    AUX_LABEL_ICONS,
    AUX_RELAY_LABELS,
    AUX_VALVE_LABELS,
    alert_display_name,
    aux_display_name,
    aux_label_id,
)
from .coordinator import PoolCopConfigEntry, PoolCopData, PoolCopDataUpdateCoordinator
from .entity import PoolCopEntity

# Coordinator-driven; no per-entity polling
PARALLEL_UPDATES = 0


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
    """Return alarm attributes with resolved names for all active alarms."""
    alarms = data.device.state.alarms
    if not alarms:
        return {"alarm_count": 0, "alarms": []}
    resolved = []
    for code in alarms:
        display = alert_display_name(code) if code.startswith("alert_title_") else code
        # Try to look up by alarm name string directly
        if not code.startswith("alert_title_"):
            # Code is a string like "FreezeRisk" or numeric string
            display = ALARM_NAMES.get(int(code), code) if code.isdigit() else code
        resolved.append({"code": code, "description": display})
    first = resolved[0] if resolved else {}
    return {
        "alarm_count": len(resolved),
        **first,
        "alarms": resolved,
    }


FILTER_CYCLE_ICONS = ("mdi:sync", "mdi:sync-off")
PUMP_ICONS = ("mdi:pump", "mdi:pump-off")
VALVE_ICONS = ("mdi:valve-open", "mdi:valve-closed")
INSTALLED_ICONS = ("mdi:check-circle-outline", "mdi:close-circle-outline")
BINARY_SENSORS = (
    # Running state binary sensors
    PoolCopBinarySensorEntityDescription(
        key="pump",
        translation_key="pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda data: (
            data.device.state.pumps[0].pump_state if data.device.state.pumps else False
        ),
        on_off_icons=PUMP_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="ph_control",
        translation_key="ph_control",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda data: data.device.state.ph_dosing,
        on_off_icons=PUMP_ICONS,
    ),
    PoolCopBinarySensorEntityDescription(
        key="orp_control",
        translation_key="orp_control",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda data: data.device.state.disinfection_dosing,
        on_off_icons=PUMP_ICONS,
    ),
    # Equipment installation status (connectivity)
    PoolCopBinarySensorEntityDescription(
        key="orp_installed",
        translation_key="orp_installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda data: data.device.equipments_info.has_orp_sensor,
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PoolCopBinarySensorEntityDescription(
        key="pH_installed",
        translation_key="ph_installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda data: data.device.equipments_info.has_ph_sensor,
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PoolCopBinarySensorEntityDescription(
        key="waterlevel_installed",
        translation_key="waterlevel_installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda data: data.device.equipments_info.has_water_level_sensor,
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PoolCopBinarySensorEntityDescription(
        key="air_installed",
        translation_key="air_installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda data: data.device.equipments_info.has_air_temperature_sensor,
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Special binary sensors
    PoolCopBinarySensorEntityDescription(
        key="active_alarm",
        translation_key="active_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda data: len(data.device.state.alarms) > 0,
        on_off_icons=("mdi:alert-circle", "mdi:check-circle"),
        extra_attrs_fn=_alarm_attrs,
    ),
    # Settings / diagnostic state binary sensors
    PoolCopBinarySensorEntityDescription(
        key="pool_freeze_protection",
        translation_key="pool_freeze_protection",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.device.settings.pool.freeze_protection,
        on_off_icons=("mdi:snowflake-alert", "mdi:snowflake-off"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="pool_service_mode",
        translation_key="pool_service_mode",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.device.state.service_mode,
        on_off_icons=("mdi:tools", "mdi:tools-off"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="pump_protect",
        translation_key="pump_protect",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: (
            data.device.settings.filtrations[0].pump_protection
            if data.device.settings.filtrations
            else False
        ),
        on_off_icons=("mdi:shield", "mdi:shield-off"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="ph_dosing",
        translation_key="ph_dosing",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.device.state.ph_dosing,
        on_off_icons=("mdi:flask", "mdi:flask-empty"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="disinfection_dosing",
        translation_key="disinfection_dosing",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.device.state.disinfection_dosing,
        on_off_icons=("mdi:flask", "mdi:flask-empty"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="waterlevel_auto_add",
        translation_key="waterlevel_auto_add",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.device.settings.water_level.can_refill,
        on_off_icons=("mdi:water-plus", "mdi:water-off"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="waterlevel_continuous",
        translation_key="waterlevel_continuous",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.device.settings.water_level.continuous_fill,
        on_off_icons=("mdi:water-sync", "mdi:water-off"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="waterlevel_auto_reduce",
        translation_key="waterlevel_auto_reduce",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.device.settings.water_level.can_reduce,
        on_off_icons=("mdi:water-minus", "mdi:water-off"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="waterlevel_on_target",
        translation_key="waterlevel_on_target",
        is_on_fn=lambda data: data.device.state.water_level.is_on_target,
        on_off_icons=("mdi:check-circle", "mdi:close-circle"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="waterlevel_on_error",
        translation_key="waterlevel_on_error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda data: data.device.state.water_level.is_on_error,
        on_off_icons=("mdi:alert-circle", "mdi:check-circle"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="waterlevel_refilling",
        translation_key="waterlevel_refilling",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda data: data.device.state.water_level.is_refilling,
        on_off_icons=("mdi:water-plus", "mdi:water-off"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="waterlevel_measuring",
        translation_key="waterlevel_measuring",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda data: data.device.state.water_level.is_measuring,
        on_off_icons=("mdi:ruler", "mdi:ruler"),
    ),
    # Pool cover state
    PoolCopBinarySensorEntityDescription(
        key="pool_cover_open",
        translation_key="pool_cover_open",
        device_class=BinarySensorDeviceClass.OPENING,
        is_on_fn=lambda data: data.device.state.pool_cover.is_open,
        on_off_icons=("mdi:window-shutter-open", "mdi:window-shutter"),
        extra_attrs_fn=lambda data: {
            "is_closing": data.device.state.pool_cover.is_closing,
            "is_opening": data.device.state.pool_cover.is_opening,
            "is_stopped": data.device.state.pool_cover.is_stopped,
            "controllable": data.device.state.pool_cover.controllable,
        },
    ),
    # Jet stream state
    PoolCopBinarySensorEntityDescription(
        key="jet_stream_running",
        translation_key="jet_stream_running",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda data: data.device.state.jet_stream.is_running,
        on_off_icons=("mdi:waves-arrow-right", "mdi:waves-arrow-right"),
    ),
    # Digital inputs
    PoolCopBinarySensorEntityDescription(
        key="input_1",
        translation_key="input_1",
        is_on_fn=lambda data: data.device.state.inputs.get("Input1", False),
        on_off_icons=("mdi:electric-switch-closed", "mdi:electric-switch"),
    ),
    PoolCopBinarySensorEntityDescription(
        key="input_2",
        translation_key="input_2",
        is_on_fn=lambda data: data.device.state.inputs.get("Input2", False),
        on_off_icons=("mdi:electric-switch-closed", "mdi:electric-switch"),
    ),
    # pH auto-adjust setting
    PoolCopBinarySensorEntityDescription(
        key="ph_auto_adjust",
        translation_key="ph_auto_adjust",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.device.settings.ph.auto_adjust,
        on_off_icons=("mdi:ph", "mdi:ph"),
    ),
    # Equipment inventory flags (always visible for diagnostics)
    PoolCopBinarySensorEntityDescription(
        key="equip_fac_sensor",
        translation_key="equip_fac_sensor",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda data: data.device.equipments_info.has_fac_sensor,
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PoolCopBinarySensorEntityDescription(
        key="equip_salt_sensor",
        translation_key="equip_salt_sensor",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda data: data.device.equipments_info.has_salt_sensor,
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PoolCopBinarySensorEntityDescription(
        key="equip_flow_meter",
        translation_key="equip_flow_meter",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda data: data.device.equipments_info.has_flow_meter,
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PoolCopBinarySensorEntityDescription(
        key="equip_energy_meter",
        translation_key="equip_energy_meter",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda data: data.device.equipments_info.has_energy_meter,
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PoolCopBinarySensorEntityDescription(
        key="equip_pool_cover",
        translation_key="equip_pool_cover",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda data: data.device.equipments_info.has_pool_cover,
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PoolCopBinarySensorEntityDescription(
        key="equip_jet_stream",
        translation_key="equip_jet_stream",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda data: data.device.equipments_info.has_jet_stream,
        on_off_icons=INSTALLED_ICONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolCopConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PoolCop binary sensors based on a config entry."""
    coordinator = entry.runtime_data

    entities: list[BinarySensorEntity] = [
        PoolCopBinarySensorEntity(coordinator=coordinator, description=description)
        for description in BINARY_SENSORS
        if PoolCopEntity.is_component_installed(coordinator, description.key)
    ]

    # Dynamic aux binary sensors for non-switchable or slaved aux ports
    for aux in coordinator.data.device.settings.auxs:
        if aux.is_reserved or aux.is_slave:
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
    """Binary sensor for a non-switchable PoolCop auxiliary input."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        coordinator: PoolCopDataUpdateCoordinator,
        aux: AuxSettings,
    ) -> None:
        """Initialize the aux binary sensor."""
        self._aux_channel: int = aux.aux_channel
        self._module: str = aux.module
        self._aux_id_str: str = f"Aux{aux.aux_channel}"
        api_label = aux.label or ""
        label = aux_display_name(api_label, aux.aux_channel)
        self._label_id = aux_label_id(api_label)
        lid = self._label_id

        # Fixed-function aux ports have first-class entity counterparts
        # -- show as "Label (Aux N)" and mark diagnostic
        if lid is not None and lid in AUX_FIXED_FUNCTION_LABELS:
            label = f"{label} (Aux {aux.aux_channel})"
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        super().__init__(
            coordinator=coordinator,
            description=EntityDescription(
                key=f"aux_{aux.aux_channel}",
                name=label,
            ),
        )

        # Valve-type aux ports: Open/Closed
        if lid is not None and lid in AUX_VALVE_LABELS:
            self._attr_device_class = BinarySensorDeviceClass.OPENING
        # Relay-type aux ports with first-class counterparts: On/Off
        elif lid is not None and lid in AUX_RELAY_LABELS:
            self._attr_device_class = BinarySensorDeviceClass.POWER

    @property
    def is_on(self) -> bool | None:
        """Return true if the aux input is active."""
        auxiliaries = self.coordinator.data.device.state.auxiliaries
        module_ports = auxiliaries.get(self._module)
        if module_ports is not None:
            return module_ports.get(self._aux_id_str)
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        for aux in self.coordinator.data.device.settings.auxs:
            if aux.aux_channel == self._aux_channel and aux.module == self._module:
                attrs: dict[str, Any] = {}
                if aux.is_slave:
                    attrs["slave"] = aux.slaved_to
                if aux.days_of_week:
                    attrs["days"] = aux.days_of_week
                if aux.label:
                    attrs["label"] = aux.label
                if aux.friendly_name:
                    attrs["friendly_name"] = aux.friendly_name
                if aux.mode:
                    attrs["mode"] = aux.mode
                return attrs
        return {}

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        if self._attr_device_class == BinarySensorDeviceClass.OPENING:
            return "mdi:valve-open" if self.is_on else "mdi:valve-closed"
        icons = (
            AUX_LABEL_ICONS.get(self._label_id) if self._label_id is not None else None
        )
        if icons:
            return icons[0] if self.is_on else icons[1]
        return "mdi:toggle-switch" if self.is_on else "mdi:toggle-switch-off"
