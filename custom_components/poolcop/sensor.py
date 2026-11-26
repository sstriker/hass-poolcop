"""Support for PoolCop sensors."""

from __future__ import annotations

import zoneinfo
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, tzinfo
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    AUX_FIXED_FUNCTION_LABELS,
    CYCLE_ACTIVE_MODES,
    LOGGER,
    aux_display_name,
)
from .coordinator import (
    MODE_NAME_TO_ID,
    PoolCopConfigEntry,
    PoolCopData,
    PoolCopDataUpdateCoordinator,
)
from .entity import PoolCopEntity
from .units import FLOW_RATE, PRESSURE, TEMPERATURE, VOLUME, ha_unit

# Coordinator-driven; no per-entity polling
PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class PoolCopSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[PoolCopData], str | int | float | datetime | None]


@dataclass(frozen=True)
class PoolCopSensorEntityDescription(
    SensorEntityDescription, PoolCopSensorEntityDescriptionMixin
):
    """Describes PoolCop sensor entity."""

    # Measurement kind in the API's units header. Values always come in the
    # metric native unit; the account's preferred unit is suggested for display.
    unit_kind: str | None = None


# ---------------------------------------------------------------------------
# Helper: parse ISO datetime strings from history fields
# ---------------------------------------------------------------------------


def _parse_datetime(value: str | None, tz_name: str = "UTC") -> datetime | None:
    """Parse an ISO datetime string, guarding against epoch/reset timestamps.

    Naive datetimes are assumed to be in the given timezone (default UTC).
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.year < 2000:
            return None
        if parsed.tzinfo is None:
            try:
                tz = zoneinfo.ZoneInfo(tz_name)
            except ValueError, zoneinfo.ZoneInfoNotFoundError:
                tz = zoneinfo.ZoneInfo("UTC")
            parsed = parsed.replace(tzinfo=tz)
        return parsed
    except ValueError, TypeError:
        return None


def _parse_duration_seconds(value: str | None) -> int | None:
    """Parse a TimeSpan string (HH:MM:SS) to total seconds, None if empty."""
    if not value or value == "00:00:00":
        return None
    try:
        parts = value.split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError, IndexError:
        return None


def _setting_seconds(value: str | None) -> int | None:
    """Parse a settings TimeSpan (D.HH:MM:SS or HH:MM:SS) to seconds.

    Unlike _parse_duration_seconds, a zero duration is a valid setting.
    """
    if not value:
        return None
    days, _, rest = value.rpartition(".")
    try:
        hours, minutes, seconds = (int(part) for part in rest.split(":"))
        return int(days or 0) * 86400 + hours * 3600 + minutes * 60 + seconds
    except ValueError:
        return None


def _setting_days(value: str | None) -> float | None:
    """Parse a settings TimeSpan to days."""
    seconds = _setting_seconds(value)
    return None if seconds is None else round(seconds / 86400, 2)


# ---------------------------------------------------------------------------
# Helper: safe pump accessor
# ---------------------------------------------------------------------------


def _pump(data: PoolCopData) -> Any:
    """Return first pump info or None."""
    pumps = data.device.state.pumps
    return pumps[0] if pumps else None


# ---------------------------------------------------------------------------
# Helper: safe first filtration settings accessor
# ---------------------------------------------------------------------------


def _filtration(data: PoolCopData) -> Any:
    """Return first filtration settings or None."""
    filtrations = data.device.settings.filtrations
    return filtrations[0] if filtrations else None


# ---------------------------------------------------------------------------
# Cycle tracking helpers (read from coordinator-computed cycle_status dict)
# ---------------------------------------------------------------------------


def _is_cycle_mode(data: PoolCopData) -> bool:
    """Return True if the current operating mode uses filtration cycles."""
    pump = _pump(data)
    if pump is None:
        return False
    mode_id = MODE_NAME_TO_ID.get(pump.running_status)
    return mode_id in CYCLE_ACTIVE_MODES if mode_id is not None else False


def _api_cycle_seconds(data: PoolCopData, attr: str) -> int | None:
    """Return the current cycle's elapsed or remaining time reported by the API."""
    filtration = _filtration(data)
    if filtration is None:
        return None
    return _parse_duration_seconds(getattr(filtration, attr))


