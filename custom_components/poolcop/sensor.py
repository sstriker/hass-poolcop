"""Support for PoolCop sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CYCLE_ACTIVE_MODES, DOMAIN, VALVE_POSITIONS
from .coordinator import PoolCopData, PoolCopDataUpdateCoordinator
from .entity import PoolCopEntity


@dataclass(frozen=True)
class PoolCopSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[PoolCopData], str | int | float | datetime | None]


@dataclass(frozen=True)
class PoolCopSensorEntityDescription(
    SensorEntityDescription, PoolCopSensorEntityDescriptionMixin
):
    """Describes PoolCop sensor entity."""

    extra_attrs_fn: Callable[[PoolCopData], dict[str, Any]] | None = None
    available_fn: Callable[[PoolCopData], bool] | None = None


def _is_cycle_mode(data: PoolCopData) -> bool:
    """Return True if the current operating mode uses filtration cycles."""
    return data.state.status in CYCLE_ACTIVE_MODES


def _cycle_time_remaining_fn(data: PoolCopData) -> float | None:
    """Get remaining time in seconds for the current cycle."""
    if not _is_cycle_mode(data):
        return None
    if data.cycle_status and data.cycle_status.get("remaining_time") is not None:
        return data.cycle_status["remaining_time"]
    return None


def _cycle_end_time_fn(data: PoolCopData) -> datetime | None:
    """Get predicted end time for the current cycle."""
    if not _is_cycle_mode(data):
        return None
    if data.cycle_status and data.cycle_status.get("predicted_end") is not None:
        timestamp = data.cycle_status["predicted_end"]
        return datetime.fromtimestamp(timestamp)
    return None


def _cycle_elapsed_time_fn(data: PoolCopData) -> float | None:
    """Get elapsed time in seconds for the current cycle."""
    if not _is_cycle_mode(data):
        return None
    if data.cycle_status and data.cycle_status.get("elapsed_time") is not None:
        return data.cycle_status["elapsed_time"]
    return None


SENSORS: tuple[PoolCopSensorEntityDescription, ...] = (
    PoolCopSensorEntityDescription(
        key="temperature_water",
        name="Water temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.state.water_temperature,
    ),
    PoolCopSensorEntityDescription(
        key="temperature_air",
        name="Air temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.state.air_temperature,
    ),
    PoolCopSensorEntityDescription(
        key="pressure",
        name="Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.KPA,
        value_fn=lambda data: data.pump.pressure if data.pump else None,
    ),
    PoolCopSensorEntityDescription(
        key="pH",
        name="pH",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="pH",
        value_fn=lambda data: data.state.ph,
    ),
    PoolCopSensorEntityDescription(
        key="orp",
        name="Oxidation-Reduction Potential",
        icon="mdi:molecule",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mV",
        value_fn=lambda data: data.state.orp,
    ),
    PoolCopSensorEntityDescription(
        key="voltage",
        name="Battery Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: data.state.battery_voltage,
    ),
    PoolCopSensorEntityDescription(
        key="mains_voltage",
        name="Mains Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.state.mains_voltage,
    ),
    PoolCopSensorEntityDescription(
        key="water_level",
        name="Water level",
        icon="mdi:waves",
        device_class=SensorDeviceClass.ENUM,
        options=["Faulty", "Low", "Normal", "High", "Very High"],
        value_fn=lambda data: data.state.water_level.state,
    ),
    PoolCopSensorEntityDescription(
        key="valve_position",
        name="Valve position",
        icon="mdi:valve",
        device_class=SensorDeviceClass.ENUM,
        options=VALVE_POSITIONS,
        value_fn=lambda data: data.pump.valve_position if data.pump else None,
    ),
    PoolCopSensorEntityDescription(
        key="pump_speed",
        name="Pump speed",
        icon="mdi:speedometer",
        value_fn=lambda data: data.pump.current_speed if data.pump else None,
    ),
    PoolCopSensorEntityDescription(
        key="operation_mode",
        name="Operation Mode",
        icon="mdi:state-machine",
        value_fn=lambda data: data.state.status,
    ),
    PoolCopSensorEntityDescription(
        key="forced_filtration_remaining",
        name="Forced filtration remaining",
        icon="mdi:timer-outline",
        value_fn=lambda data: data.pump.forced_remaining if data.pump else None,
    ),
    # Cycle tracking sensors
    PoolCopSensorEntityDescription(
        key="cycle_elapsed_time",
        name="Cycle Elapsed Time",
        icon="mdi:timer",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda data: (
            round(elapsed / 60)
            if (elapsed := _cycle_elapsed_time_fn(data)) is not None
            else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="cycle_remaining_time",
        name="Cycle Remaining Time",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda data: (
            round(remaining / 60)
            if (remaining := _cycle_time_remaining_fn(data)) is not None
            else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="cycle_predicted_end",
        name="Cycle Predicted End",
        icon="mdi:clock-end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_cycle_end_time_fn,
    ),
    PoolCopSensorEntityDescription(
        key="free_chlorine",
        name="Free Available Chlorine",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mg/L",
        icon="mdi:flask",
        value_fn=lambda data: data.state.free_available_chlorine or None,
    ),
)

# Settings sensors — read from config endpoints
SETTINGS_SENSORS: tuple[PoolCopSensorEntityDescription, ...] = (
    PoolCopSensorEntityDescription(
        key="pool_volume",
        name="Pool Volume",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="m\u00b3",
        icon="mdi:pool",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.pool_config.get("volume") if data.pool_config else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="pool_turnover",
        name="Pool Turnover Rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="x/day",
        icon="mdi:refresh",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.pool_config.get("turnover") if data.pool_config else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="filter_timer_mode",
        name="Filter Timer Mode",
        icon="mdi:timer-cog",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.filter_config.get("timerMode") if data.filter_config else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="filter_backwash_duration",
        name="Backwash Duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.filter_config.get("backwashDuration") if data.filter_config else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="filter_rinse_duration",
        name="Rinse Duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.filter_config.get("rinseDuration") if data.filter_config else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="pump_type",
        name="Pump Type",
        icon="mdi:pump",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.pump_config.get("type") if data.pump_config else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="pump_nb_speeds",
        name="Pump Speed Levels",
        icon="mdi:speedometer",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.pump_config.get("nbSpeed") if data.pump_config else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="pump_flowrate",
        name="Pump Base Flowrate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        icon="mdi:water-pump",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.pump_config.get("flowrate") if data.pump_config else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="ph_set_point",
        name="pH Set Point",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="pH",
        icon="mdi:ph",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.ph_config.get("setPoint") if data.ph_config else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="orp_set_point",
        name="ORP Set Point",
        icon="mdi:molecule",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mV",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.orp_config.get("setPoint") if data.orp_config else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="orp_disinfectant",
        name="ORP Disinfectant Type",
        icon="mdi:water-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.orp_config.get("disinfectantType") if data.orp_config else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PoolCop sensors based on a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Add standard sensors (skip uninstalled components)
    entities: list[SensorEntity] = [
        PoolCopSensorEntity(coordinator=coordinator, description=description)
        for description in SENSORS
        if PoolCopEntity.is_component_installed(coordinator, description.key)
    ]

    # Add computed flow/volume sensors
    entities.append(FlowRateSensor(coordinator=coordinator))
    entities.append(DailyFiltrationVolumeSensor(coordinator=coordinator))
    entities.append(DailyTurnoverSensor(coordinator=coordinator))
    entities.append(PlannedRemainingVolumeSensor(coordinator=coordinator))
    entities.append(PlannedRemainingTurnoverSensor(coordinator=coordinator))

    # Add settings sensors (skip uninstalled components)
    entities.extend(
        PoolCopSensorEntity(coordinator=coordinator, description=description)
        for description in SETTINGS_SENSORS
        if PoolCopEntity.is_component_installed(coordinator, description.key)
    )

    async_add_entities(entities)


class PoolCopSensorEntity(PoolCopEntity, SensorEntity):
    """Defines a PoolCop sensor."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by PoolCop"
    entity_description: PoolCopSensorEntityDescription

    def __init__(
        self,
        *,
        coordinator: PoolCopDataUpdateCoordinator,
        description: PoolCopSensorEntityDescription,
    ) -> None:
        """Initialize PoolCop sensor."""
        super().__init__(coordinator=coordinator, description=description)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.entity_description.available_fn is not None:
            return super().available and self.entity_description.available_fn(
                self.coordinator.data
            )
        return super().available

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if self.entity_description.extra_attrs_fn:
            return self.entity_description.extra_attrs_fn(self.coordinator.data)
        return None


