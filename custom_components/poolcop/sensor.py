"""Support for PoolCop sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
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
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, FILTER_MODES, FILTER_TIMER_MODES
from .coordinator import PoolCopData, PoolCopDataUpdateCoordinator
from .entity import PoolCopEntity


@dataclass
class PoolCopSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[PoolCopData], str | int | float | datetime | None]


@dataclass
class PoolCopSensorEntityDescription(
    SensorEntityDescription, PoolCopSensorEntityDescriptionMixin
):
    """Describes PoolCop sensor entity."""


def _value_fn(
    path: str,
) -> Callable[[PoolCopData], str | int | float | datetime | None]:
    """Return a value function for data at path."""

    def value_fn(data: PoolCopData) -> str | int | float | datetime | None:
        return data.status_value(path)

    return value_fn


def _datetime_value_fn(
    path: str,
) -> Callable[[PoolCopData], datetime | None]:
    """Return a value function for timestamp at path."""

    def value_fn(data: PoolCopData) -> datetime | None:
        value = data.status_value(path)
        if value is None:
            return None
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")

    return value_fn


def _active_alarm_value_fn(
    attribute: str,
) -> Callable[[PoolCopData], str | int | float | datetime | None]:
    """Return value function for active alarm data."""
    
    def value_fn(data: PoolCopData) -> str | int | float | datetime | None:
        if not data.active_alarms:
            return None
        # Return the attribute from the most recent active alarm
        return data.active_alarms[0].get(attribute)
        
    return value_fn


def _active_alarm_timestamp_fn(
    attribute: str,
) -> Callable[[PoolCopData], datetime | None]:
    """Return timestamp function for active alarm data."""
    
    def value_fn(data: PoolCopData) -> datetime | None:
        if not data.active_alarms:
            return None
        timestamp = data.active_alarms[0].get(attribute)
        if not timestamp:
            return None
        return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")
        
    return value_fn


def _pump_flow_fn(data: PoolCopData) -> float | None:
    """Calculate pump flow rate based on current pump speed."""
    # Get the pump state and speed
    is_pump_on = bool(data.status_value("status.pump"))
    if not is_pump_on:
        return 0.0
        
    # Get the current pump speed level
    speed_level = data.status_value("status.pumpspeed")
    if speed_level is None:
        return None
        
    # Get the coordinator reference to access flow calculation method
    # This is a bit of a hack, but it allows us to access the coordinator's method
    coordinator = data._asdict().get("_coordinator")
    if not coordinator:
        return None
        
    # Calculate the flow rate based on the current speed level
    return coordinator.calculate_flow_rate(float(speed_level))


def _cycle_time_remaining_fn(data: PoolCopData) -> float | None:
    """Get remaining time in seconds for the current cycle."""
    if data.cycle_status and data.cycle_status.get("remaining_time") is not None:
        return data.cycle_status["remaining_time"]
    return None


def _cycle_end_time_fn(data: PoolCopData) -> datetime | None:
    """Get predicted end time for the current cycle."""
    if data.cycle_status and data.cycle_status.get("predicted_end") is not None:
        timestamp = data.cycle_status["predicted_end"]
        return datetime.fromtimestamp(timestamp)
    return None


def _cycle_elapsed_time_fn(data: PoolCopData) -> float | None:
    """Get elapsed time in seconds for the current cycle."""
    if data.cycle_status and data.cycle_status.get("elapsed_time") is not None:
        return data.cycle_status["elapsed_time"]
    return None


# Define value functions for pool settings
def _value_fn_pool_settings(path: str) -> Callable[[PoolCopData], Any]:
    """Return a value function for settings data at path."""
    def value_fn(data: PoolCopData) -> Any:
        try:
            return data.status_value(path, prefix="PoolCop.settings")
        except (KeyError, AttributeError):
            return None
    return value_fn


def _state_mapping_fn(path: str, mapping: dict) -> Callable[[PoolCopData], str | None]:
    """Return a value function that maps a numeric value to a string."""
    def value_fn(data: PoolCopData) -> str | None:
        value = data.status_value(path)
        if value is None:
            return None
        return mapping.get(value, f"Unknown ({value})")
    return value_fn

def _time_str_to_time_today(time_str: str) -> datetime | None:
    """Convert a time string (HH:MM:SS) to a datetime object for today."""
    if not time_str or time_str == "00:00:00":
        return None
        
    try:
        hour, minute, second = map(int, time_str.split(':'))
        now = datetime.now()
        result = datetime(
            year=now.year, month=now.month, day=now.day,
            hour=hour, minute=minute, second=second
        )
        
        # Handle case where the time is for tomorrow (e.g., if now is 23:00 and time is 01:00)
        if result < now and hour < 12:
            result = result + timedelta(days=1)
            
        return result
    except (ValueError, TypeError):
        return None

def _timer_fn(timer_name: str, field: str) -> Callable[[PoolCopData], Any]:
    """Return a value function for a timer field."""
    def value_fn(data: PoolCopData) -> Any:
        try:
            timer = data.status_value(f"timers.{timer_name}")
            if timer:
                return timer.get(field)
            return None
        except (KeyError, AttributeError):
            return None
    return value_fn

def _timer_time_fn(timer_name: str, field: str) -> Callable[[PoolCopData], datetime | None]:
    """Return a value function for a timer time field as datetime."""
    def value_fn(data: PoolCopData) -> datetime | None:
        try:
            timer = data.status_value(f"timers.{timer_name}")
            if timer and timer.get("enabled") == 1:
                time_str = timer.get(field)
                return _time_str_to_time_today(time_str)
            return None
        except (KeyError, AttributeError):
            return None
    return value_fn


SENSORS: tuple[PoolCopSensorEntityDescription, ...] = (
    PoolCopSensorEntityDescription(
        key="temperature_water",
        name="Water temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=_value_fn("temperature.water"),
    ),
    PoolCopSensorEntityDescription(
        key="temperature_air",
        name="Air temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=_value_fn("temperature.air"),
    ),
    PoolCopSensorEntityDescription(
        key="pressure",
        name="Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.PA,
        value_fn=_value_fn("pressure"),
    ),
    PoolCopSensorEntityDescription(
        key="pH",
        name="pH",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="pH",
        value_fn=_value_fn("pH"),
    ),
    PoolCopSensorEntityDescription(
        key="orp",
        name="Oxidation-Reduction Potential",
        icon="mdi:molecule",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mV",
        value_fn=_value_fn("orp"),
    ),
    PoolCopSensorEntityDescription(
        key="ioniser",
        name="Ioniser",
        icon="mdi:lightning-bolt",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="g/h",
        value_fn=_value_fn("ioniser"),
    ),
    PoolCopSensorEntityDescription(
        key="voltage",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=_value_fn("voltage"),
    ),
    PoolCopSensorEntityDescription(
        key="waterlevel",
        name="Water level",
        icon="mdi:waves",
        device_class=SensorDeviceClass.ENUM,
        options=["Not Installed", "Low", "Normal", "High", "Error"],
        value_fn=_value_fn("waterlevel"),
    ),
    PoolCopSensorEntityDescription(
        key="valve_position",
        name="Valve position",
        icon="mdi:valve",
        device_class=SensorDeviceClass.ENUM,
        options=["Filter", "Waste", "Closed", "Backwash", "Bypass", "Rinse", "Unknown", "None"],
        value_fn=_value_fn("status.valveposition"),
    ),
    PoolCopSensorEntityDescription(
        key="pump_speed",
        name="Pump speed",
        icon="mdi:speedometer",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value_fn("status.pumpspeed"),
    ),
    PoolCopSensorEntityDescription(
        key="poolcop",
        name="Operation Mode",
        icon="mdi:state-machine",
        value_fn=_value_fn("status.poolcop"),
        device_class=SensorDeviceClass.ENUM,
        options=["Idle", "Cycle 1", "Backwash", "Cycle 2", "Waste", "Rinse", "Pause", "External Filter"],
    ),
    PoolCopSensorEntityDescription(
        key="last_backwash",
        name="Last backwash",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_datetime_value_fn("history.backwash"),
    ),
    PoolCopSensorEntityDescription(
        key="last_refill",
        name="Last refill",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_datetime_value_fn("history.refill"),
    ),
    PoolCopSensorEntityDescription(
        key="last_ph_measure",
        name="Last pH measure",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_datetime_value_fn("history.ph_measure"),
    ),
    PoolCopSensorEntityDescription(
        key="forced_filtration_mode",
        name="Forced filtration mode",
        icon="mdi:clock-fast",
        device_class=SensorDeviceClass.ENUM,
        options=["None", "24 Hours", "48 Hours", "72 Hours"],
        value_fn=_value_fn("status.forced.mode"),
    ),
    PoolCopSensorEntityDescription(
        key="forced_filtration_remaining",
        name="Forced filtration remaining",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=_value_fn("status.forced.remaining_hours"),
    ),
    PoolCopSensorEntityDescription(
        key="water_valve_position",
        name="Water valve position",
        icon="mdi:pipe-valve",
        device_class=SensorDeviceClass.ENUM,
        options=["Standby", "Refill", "Measure"],
        value_fn=_value_fn("status.watervalve"),
    ),
    PoolCopSensorEntityDescription(
        key="running_status",
        name="System Running Status",
        icon="mdi:sync-circle",
        device_class=SensorDeviceClass.ENUM,
        options=["Stopped", "Freeze Protection", "Forced", "Auto", "Timer", "Manual", "Paused", "External"],
        value_fn=_value_fn("status.running_status"),
    ),
    PoolCopSensorEntityDescription(
        key="ph_setpoint",
        name="pH Setpoint",
        icon="mdi:ph",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="pH",
        value_fn=_value_fn("conf.ph_setpoint"),
    ),
    PoolCopSensorEntityDescription(
        key="orp_setpoint",
        name="ORP Setpoint",
        icon="mdi:molecule",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mV",
        value_fn=_value_fn("conf.orp_setpoint"),
    ),
    PoolCopSensorEntityDescription(
        key="filtration_time_today",
        name="Filtration Time Today",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=_value_fn("status.filtration_time.today"),
    ),
    PoolCopSensorEntityDescription(
        key="filtration_time_yesterday",
        name="Filtration Time Yesterday",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=_value_fn("status.filtration_time.yesterday"),
    ),
    PoolCopSensorEntityDescription(
        key="filtration_time_total",
        name="Filtration Time Total",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=_value_fn("status.filtration_time.total"),
    ),
    PoolCopSensorEntityDescription(
        key="active_alarm_code",
        name="Alarm Code",
        icon="mdi:alert-circle",
        value_fn=_active_alarm_value_fn("code"),
    ),
    PoolCopSensorEntityDescription(
        key="active_alarm_description",
        name="Alarm Description",
        icon="mdi:alert-circle",
        value_fn=_active_alarm_value_fn("description"),
    ),
    PoolCopSensorEntityDescription(
        key="active_alarm_timestamp",
        name="Alarm Time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_active_alarm_timestamp_fn("timestamp"),
    ),
    # Cycle tracking sensors
    PoolCopSensorEntityDescription(
        key="cycle_elapsed_time",
        name="Cycle Elapsed Time",
        icon="mdi:timer",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda data: round(_cycle_elapsed_time_fn(data) / 60) if _cycle_elapsed_time_fn(data) is not None else None,
    ),
    PoolCopSensorEntityDescription(
        key="cycle_remaining_time",
        name="Cycle Remaining Time",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda data: round(_cycle_time_remaining_fn(data) / 60) if _cycle_time_remaining_fn(data) is not None else None,
    ),
    PoolCopSensorEntityDescription(
        key="cycle_predicted_end",
        name="Cycle Predicted End",
        icon="mdi:clock-end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_cycle_end_time_fn,
    ),
    PoolCopSensorEntityDescription(
        key="filter_mode",
        name="Filter Mode",
        icon="mdi:air-filter",
        device_class=SensorDeviceClass.ENUM,
        options=list(FILTER_MODES.values()),
        value_fn=_state_mapping_fn("status.filter_mode", FILTER_MODES),
    ),
)

# Additional sensors for pool settings
SETTINGS_SENSORS: tuple[PoolCopSensorEntityDescription, ...] = (
    # Pool settings
    PoolCopSensorEntityDescription(
        key="pool_volume",
        name="Pool Volume",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="m³",
        icon="mdi:pool",
        value_fn=_value_fn_pool_settings("pool.volume"),
    ),
    PoolCopSensorEntityDescription(
        key="pool_turnover",
        name="Pool Turnover Rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="×/day",
        icon="mdi:refresh",
        value_fn=_value_fn_pool_settings("pool.turnover"),
    ),
    PoolCopSensorEntityDescription(
        key="pool_cover_reduction",
        name="Cover Flow Reduction",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        icon="mdi:percent",
        value_fn=_value_fn_pool_settings("pool.cover_reduction"),
    ),
    
    # Filter settings
    PoolCopSensorEntityDescription(
        key="filter_backwash_duration",
        name="Backwash Duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-outline",
        value_fn=_value_fn_pool_settings("filter.backwash_duration"),
    ),
    PoolCopSensorEntityDescription(
        key="filter_rinse_duration",
        name="Rinse Duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-outline",
        value_fn=_value_fn_pool_settings("filter.rinse_duration"),
    ),
    PoolCopSensorEntityDescription(
        key="filter_max_days",
        name="Maximum Days Between Backwash",
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:calendar-range",
        value_fn=_value_fn_pool_settings("filter.max_days"),
    ),
    PoolCopSensorEntityDescription(
        key="filter_timer_mode",
        name="Filter Timer Mode",
        icon="mdi:timer-cog",
        device_class=SensorDeviceClass.ENUM,
        options=list(FILTER_TIMER_MODES.values()),
        value_fn=lambda data: FILTER_TIMER_MODES.get(
            data.status_value("filter.timer", prefix="PoolCop.settings"), 
            f"Unknown ({data.status_value('filter.timer', prefix='PoolCop.settings')})"
        ),
    ),
    
    # Pump settings
    PoolCopSensorEntityDescription(
        key="pump_nb_speeds",
        name="Pump Speed Levels",
        icon="mdi:speedometer",
        value_fn=_value_fn_pool_settings("pump.nb_speed"),
    ),
    PoolCopSensorEntityDescription(
        key="pump_pressure_low",
        name="Pump Low Pressure Threshold",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.PA,
        value_fn=_value_fn_pool_settings("pump.pressure_low"),
    ),
    PoolCopSensorEntityDescription(
        key="pump_pressure_alarm",
        name="Pump Alarm Pressure Threshold",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.PA,
        value_fn=_value_fn_pool_settings("pump.pressure_alarm"),
    ),
    
    # pH settings
    PoolCopSensorEntityDescription(
        key="ph_set_point",
        name="pH Set Point",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="pH",
        icon="mdi:ph",
        value_fn=_value_fn_pool_settings("ph.set_point"),
    ),
    
    # ORP settings
    PoolCopSensorEntityDescription(
        key="orp_set_point",
        name="ORP Set Point",
        icon="mdi:molecule",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mV",
        value_fn=_value_fn_pool_settings("orp.set_point"),
    ),
    PoolCopSensorEntityDescription(
        key="orp_hyper_set_point",
        name="ORP Hyper Chlorination Set Point",
        icon="mdi:molecule",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mV",
        value_fn=_value_fn_pool_settings("orp.hyper_set_point"),
    ),
    PoolCopSensorEntityDescription(
        key="orp_temperature_shutdown",
        name="ORP Temperature Shutdown",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=_value_fn_pool_settings("orp.temperature_shutdown"),
    ),
)

# Timer sensors to expose cycle and auxiliary timers
TIMER_SENSORS: tuple[PoolCopSensorEntityDescription, ...] = (
    # Cycle 1 timer
    PoolCopSensorEntityDescription(
        key="cycle1_enabled",
        name="Cycle 1 Enabled",
        icon="mdi:toggle-switch",
        device_class=SensorDeviceClass.ENUM,
        options=["Disabled", "Enabled"],
        value_fn=lambda data: "Enabled" if _timer_fn("cycle1", "enabled")(data) == 1 else "Disabled",
    ),
    PoolCopSensorEntityDescription(
        key="cycle1_start_time",
        name="Cycle 1 Start Time",
        icon="mdi:clock-start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_timer_time_fn("cycle1", "start"),
    ),
    PoolCopSensorEntityDescription(
        key="cycle1_stop_time",
        name="Cycle 1 Stop Time",
        icon="mdi:clock-end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_timer_time_fn("cycle1", "stop"),
    ),
    
    # Cycle 2 timer
    PoolCopSensorEntityDescription(
        key="cycle2_enabled",
        name="Cycle 2 Enabled",
        icon="mdi:toggle-switch",
        device_class=SensorDeviceClass.ENUM,
        options=["Disabled", "Enabled"],
        value_fn=lambda data: "Enabled" if _timer_fn("cycle2", "enabled")(data) == 1 else "Disabled",
    ),
    PoolCopSensorEntityDescription(
        key="cycle2_start_time",
        name="Cycle 2 Start Time",
        icon="mdi:clock-start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_timer_time_fn("cycle2", "start"),
    ),
    PoolCopSensorEntityDescription(
        key="cycle2_stop_time",
        name="Cycle 2 Stop Time",
        icon="mdi:clock-end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_timer_time_fn("cycle2", "stop"),
    ),
    
    # Add sensors for switchable auxiliary outputs
    PoolCopSensorEntityDescription(
        key="aux4_enabled",
        name="Aux 4 Enabled",
        icon="mdi:toggle-switch",
        device_class=SensorDeviceClass.ENUM,
        options=["Disabled", "Enabled"],
        value_fn=lambda data: "Enabled" if _timer_fn("aux4", "enabled")(data) == 1 else "Disabled",
    ),
    PoolCopSensorEntityDescription(
        key="aux4_start_time",
        name="Aux 4 Start Time",
        icon="mdi:clock-start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_timer_time_fn("aux4", "start"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PoolCop sensors based on a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Add standard sensors
    entities = [
        PoolCopSensorEntity(coordinator=coordinator, description=description)
        for description in SENSORS
    ]
    
    # Add the flow rate sensor
    entities.append(FlowRateSensor(coordinator=coordinator))
    
    # Add settings sensors
    entities.extend(
        PoolCopSensorEntity(coordinator=coordinator, description=description)
        for description in SETTINGS_SENSORS
    )
    
    # Add timer sensors
    entities.extend(
        PoolCopSensorEntity(coordinator=coordinator, description=description)
        for description in TIMER_SENSORS
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
        self.entity_id = f"{SENSOR_DOMAIN}.{self._attr_unique_id}"

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class FlowRateSensor(PoolCopSensorEntity):
    """Flow rate sensor that calculates flow based on pump speed."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "m³/h"
    _attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:water-pump"

    def __init__(
        self,
        *,
        coordinator: PoolCopDataUpdateCoordinator,
    ) -> None:
        """Initialize the flow rate sensor."""
        # Create a simple description for this sensor
        description = PoolCopSensorEntityDescription(
            key="pump_flow_rate",
            name="Pump Flow Rate",
            value_fn=lambda data: None,  # We'll override native_value
        )
        super().__init__(coordinator=coordinator, description=description)

    @property
    def native_value(self) -> float | None:
        """Return the current flow rate based on pump speed."""
        # First check if the pump is on
        is_pump_on = bool(self.coordinator.data.status_value("status.pump"))
        if not is_pump_on:
            return 0.0
            
        # Get the current pump speed level (discrete value 0-3)
        speed_level = self.coordinator.data.status_value("status.pumpspeed")
        if speed_level is None:
            return None
            
        # Calculate the flow rate based on the current speed level
        return self.coordinator.calculate_flow_rate(speed_level)