def _cycle_time_remaining_fn(data: PoolCopData) -> float | None:
    """Get remaining time in seconds for the current cycle."""
    if not _is_cycle_mode(data):
        return None
    if (
        seconds := _api_cycle_seconds(data, "current_cycle_remaining_time")
    ) is not None:
        return float(seconds)
    if data.cycle_status and data.cycle_status.get("remaining_time") is not None:
        return float(data.cycle_status["remaining_time"])
    return None


def _cycle_end_time_fn(data: PoolCopData) -> datetime | None:
    """Get predicted end time for the current cycle."""
    if not _is_cycle_mode(data):
        return None
    if (
        seconds := _api_cycle_seconds(data, "current_cycle_remaining_time")
    ) is not None:
        # Whole minutes, so the state doesn't change on every update
        return (dt_util.utcnow() + timedelta(seconds=seconds)).replace(
            second=0, microsecond=0
        )
    if data.cycle_status and data.cycle_status.get("predicted_end") is not None:
        timestamp = data.cycle_status["predicted_end"]
        pool_tz_name = data.pool.timezone if data.pool else None
        tz_name = pool_tz_name or "UTC"
        try:
            tz_info = zoneinfo.ZoneInfo(tz_name)
        except ValueError, zoneinfo.ZoneInfoNotFoundError:
            tz_info = zoneinfo.ZoneInfo("UTC")
        return datetime.fromtimestamp(timestamp, tz=tz_info)
    return None


def _cycle_elapsed_time_fn(data: PoolCopData) -> float | None:
    """Get elapsed time in seconds for the current cycle."""
    if not _is_cycle_mode(data):
        return None
    if (seconds := _api_cycle_seconds(data, "current_cycle_elapsed_time")) is not None:
        return float(seconds)
    if data.cycle_status and data.cycle_status.get("elapsed_time") is not None:
        return float(data.cycle_status["elapsed_time"])
    return None


# ---------------------------------------------------------------------------
# Helper: convert HH:MM:SS to datetime today in pool timezone
# ---------------------------------------------------------------------------


def _time_str_to_time_today(time_str: str, timezone: str) -> datetime | None:
    """Convert a time string (HH:MM:SS) to a datetime object for today."""
    if not time_str or time_str == "00:00:00":
        return None

    try:
        hour, minute, second = map(int, time_str.split(":"))

        tz_info: tzinfo
        try:
            tz_info = zoneinfo.ZoneInfo(timezone)
        except ValueError, zoneinfo.ZoneInfoNotFoundError:
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

        # Handle case where the time is for tomorrow
        if result < now and hour < 12:
            result = result + timedelta(days=1)
    except ValueError, TypeError, zoneinfo.ZoneInfoNotFoundError:
        return None
    else:
        return result


def _pool_timezone(data: PoolCopData) -> str:
    """Return pool timezone string or 'UTC'."""
    return (data.pool.timezone if data.pool else None) or "UTC"


# ---------------------------------------------------------------------------
# Slug mappings for translatable enum sensors
# API returns PascalCase strings; HA translations expect snake_case keys
# ---------------------------------------------------------------------------

_RUNNING_STATUS_SLUG: dict[str, str] = {
    "Stopped": "stopped",
    "FreezeProtection": "freeze_protection",
    "ForcedMode": "forced_mode",
    "EcoPlusMode": "eco_plus_mode",
    "TimerMode": "timer_mode",
    "Manual": "manual",
    "Paused": "paused",
    "ExternalRequest": "external_request",
    "WaterLevelManagement": "water_level_management",
    "Mode24H": "mode_24h",
}

_FILTRATION_MODE_SLUG: dict[str, str] = {
    "Stop": "stop",
    "Timer": "timer",
    "EcoPlus": "eco_plus",
    "Volume": "volume",
    "Continuous": "continuous",
    "Forced24H": "forced_24h",
    "Forced48H": "forced_48h",
    "Forced72H": "forced_72h",
    "Mode24H": "mode_24h",
    "NoPump": "no_pump",
}

_VALVE_SLUG: dict[str, str] = {
    "Filter": "filter",
    "Waste": "waste",
    "Closed": "closed",
    "Backwash": "backwash",
    "Bypass": "bypass",
    "Rinse": "rinse",
}

_WATER_LEVEL_SLUG: dict[str, str] = {
    "Faulty": "faulty",
    "Low": "low",
    "Normal": "normal",
    "High": "high",
    "VeryHigh": "very_high",
}

_SPEED_SLUG: dict[str, str] = {
    "None": "none",
    **{f"Speed{n}": f"speed_{n}" for n in range(1, 9)},
}