class FlowRateSensor(PoolCopSensorEntity):
    """Flow rate sensor based on pump state, speed, and valve position."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR
    _attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:water-pump"

    def __init__(self, *, coordinator: PoolCopDataUpdateCoordinator) -> None:
        """Initialize the flow rate sensor."""
        description = PoolCopSensorEntityDescription(
            key="pump_flow_rate",
            name="Pump Flow Rate",
            value_fn=lambda data: None,
        )
        super().__init__(coordinator=coordinator, description=description)

    @property
    def native_value(self) -> float:
        """Return the current effective flow rate."""
        return self.coordinator.get_current_flow_rate()


class DailyFiltrationVolumeSensor(PoolCopSensorEntity):
    """Accumulated filtration volume for the current day."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:water-sync"

    def __init__(self, *, coordinator: PoolCopDataUpdateCoordinator) -> None:
        """Initialize the daily filtration volume sensor."""
        description = PoolCopSensorEntityDescription(
            key="daily_filtration_volume",
            name="Daily Filtration Volume",
            value_fn=lambda data: None,
        )
        super().__init__(coordinator=coordinator, description=description)

    @property
    def native_value(self) -> float:
        """Return the accumulated filtration volume today in m3."""
        return self.coordinator.daily_volume


class DailyTurnoverSensor(PoolCopSensorEntity):
    """Number of pool turnovers completed today."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:sync"

    def __init__(self, *, coordinator: PoolCopDataUpdateCoordinator) -> None:
        """Initialize the daily turnover sensor."""
        description = PoolCopSensorEntityDescription(
            key="daily_turnovers",
            name="Daily Turnovers",
            value_fn=lambda data: None,
        )
        super().__init__(coordinator=coordinator, description=description)

    @property
    def native_value(self) -> float | None:
        """Return the number of pool turnovers today."""
        return self.coordinator.daily_turnovers


class PlannedRemainingVolumeSensor(PoolCopSensorEntity):
    """Planned remaining filtration volume for the current day."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:water-outline"

    def __init__(self, *, coordinator: PoolCopDataUpdateCoordinator) -> None:
        """Initialize the planned remaining volume sensor."""
        description = PoolCopSensorEntityDescription(
            key="planned_remaining_volume",
            name="Planned Remaining Filter Volume",
            value_fn=lambda data: None,
        )
        super().__init__(coordinator=coordinator, description=description)

    @property
    def native_value(self) -> float:
        """Return the planned remaining filtration volume in m3."""
        return self.coordinator.planned_remaining_volume


class PlannedRemainingTurnoverSensor(PoolCopSensorEntity):
    """Planned remaining turnovers for the current day."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:sync-circle"

    def __init__(self, *, coordinator: PoolCopDataUpdateCoordinator) -> None:
        """Initialize the planned remaining turnover sensor."""
        description = PoolCopSensorEntityDescription(
            key="planned_remaining_turnovers",
            name="Planned Remaining Turnovers",
            value_fn=lambda data: None,
        )
        super().__init__(coordinator=coordinator, description=description)

    @property
    def native_value(self) -> float | None:
        """Return the planned remaining turnovers."""
        return self.coordinator.planned_remaining_turnovers
