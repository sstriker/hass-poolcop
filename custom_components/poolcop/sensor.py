"""Support for PoolCop sensors."""

from __future__ import annotations

import zoneinfo
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AUX_FIXED_FUNCTION_LABELS,
    CYCLE_ACTIVE_MODES,
    DOMAIN,
    FILTER_MODES,
    FILTER_TIMER_MODES,
    FILTER_TIMER_MODE_DESCRIPTIONS,
    FORCED_FILTRATION_MODES,
    LOGGER,
    OPERATION_MODE_DESCRIPTIONS,
    OPERATION_MODES,
    PH_TYPES,
    POOL_TYPES,
    PUMP_TYPES,
    VALVE_POSITION_NAMES,
    WATER_VALVE_POSITIONS,
    WATERLEVEL_STATES,
    aux_display_name,
    aux_label_id,
)
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

    extra_attrs_fn: Callable[[PoolCopData], dict[str, Any]] | None = None


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
    """Return a value function for timestamp at path.

    Guards against epoch timestamps (before year 2000) which occur when
    the PoolCop hardware resets — returns None instead of a bogus date.
    """

    def value_fn(data: PoolCopData) -> datetime | None:
        value = data.status_value(path)
        if value is None:
            return None
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
        if parsed.year < 2000:
            return None
        return parsed

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


def _is_cycle_mode(data: PoolCopData) -> bool:
    """Return True if the current operating mode uses filtration cycles."""
    mode = data.status_value("status.poolcop")
    return mode in CYCLE_ACTIVE_MODES if mode is not None else False


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


def _state_mapping_fn(path: str, mapping: dict) -> Callable[[PoolCopData], str | None]:
    """Return a value function that maps a numeric value to a string."""

    def value_fn(data: PoolCopData) -> str | None:
        value = data.status_value(path)
        return mapping.get(value)

    return value_fn


def _time_str_to_time_today(time_str: str, timezone: str) -> datetime | None:
    """Convert a time string (HH:MM:SS) to a datetime object for today using timezone."""
    if not time_str or time_str == "00:00:00":
        return None

    try:
        hour, minute, second = map(int, time_str.split(":"))

        # Try using the provided timezone
        try:
            tz_info = zoneinfo.ZoneInfo(timezone)
        except (ValueError, zoneinfo.ZoneInfoNotFoundError):
            # Fall back to system timezone if provided timezone is invalid
            from datetime import timezone as dt_timezone
            from time import localtime

            utc_offset = -localtime().tm_gmtoff
            tz_info = dt_timezone(timedelta(seconds=utc_offset))

        now = datetime.now(tz=tz_info)
        result = datetime(
            year=now.year,
            month=now.month,
            day=now.day,
            hour=hour,
            minute=minute,
            second=second,
            tzinfo=tz_info,
        )

        # Handle case where the time is for tomorrow (e.g., if now is 23:00 and time is 01:00)
        if result < now and hour < 12:
            result = result + timedelta(days=1)
    except (ValueError, TypeError, zoneinfo.ZoneInfoNotFoundError):
        return None
    else:
        return result


def _timer_fn(timer_name: str, field: str) -> Callable[[PoolCopData], Any]:
    """Return a value function for a timer field."""

    def value_fn(data: PoolCopData) -> Any:
        try:
            timer = data.status_value(f"timers.{timer_name}")
            if timer:
                return timer.get(field)
        except (KeyError, AttributeError):
            pass
        return None

    return value_fn


def _timer_time_fn(
    timer_name: str, field: str
) -> Callable[[PoolCopData], datetime | None]:
    """Return a value function for a timer time field as datetime."""

    def value_fn(data: PoolCopData) -> datetime | None:
        try:
            timer = data.status_value(f"timers.{timer_name}")
            if timer and timer.get("enabled") == 1:
                time_str = timer.get(field)

                # Get timezone from Pool data or fallback to UTC
                timezone = data.status_value("timezone", prefix="Pool") or "UTC"
                return _time_str_to_time_today(time_str, timezone)
        except (KeyError, AttributeError, zoneinfo.ZoneInfoNotFoundError) as err:
            LOGGER.debug("Error creating timer time with timezone: %s", err)
        return None

    return value_fn