_POOL_TYPE_SLUG: dict[str, str] = {
    "ClassicPool": "classic_pool",
    "RimflowTypeA": "rimflow_type_a",
    "RimflowTypeB": "rimflow_type_b",
    "Spa": "spa",
}

_BACKWASH_MODE_SLUG: dict[str, str] = {
    "Inhibited": "inhibited",
    "Manual": "manual",
    "Automatic": "automatic",
}

_FILTER_TYPE_SLUG: dict[str, str] = {
    "NoFilter": "no_filter",
    "Pressure": "pressure",
    "Suction": "suction",
}

_PUMP_TYPE_SLUG: dict[str, str] = {
    "NoPump": "no_pump",
    "MonoSpeedPump": "mono_speed_pump",
    "PentairIntelliFlo": "pentair_intelliflo",
    "PentairSuperFlo": "pentair_superflo",
    "HaywardEcostar": "hayward_ecostar",
    "HaywardTristar": "hayward_tristar",
    "BaduEcoTouch": "badu_ecotouch",
    "BaduEcoMotion": "badu_ecomotion",
    "ZodiacFloPro": "zodiac_flopro",
    "InvertekOptidrive": "invertek_optidrive",
    "BinaryCombination": "binary_combination",
    "DaveyProMaster": "davey_promaster",
    "ACISVIPoolMKB": "acis_vipool_mkb",
    "DABESwim": "dab_eswim",
    "AQUAGEMiSAVERplus": "aquagem_isaver_plus",
    "SACIEpoolEjoy": "saci_epool_ejoy",
    "SCHNEIDERATV21": "schneider_atv21",
}

_PH_MODE_SLUG: dict[str, str] = {
    "phMinus": "ph_minus",
    "pHPlus": "ph_plus",
    "ReadOnly": "read_only",
}

_DISINFECTANT_SLUG: dict[str, str] = {
    "ReadOnly": "read_only",
    "Chlorine": "chlorine",
    "Salt": "salt",
    "Bromine": "bromine",
    "PoolCopOcean": "poolcop_ocean",
    "DASpace": "da_space",
    "DAGen": "da_gen",
    "Aquark": "aquark",
}

_TIMER_ENABLED_OPTIONS = ["disabled", "enabled"]


def _slugify_enum(value: str | None, mapping: dict[str, str]) -> str | None:
    """Convert an API enum value to a translation slug.

    Values the API adds later are reported as unknown rather than failing
    the enum option check.
    """
    if value is None:
        return None
    return mapping.get(value)


def _enum_fn(
    getter: Callable[[PoolCopData], str | None], mapping: dict[str, str]
) -> Callable[[PoolCopData], str | None]:
    """Return a value_fn that maps an API enum value to its slug."""
    return lambda data: _slugify_enum(getter(data), mapping)


def _filtration_attr(attr: str) -> Callable[[PoolCopData], Any]:
    """Return a getter for a first-filtration settings attribute."""

    def getter(data: PoolCopData) -> Any:
        filt = _filtration(data)
        return getattr(filt, attr) if filt is not None else None

    return getter


def _speed_count(value: str | None) -> int | None:
    """Convert a 'SpeedN' number-of-speeds value to N."""
    if not value or not value.startswith("Speed"):
        return None
    return int(value[5:])


# ---------------------------------------------------------------------------
# Timer helpers for filtration timers
# ---------------------------------------------------------------------------


def _filtration_timer_enabled_fn(
    timer_index: int,
) -> Callable[[PoolCopData], str]:
    """Return value_fn that checks if a filtration timer is enabled."""

    def value_fn(data: PoolCopData) -> str:
        filt = _filtration(data)
        if filt is None or timer_index >= len(filt.timers):
            return "disabled"
        return "enabled" if filt.timers[timer_index].enabled else "disabled"

    return value_fn


def _filtration_timer_time_fn(
    timer_index: int, field: str
) -> Callable[[PoolCopData], datetime | None]:
    """Return value_fn for a filtration timer time field as datetime.

    field is 'time_on' or 'time_off'.
    """

    def value_fn(data: PoolCopData) -> datetime | None:
        filt = _filtration(data)
        if filt is None or timer_index >= len(filt.timers):
            return None
        timer = filt.timers[timer_index]
        if not timer.enabled:
            return None
        time_str = getattr(timer, field, None)
        if not time_str:
            return None
        try:
            timezone = _pool_timezone(data)
            return _time_str_to_time_today(time_str, timezone)
        except (KeyError, AttributeError, zoneinfo.ZoneInfoNotFoundError) as err:
            LOGGER.debug("Error creating timer time with timezone: %s", err)
        return None

    return value_fn


# ---------------------------------------------------------------------------
# Aux timer helpers
# ---------------------------------------------------------------------------


def _aux_timer_enabled_fn(
    aux_settings_id: str,
) -> Callable[[PoolCopData], str]:
    """Return value_fn that checks if an aux has any enabled timer."""

    def value_fn(data: PoolCopData) -> str:
        for aux in data.device.settings.auxs:
            if aux.id == aux_settings_id:
                for timer in aux.timers:
                    # Aux timers don't have an enabled flag; they are active
                    # if time_on != "00:00:00"
                    if timer.time_on and timer.time_on != "00:00:00":
                        return "enabled"
                return "disabled"
        return "disabled"

    return value_fn


def _aux_timer_time_fn(
    aux_settings_id: str, timer_index: int, field: str
) -> Callable[[PoolCopData], datetime | None]:
    """Return value_fn for an aux timer time field as datetime."""

    def value_fn(data: PoolCopData) -> datetime | None:
        for aux in data.device.settings.auxs:
            if aux.id == aux_settings_id:
                if timer_index >= len(aux.timers):
                    return None
                timer = aux.timers[timer_index]
                time_str = getattr(timer, field, None)
                if not time_str or time_str == "00:00:00":
                    return None
                try:
                    timezone = _pool_timezone(data)
                    return _time_str_to_time_today(time_str, timezone)
                except (
                    KeyError,
                    AttributeError,
                    zoneinfo.ZoneInfoNotFoundError,
                ) as err:
                    LOGGER.debug("Error creating aux timer time with timezone: %s", err)
                return None
        return None

    return value_fn


# ---------------------------------------------------------------------------
# Core sensors
# ---------------------------------------------------------------------------