def _weekday_mapping_fn(path: str) -> Callable[[PoolCopData], str | None]:
    """Return a value function that maps a numeric day value to a weekday name."""
    WEEKDAYS = [
        "Disabled",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    def value_fn(data: PoolCopData) -> str | None:
        value = data.status_value(path)
        if value is None:
            return None
        try:
            day_index = int(value)
            if 0 <= day_index < len(WEEKDAYS):
                return WEEKDAYS[day_index]
        except (ValueError, TypeError):
            pass
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
        native_unit_of_measurement=UnitOfPressure.KPA,
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
        options=list(WATERLEVEL_STATES.values()),
        value_fn=_state_mapping_fn("waterlevel", WATERLEVEL_STATES),
    ),
    PoolCopSensorEntityDescription(
        key="valve_position",
        name="Valve position",
        icon="mdi:valve",
        device_class=SensorDeviceClass.ENUM,
        options=list(VALVE_POSITION_NAMES.values()),
        value_fn=_state_mapping_fn("status.valveposition", VALVE_POSITION_NAMES),
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
        device_class=SensorDeviceClass.ENUM,
        options=list(OPERATION_MODES.values()),
        value_fn=_state_mapping_fn("status.poolcop", OPERATION_MODES),
        extra_attrs_fn=lambda data: {
            "description": OPERATION_MODE_DESCRIPTIONS.get(
                data.status_value("status.poolcop"), ""
            )
        },
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
        options=list(FORCED_FILTRATION_MODES.values()),
        value_fn=_state_mapping_fn("status.forced.mode", FORCED_FILTRATION_MODES),
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
        key="refill_status",
        name="Refill Status",
        icon="mdi:water-pump",
        device_class=SensorDeviceClass.ENUM,
        options=list(WATER_VALVE_POSITIONS.values()),
        value_fn=_state_mapping_fn("status.watervalve", WATER_VALVE_POSITIONS),
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
        value_fn=lambda data: (
            round(_cycle_elapsed_time_fn(data) / 60)
            if _cycle_elapsed_time_fn(data) is not None
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
            round(_cycle_time_remaining_fn(data) / 60)
            if _cycle_time_remaining_fn(data) is not None
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
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.pool.volume"),
    ),
    PoolCopSensorEntityDescription(
        key="pool_turnover",
        name="Pool Turnover Rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="x/day",
        icon="mdi:refresh",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.pool.turnover"),
    ),
    PoolCopSensorEntityDescription(
        key="pool_cover_reduction",
        name="Cover Flow Reduction",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        icon="mdi:percent",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.pool.cover_reduction"),
    ),
    PoolCopSensorEntityDescription(
        key="pool_type",
        name="Pool Type",
        icon="mdi:pool",
        device_class=SensorDeviceClass.ENUM,
        options=list(POOL_TYPES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_state_mapping_fn("settings.pool.type", POOL_TYPES),
    ),
    # Filter settings
    PoolCopSensorEntityDescription(
        key="filter_pressure",
        name="Filter Pressure Threshold",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.PA,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.filter.pressure"),
    ),
    PoolCopSensorEntityDescription(
        key="filter_backwash_duration",
        name="Backwash Duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.filter.backwash_duration"),
    ),
    PoolCopSensorEntityDescription(
        key="filter_rinse_duration",
        name="Rinse Duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.filter.rinse_duration"),
    ),
    PoolCopSensorEntityDescription(
        key="filter_max_days",
        name="Maximum Days Between Backwash",
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:calendar-range",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.filter.max_days"),
    ),
    PoolCopSensorEntityDescription(
        key="filter_timer_mode",
        name="Filter Timer Mode",
        icon="mdi:timer-cog",
        device_class=SensorDeviceClass.ENUM,
        options=list(FILTER_TIMER_MODES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_state_mapping_fn("settings.filter.timer", FILTER_TIMER_MODES),
        extra_attrs_fn=lambda data: {
            "description": FILTER_TIMER_MODE_DESCRIPTIONS.get(
                data.status_value("settings.filter.timer"), ""
            )
        },
    ),
    PoolCopSensorEntityDescription(
        key="filter_mode",
        name="Filter Mode",
        icon="mdi:air-filter",
        device_class=SensorDeviceClass.ENUM,
        options=list(FILTER_MODES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_state_mapping_fn("settings.filter.mode", FILTER_MODES),
    ),
    # Pump settings
    PoolCopSensorEntityDescription(
        key="pump_nb_speeds",
        name="Pump Speed Levels",
        icon="mdi:speedometer",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.pump.nb_speed"),
    ),
    PoolCopSensorEntityDescription(
        key="pump_pressure_low",
        name="Pump Low Pressure Threshold",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.PA,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.pump.pressure_low"),
    ),
    PoolCopSensorEntityDescription(
        key="pump_pressure_alarm",
        name="Pump Alarm Pressure Threshold",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.PA,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.pump.pressure_alarm"),
    ),
    PoolCopSensorEntityDescription(
        key="pump_type",
        name="Pump Type",
        icon="mdi:pump",
        device_class=SensorDeviceClass.ENUM,
        options=list(PUMP_TYPES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_state_mapping_fn("settings.pump.type", PUMP_TYPES),
    ),
    PoolCopSensorEntityDescription(
        key="pump_flowrate",
        name="Pump Base Flowrate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        icon="mdi:water-pump",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.pump.flowrate"),
    ),
    PoolCopSensorEntityDescription(
        key="pump_speed_cycle1",
        name="Pump Speed Cycle 1",
        icon="mdi:speedometer",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.pump.speed_cycle1"),
    ),
    PoolCopSensorEntityDescription(
        key="pump_speed_cycle2",
        name="Pump Speed Cycle 2",
        icon="mdi:speedometer",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.pump.speed_cycle2"),
    ),
    PoolCopSensorEntityDescription(
        key="pump_speed_backwash",
        name="Pump Speed Backwash",
        icon="mdi:speedometer",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.pump.speed_backwash"),
    ),
    PoolCopSensorEntityDescription(
        key="pump_speed_cover",
        name="Pump Speed Cover",
        icon="mdi:speedometer",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.pump.speed_cover"),
    ),
    # pH settings
    PoolCopSensorEntityDescription(
        key="ph_set_point",
        name="pH Set Point",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="pH",
        icon="mdi:ph",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.ph.set_point"),
    ),
    PoolCopSensorEntityDescription(
        key="ph_type",
        name="pH Dosing Type",
        icon="mdi:ph",
        device_class=SensorDeviceClass.ENUM,
        options=list(PH_TYPES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_state_mapping_fn("settings.ph.type", PH_TYPES),
    ),
    PoolCopSensorEntityDescription(
        key="ph_dosing_time",
        name="pH Dosing Time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.ph.dosing_time"),
    ),
    PoolCopSensorEntityDescription(
        key="ph_next_injection",
        name="pH Next Injection",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-sand",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.ph.next_injection"),
    ),
    # ORP settings
    PoolCopSensorEntityDescription(
        key="orp_set_point",
        name="ORP Set Point",
        icon="mdi:molecule",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mV",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.orp.set_point"),
    ),
    PoolCopSensorEntityDescription(
        key="orp_disinfectant",
        name="ORP Disinfectant Type",
        icon="mdi:water-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.orp.disinfectant"),
    ),
    PoolCopSensorEntityDescription(
        key="orp_next_injection",
        name="ORP Next Injection",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-sand",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.orp.next_injection"),
    ),
    PoolCopSensorEntityDescription(
        key="orp_hyper_set_point",
        name="ORP Hyper Chlorination Set Point",
        icon="mdi:molecule",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mV",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.orp.hyper_set_point"),
    ),
    PoolCopSensorEntityDescription(
        key="orp_hyper_day",
        name="ORP Hyper Chlorination Day",
        icon="mdi:calendar-week",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "Disabled",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_weekday_mapping_fn("settings.orp.hyper_day"),
    ),
    PoolCopSensorEntityDescription(
        key="orp_temperature_shutdown",
        name="ORP Temperature Shutdown",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.orp.temperature_shutdown"),
    ),
    # Waterlevel settings
    PoolCopSensorEntityDescription(
        key="waterlevel_cable_status",
        name="Waterlevel Cable Status",
        icon="mdi:cable-data",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.waterlevel.cable_status"),
    ),
    PoolCopSensorEntityDescription(
        key="waterlevel_max_duration",
        name="Waterlevel Max Duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.waterlevel.max_duration"),
    ),
    PoolCopSensorEntityDescription(
        key="waterlevel_draining_duration",
        name="Waterlevel Draining Duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.waterlevel.draining_duration"),
    ),
    # Autochlor settings
    PoolCopSensorEntityDescription(
        key="autochlor_duration",
        name="Autochlor Duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.autochlor.duration"),
    ),
    PoolCopSensorEntityDescription(
        key="autochlor_next_injection",
        name="Autochlor Next Injection",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-sand",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.autochlor.next_injection"),
    ),
    # Ioniser settings
    PoolCopSensorEntityDescription(
        key="ioniser_duration",
        name="Ioniser Duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.ioniser.duration"),
    ),
    PoolCopSensorEntityDescription(
        key="ioniser_current",
        name="Ioniser Current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement="A",
        icon="mdi:lightning-bolt",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.ioniser.current"),
    ),
    PoolCopSensorEntityDescription(
        key="ioniser_next_injection",
        name="Ioniser Next Injection",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-sand",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value_fn("settings.ioniser.next_injection"),
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
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            "Enabled" if _timer_fn("cycle1", "enabled")(data) == 1 else "Disabled"
        ),
    ),
    PoolCopSensorEntityDescription(
        key="cycle1_start_time",
        name="Cycle 1 Start Time",
        icon="mdi:clock-start",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_timer_time_fn("cycle1", "start"),
    ),
    PoolCopSensorEntityDescription(
        key="cycle1_stop_time",
        name="Cycle 1 Stop Time",
        icon="mdi:clock-end",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_timer_time_fn("cycle1", "stop"),
    ),
    # Cycle 2 timer
    PoolCopSensorEntityDescription(
        key="cycle2_enabled",
        name="Cycle 2 Enabled",
        icon="mdi:toggle-switch",
        device_class=SensorDeviceClass.ENUM,
        options=["Disabled", "Enabled"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            "Enabled" if _timer_fn("cycle2", "enabled")(data) == 1 else "Disabled"
        ),
    ),
    PoolCopSensorEntityDescription(
        key="cycle2_start_time",
        name="Cycle 2 Start Time",
        icon="mdi:clock-start",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_timer_time_fn("cycle2", "start"),
    ),
    PoolCopSensorEntityDescription(
        key="cycle2_stop_time",
        name="Cycle 2 Stop Time",
        icon="mdi:clock-end",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_timer_time_fn("cycle2", "stop"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PoolCop sensors based on a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Add standard sensors (skip uninstalled components)
    entities = [
        PoolCopSensorEntity(coordinator=coordinator, description=description)
        for description in SENSORS
        if PoolCopEntity.is_component_installed(coordinator, description.key)
    ]

    # Add the flow rate sensor
    entities.append(FlowRateSensor(coordinator=coordinator))

    # Add settings sensors (skip uninstalled components)
    entities.extend(
        PoolCopSensorEntity(coordinator=coordinator, description=description)
        for description in SETTINGS_SENSORS
        if PoolCopEntity.is_component_installed(coordinator, description.key)
    )

    # Add timer sensors (cycle1, cycle2)
    entities.extend(
        PoolCopSensorEntity(coordinator=coordinator, description=description)
        for description in TIMER_SENSORS
    )

    # Add dynamic aux timer sensors from API aux array
    # Skip fixed-function aux (firmware-managed, not user-scheduled)
    aux_list = coordinator.data.status_value("aux") or []
    timers = coordinator.data.status_value("timers") or {}
    for aux in aux_list:
        aux_id = aux["id"]
        timer_key = f"aux{aux_id}"
        if timer_key not in timers:
            continue
        lid = aux_label_id(aux.get("label", ""))
        if lid is not None and lid in AUX_FIXED_FUNCTION_LABELS:
            continue
        label = aux_display_name(aux.get("label", ""), aux_id)
        entities.append(
            PoolCopSensorEntity(
                coordinator=coordinator,
                description=PoolCopSensorEntityDescription(
                    key=f"{timer_key}_enabled",
                    name=f"{label} Enabled",
                    icon="mdi:toggle-switch",
                    device_class=SensorDeviceClass.ENUM,
                    options=["Disabled", "Enabled"],
                    entity_category=EntityCategory.DIAGNOSTIC,
                    value_fn=lambda data, k=timer_key: (
                        "Enabled" if _timer_fn(k, "enabled")(data) == 1 else "Disabled"
                    ),
                ),
            )
        )
        entities.append(
            PoolCopSensorEntity(
                coordinator=coordinator,
                description=PoolCopSensorEntityDescription(
                    key=f"{timer_key}_start_time",
                    name=f"{label} Start Time",
                    icon="mdi:clock-start",
                    device_class=SensorDeviceClass.TIMESTAMP,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    value_fn=_timer_time_fn(timer_key, "start"),
                ),
            )
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
    """Flow rate sensor that calculates flow based on pump speed."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR
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

        try:
            speed_level = int(speed_level)
        except (ValueError, TypeError):
            LOGGER.warning(
                "Invalid pump speed level: %s, flow rate unavailable", speed_level
            )
            return None

        if speed_level in self.coordinator.flow_rates:
            flow_rate = self.coordinator.flow_rates[speed_level]
            LOGGER.debug(
                "Using flow rate for speed %s: %s m³/h", speed_level, flow_rate
            )
            return flow_rate

        LOGGER.warning("Unknown speed level: %s, flow rate unavailable", speed_level)
        return None