SENSORS: tuple[PoolCopSensorEntityDescription, ...] = (
    PoolCopSensorEntityDescription(
        key="temperature_water",
        translation_key="temperature_water",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        unit_kind=TEMPERATURE,
        value_fn=lambda data: data.device.state.water_temperature,
    ),
    PoolCopSensorEntityDescription(
        key="temperature_air",
        translation_key="temperature_air",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        unit_kind=TEMPERATURE,
        value_fn=lambda data: data.device.state.air_temperature,
    ),
    PoolCopSensorEntityDescription(
        key="pressure",
        translation_key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.KPA,
        unit_kind=PRESSURE,
        value_fn=lambda data: _pump(data).pressure if _pump(data) is not None else None,
    ),
    PoolCopSensorEntityDescription(
        key="pH",
        translation_key="ph",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="pH",
        value_fn=lambda data: data.device.state.ph,
    ),
    PoolCopSensorEntityDescription(
        key="orp",
        translation_key="orp",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mV",
        value_fn=lambda data: data.device.state.orp,
    ),
    PoolCopSensorEntityDescription(
        key="voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: data.device.state.battery_voltage,
    ),
    PoolCopSensorEntityDescription(
        key="mains_voltage",
        translation_key="mains_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: data.device.state.mains_voltage,
    ),
    PoolCopSensorEntityDescription(
        key="salt",
        translation_key="salt",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="g/L",
        value_fn=lambda data: data.device.state.salt,
    ),
    PoolCopSensorEntityDescription(
        key="free_available_chlorine",
        translation_key="free_available_chlorine",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mg/L",
        value_fn=lambda data: data.device.state.free_available_chlorine,
    ),
    PoolCopSensorEntityDescription(
        key="free_chlorine",
        translation_key="free_chlorine",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mg/L",
        value_fn=lambda data: data.device.state.free_chlorine,
    ),
    PoolCopSensorEntityDescription(
        key="total_chlorine",
        translation_key="total_chlorine",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mg/L",
        value_fn=lambda data: data.device.state.total_chlorine,
    ),
    PoolCopSensorEntityDescription(
        key="waterlevel",
        translation_key="waterlevel",
        device_class=SensorDeviceClass.ENUM,
        options=list(_WATER_LEVEL_SLUG.values()),
        value_fn=lambda data: _slugify_enum(
            data.device.state.water_level.state, _WATER_LEVEL_SLUG
        ),
    ),
    PoolCopSensorEntityDescription(
        key="valve_position",
        translation_key="valve_position",
        device_class=SensorDeviceClass.ENUM,
        options=list(_VALVE_SLUG.values()),
        value_fn=lambda data: _slugify_enum(
            _pump(data).valve_position if _pump(data) is not None else None,
            _VALVE_SLUG,
        ),
    ),
    PoolCopSensorEntityDescription(
        key="pump_speed",
        translation_key="pump_speed",
        device_class=SensorDeviceClass.ENUM,
        options=list(_SPEED_SLUG.values()),
        value_fn=_enum_fn(
            lambda data: _pump(data).current_speed if _pump(data) is not None else None,
            _SPEED_SLUG,
        ),
    ),
    PoolCopSensorEntityDescription(
        key="running_status",
        translation_key="running_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(_RUNNING_STATUS_SLUG.values()),
        value_fn=lambda data: _slugify_enum(
            _pump(data).running_status if _pump(data) is not None else None,
            _RUNNING_STATUS_SLUG,
        ),
    ),
    PoolCopSensorEntityDescription(
        key="filtration_mode",
        translation_key="filtration_mode",
        device_class=SensorDeviceClass.ENUM,
        options=list(_FILTRATION_MODE_SLUG.values()),
        value_fn=lambda data: _slugify_enum(
            _pump(data).filtration_mode if _pump(data) is not None else None,
            _FILTRATION_MODE_SLUG,
        ),
    ),
    PoolCopSensorEntityDescription(
        key="forced_remaining",
        translation_key="forced_remaining",
        value_fn=lambda data: (
            _pump(data).forced_remaining if _pump(data) is not None else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="flow_meter_rate",
        translation_key="flow_meter_rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        unit_kind=FLOW_RATE,
        value_fn=lambda data: (
            data.device.state.flow_vis[0].flow_rate
            if data.device.state.flow_vis
            else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="last_backwash",
        translation_key="last_backwash",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: _parse_datetime(
            data.device.history.last_backwash_date, _pool_timezone(data)
        ),
    ),
    PoolCopSensorEntityDescription(
        key="last_refill",
        translation_key="last_refill",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: _parse_datetime(
            data.device.history.last_refill_date, _pool_timezone(data)
        ),
    ),
    PoolCopSensorEntityDescription(
        key="last_ph_measure",
        translation_key="last_ph_measure",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: _parse_datetime(
            data.device.history.last_ph_measure_date, _pool_timezone(data)
        ),
    ),
    PoolCopSensorEntityDescription(
        key="ph_last_injection_duration",
        translation_key="ph_last_injection_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: _parse_duration_seconds(
            data.device.history.ph_last_injection_duration
        ),
    ),
    PoolCopSensorEntityDescription(
        key="disinfection_last_injection_duration",
        translation_key="disinfection_last_injection_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: _parse_duration_seconds(
            data.device.history.disinfection_last_injection_duration
        ),
    ),
    # Cycle tracking sensors
    PoolCopSensorEntityDescription(
        key="cycle_elapsed_time",
        translation_key="cycle_elapsed_time",
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
        translation_key="cycle_remaining_time",
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
        translation_key="cycle_predicted_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_cycle_end_time_fn,
    ),
    PoolCopSensorEntityDescription(
        key="pool_nickname",
        translation_key="pool_nickname",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.pool.nickname if data.pool else None,
    ),
    # API-provided cycle elapsed/remaining time (from filtration settings)
    PoolCopSensorEntityDescription(
        key="api_cycle_elapsed_time",
        translation_key="api_cycle_elapsed_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: _parse_duration_seconds(
            _filtration(data).current_cycle_elapsed_time
            if _filtration(data) is not None
            else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="api_cycle_remaining_time",
        translation_key="api_cycle_remaining_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: _parse_duration_seconds(
            _filtration(data).current_cycle_remaining_time
            if _filtration(data) is not None
            else None
        ),
    ),
    # Diagnostic: firmware and model
    PoolCopSensorEntityDescription(
        key="firmware_version",
        translation_key="firmware_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.version_info.poolcop_version or None,
    ),
    PoolCopSensorEntityDescription(
        key="device_model",
        translation_key="device_model",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.version_info.model or None,
    ),
    PoolCopSensorEntityDescription(
        key="os_version",
        translation_key="os_version",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.version_info.os_version or None,
    ),
)

# ---------------------------------------------------------------------------
# Settings sensors
# ---------------------------------------------------------------------------

SETTINGS_SENSORS: tuple[PoolCopSensorEntityDescription, ...] = (
    # Pool settings
    PoolCopSensorEntityDescription(
        key="pool_volume",
        translation_key="pool_volume",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        unit_kind=VOLUME,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.settings.pool.volume,
    ),
    PoolCopSensorEntityDescription(
        key="pool_turnover",
        translation_key="pool_turnover",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="x/day",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.settings.pool.turnover_per_day,
    ),
    PoolCopSensorEntityDescription(
        key="pool_cover_reduction",
        translation_key="pool_cover_reduction",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            _filtration(data).cover_filtration_reduction
            if _filtration(data) is not None
            else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="pool_type",
        translation_key="pool_type",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_POOL_TYPE_SLUG.values()),
        value_fn=_enum_fn(lambda data: data.device.settings.pool.type, _POOL_TYPE_SLUG),
    ),
    # Filter settings
    PoolCopSensorEntityDescription(
        key="filter_pressure",
        translation_key="filter_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.KPA,
        unit_kind=PRESSURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            _filtration(data).backwash_pressure
            if _filtration(data) is not None
            else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="filter_backwash_duration",
        translation_key="filter_backwash_duration",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: _setting_seconds(
            _filtration_attr("backwash_duration")(data)
        ),
    ),
    PoolCopSensorEntityDescription(
        key="filter_rinse_duration",
        translation_key="filter_rinse_duration",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: _setting_seconds(
            _filtration_attr("rinse_duration")(data)
        ),
    ),
    PoolCopSensorEntityDescription(
        key="filter_max_days",
        translation_key="filter_max_days",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda data: _setting_days(
            _filtration_attr("max_interval_between_backwash")(data)
        ),
    ),
    PoolCopSensorEntityDescription(
        key="filter_timer_mode",
        translation_key="filter_timer_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_FILTRATION_MODE_SLUG.values()),
        value_fn=_enum_fn(_filtration_attr("filtration_mode"), _FILTRATION_MODE_SLUG),
    ),
    PoolCopSensorEntityDescription(
        key="filter_backwash_mode",
        translation_key="filter_backwash_mode",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_BACKWASH_MODE_SLUG.values()),
        value_fn=_enum_fn(_filtration_attr("backwash_mode"), _BACKWASH_MODE_SLUG),
    ),
    PoolCopSensorEntityDescription(
        key="filter_backwash_time",
        translation_key="filter_backwash_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            _filtration(data).backwash_time if _filtration(data) is not None else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="filter_type",
        translation_key="filter_type",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_FILTER_TYPE_SLUG.values()),
        value_fn=_enum_fn(_filtration_attr("filter_type"), _FILTER_TYPE_SLUG),
    ),
    # Pump settings
    PoolCopSensorEntityDescription(
        key="pump_nb_speeds",
        translation_key="pump_nb_speeds",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _speed_count(_filtration_attr("nb_speeds")(data)),
    ),
    PoolCopSensorEntityDescription(
        key="pump_pressure_low",
        translation_key="pump_pressure_low",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.KPA,
        unit_kind=PRESSURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            _filtration(data).low_pressure if _filtration(data) is not None else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="pump_pressure_alarm",
        translation_key="pump_pressure_alarm",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.KPA,
        unit_kind=PRESSURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            _filtration(data).alarm_pressure if _filtration(data) is not None else None
        ),
    ),
    PoolCopSensorEntityDescription(
        key="pump_type",
        translation_key="pump_type",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_PUMP_TYPE_SLUG.values()),
        value_fn=_enum_fn(_filtration_attr("pump_type"), _PUMP_TYPE_SLUG),
    ),
    PoolCopSensorEntityDescription(
        key="pump_flowrate",
        translation_key="pump_flowrate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        unit_kind=FLOW_RATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.settings.pool.estimated_flowrate,
    ),
    PoolCopSensorEntityDescription(
        key="pump_speed_cycle1",
        translation_key="pump_speed_cycle1",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_SPEED_SLUG.values()),
        value_fn=_enum_fn(_filtration_attr("speed_cycle1"), _SPEED_SLUG),
    ),
    PoolCopSensorEntityDescription(
        key="pump_speed_cycle2",
        translation_key="pump_speed_cycle2",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_SPEED_SLUG.values()),
        value_fn=_enum_fn(_filtration_attr("speed_cycle2"), _SPEED_SLUG),
    ),
    PoolCopSensorEntityDescription(
        key="pump_speed_backwash",
        translation_key="pump_speed_backwash",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_SPEED_SLUG.values()),
        value_fn=_enum_fn(_filtration_attr("speed_backwash"), _SPEED_SLUG),
    ),
    PoolCopSensorEntityDescription(
        key="pump_speed_24h",
        translation_key="pump_speed_24h",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_SPEED_SLUG.values()),
        value_fn=_enum_fn(_filtration_attr("speed_24"), _SPEED_SLUG),
    ),
    PoolCopSensorEntityDescription(
        key="pump_speed_cover",
        translation_key="pump_speed_cover",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_SPEED_SLUG.values()),
        value_fn=_enum_fn(_filtration_attr("cover_filtration_speed"), _SPEED_SLUG),
    ),
    # pH settings
    PoolCopSensorEntityDescription(
        key="ph_set_point",
        translation_key="ph_set_point",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="pH",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.settings.ph.set_point,
    ),
    PoolCopSensorEntityDescription(
        key="ph_type",
        translation_key="ph_type",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_PH_MODE_SLUG.values()),
        value_fn=_enum_fn(lambda data: data.device.settings.ph.mode, _PH_MODE_SLUG),
    ),
    PoolCopSensorEntityDescription(
        key="ph_dosing_time",
        translation_key="ph_dosing_time",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: _setting_seconds(
            data.device.settings.ph.max_dosing_duration
        ),
    ),
    PoolCopSensorEntityDescription(
        key="ph_low_threshold",
        translation_key="ph_low_threshold",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="pH",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.settings.ph.low_value,
    ),
    PoolCopSensorEntityDescription(
        key="ph_high_threshold",
        translation_key="ph_high_threshold",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="pH",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.settings.ph.high_value,
    ),
    # ORP / Disinfection settings
    PoolCopSensorEntityDescription(
        key="orp_set_point",
        translation_key="orp_set_point",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mV",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.settings.disinfection.orp.set_point,
    ),
    PoolCopSensorEntityDescription(
        key="orp_disinfectant",
        translation_key="orp_disinfectant",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_DISINFECTANT_SLUG.values()),
        value_fn=_enum_fn(
            lambda data: data.device.settings.disinfection.disinfectant_type,
            _DISINFECTANT_SLUG,
        ),
    ),
    PoolCopSensorEntityDescription(
        key="orp_temperature_shutdown",
        translation_key="orp_temperature_shutdown",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        unit_kind=TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.device.settings.disinfection.low_shutdown_temperature
        ),
    ),
    # Water level settings
    PoolCopSensorEntityDescription(
        key="waterlevel_max_duration",
        translation_key="waterlevel_max_duration",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: _setting_seconds(
            data.device.settings.water_level.max_fill_duration
        ),
    ),
    PoolCopSensorEntityDescription(
        key="waterlevel_draining_duration",
        translation_key="waterlevel_draining_duration",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: _setting_seconds(
            data.device.settings.water_level.draining_duration
        ),
    ),
    PoolCopSensorEntityDescription(
        key="waterlevel_set_point",
        translation_key="waterlevel_set_point",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=list(_WATER_LEVEL_SLUG.values()),
        value_fn=_enum_fn(
            lambda data: data.device.settings.water_level.set_point,
            _WATER_LEVEL_SLUG,
        ),
    ),
)

# ---------------------------------------------------------------------------
# Timer sensors (filtration cycle timers)
# ---------------------------------------------------------------------------

TIMER_SENSORS: tuple[PoolCopSensorEntityDescription, ...] = (
    # Cycle 1 timer
    PoolCopSensorEntityDescription(
        key="cycle1_enabled",
        translation_key="cycle1_enabled",
        device_class=SensorDeviceClass.ENUM,
        options=_TIMER_ENABLED_OPTIONS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_filtration_timer_enabled_fn(0),
    ),
    PoolCopSensorEntityDescription(
        key="cycle1_start_time",
        translation_key="cycle1_start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_filtration_timer_time_fn(0, "time_on"),
    ),
    PoolCopSensorEntityDescription(
        key="cycle1_stop_time",
        translation_key="cycle1_stop_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_filtration_timer_time_fn(0, "time_off"),
    ),
    # Cycle 2 timer
    PoolCopSensorEntityDescription(
        key="cycle2_enabled",
        translation_key="cycle2_enabled",
        device_class=SensorDeviceClass.ENUM,
        options=_TIMER_ENABLED_OPTIONS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_filtration_timer_enabled_fn(1),
    ),
    PoolCopSensorEntityDescription(
        key="cycle2_start_time",
        translation_key="cycle2_start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_filtration_timer_time_fn(1, "time_on"),
    ),
    PoolCopSensorEntityDescription(
        key="cycle2_stop_time",
        translation_key="cycle2_stop_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_filtration_timer_time_fn(1, "time_off"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolCopConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PoolCop sensors based on a config entry."""
    coordinator = entry.runtime_data

    # Add standard sensors (skip uninstalled components)
    entities: list[PoolCopSensorEntity] = [
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

    # Add timer sensors (cycle1, cycle2)
    entities.extend(
        PoolCopSensorEntity(coordinator=coordinator, description=description)
        for description in TIMER_SENSORS
    )

    # Add dynamic aux timer sensors from settings aux array.
    # Skip fixed-function aux (firmware-managed, not user-scheduled).
    for aux in coordinator.data.device.settings.auxs:
        if not aux.timers:
            continue
        if aux.is_reserved or aux.label in AUX_FIXED_FUNCTION_LABELS:
            continue
        label = aux_display_name(aux.label, aux.friendly_name, aux.aux_channel)

        entities.append(
            PoolCopSensorEntity(
                coordinator=coordinator,
                description=PoolCopSensorEntityDescription(
                    key=f"aux{aux.aux_channel}_enabled",
                    translation_key="aux_timer_enabled",
                    translation_placeholders={"aux": label},
                    device_class=SensorDeviceClass.ENUM,
                    options=_TIMER_ENABLED_OPTIONS,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    value_fn=_aux_timer_enabled_fn(aux.id),
                ),
            )
        )
        # Expose start time for the first timer of each aux
        entities.append(
            PoolCopSensorEntity(
                coordinator=coordinator,
                description=PoolCopSensorEntityDescription(
                    key=f"aux{aux.aux_channel}_start_time",
                    translation_key="aux_timer_start_time",
                    translation_placeholders={"aux": label},
                    device_class=SensorDeviceClass.TIMESTAMP,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    value_fn=_aux_timer_time_fn(aux.id, 0, "time_on"),
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
    def suggested_unit_of_measurement(self) -> str | None:
        """Suggest the unit chosen in the account's PoolCop app preferences."""
        kind = self.entity_description.unit_kind
        if kind is not None and kind in self.coordinator.api.units:
            return ha_unit(self.coordinator.api.units, kind)
        return super().suggested_unit_of_measurement


class FlowRateSensor(PoolCopSensorEntity):
    """Flow rate sensor based on pump state, speed, and valve position."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR
    _attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, *, coordinator: PoolCopDataUpdateCoordinator) -> None:
        """Initialize the flow rate sensor."""
        description = PoolCopSensorEntityDescription(
            key="pump_flow_rate",
            translation_key="pump_flow_rate",
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

    def __init__(self, *, coordinator: PoolCopDataUpdateCoordinator) -> None:
        """Initialize the daily filtration volume sensor."""
        description = PoolCopSensorEntityDescription(
            key="daily_filtration_volume",
            translation_key="daily_filtration_volume",
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

    def __init__(self, *, coordinator: PoolCopDataUpdateCoordinator) -> None:
        """Initialize the daily turnover sensor."""
        description = PoolCopSensorEntityDescription(
            key="daily_turnovers",
            translation_key="daily_turnovers",
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

    def __init__(self, *, coordinator: PoolCopDataUpdateCoordinator) -> None:
        """Initialize the planned remaining volume sensor."""
        description = PoolCopSensorEntityDescription(
            key="planned_remaining_volume",
            translation_key="planned_remaining_volume",
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

    def __init__(self, *, coordinator: PoolCopDataUpdateCoordinator) -> None:
        """Initialize the planned remaining turnover sensor."""
        description = PoolCopSensorEntityDescription(
            key="planned_remaining_turnovers",
            translation_key="planned_remaining_turnovers",
            value_fn=lambda data: None,
        )
        super().__init__(coordinator=coordinator, description=description)

    @property
    def native_value(self) -> float | None:
        """Return the planned remaining turnovers."""
        return self.coordinator.planned_remaining_turnovers
