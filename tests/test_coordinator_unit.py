"""Unit tests for PoolCop coordinator logic (no HA integration setup)."""

import time
from copy import deepcopy
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiopoolcop import Pool, PoolCopDevice

from custom_components.poolcop.coordinator import (
    DEFAULT_CYCLE_DURATIONS,
    MODE_NAME_TO_ID,
    SPEED_NAME_TO_LEVEL,
    VALVE_NAME_TO_ID,
    PoolCopData,
    PoolCopDataUpdateCoordinator,
)

from conftest import MOCK_DEVICE_RESPONSE, MOCK_POOL_RESPONSE


def _make_device(overrides: dict | None = None) -> PoolCopDevice:
    """Build a PoolCopDevice with optional state overrides."""
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    if overrides:
        for key, value in overrides.items():
            parts = key.split(".")
            target = data
            for part in parts[:-1]:
                target = target[part]
            target[parts[-1]] = value
    return PoolCopDevice.from_dict(data)


def _make_pool() -> Pool:
    return Pool.from_dict(deepcopy(MOCK_POOL_RESPONSE))


def _make_coordinator(hass, config_entry, api=None) -> PoolCopDataUpdateCoordinator:
    """Create a coordinator with mocked hass and config_entry."""
    if api is None:
        api = AsyncMock()
    coord = PoolCopDataUpdateCoordinator(hass, api, 2478, config_entry)
    return coord


# ------------------------------------------------------------------
# _pump, _mode_id, _speed_level, _valve_id helpers
# ------------------------------------------------------------------


async def test_pump_returns_first(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = _make_device()
    pump = coord._pump(device)
    assert pump is not None
    assert pump.pump_state is True


async def test_pump_returns_none_no_pumps(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = PoolCopDevice.from_dict({"id": 1, "state": {}})
    assert coord._pump(device) is None


async def test_mode_id_timer(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = _make_device()
    assert coord._mode_id(device) == MODE_NAME_TO_ID["TimerMode"]


async def test_mode_id_no_pumps(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = PoolCopDevice.from_dict({"id": 1, "state": {}})
    assert coord._mode_id(device) is None


async def test_speed_level(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = _make_device()
    assert coord._speed_level(device) == SPEED_NAME_TO_LEVEL["Speed1"]


async def test_speed_level_no_pumps(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = PoolCopDevice.from_dict({"id": 1, "state": {}})
    assert coord._speed_level(device) is None


async def test_valve_id_filter(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = _make_device()
    assert coord._valve_id(device) == VALVE_NAME_TO_ID["Filter"]


async def test_valve_id_no_pumps(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = PoolCopDevice.from_dict({"id": 1, "state": {}})
    assert coord._valve_id(device) is None


# ------------------------------------------------------------------
# _pool_timezone
# ------------------------------------------------------------------


async def test_pool_timezone_valid(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord._pool = _make_pool()
    tz = coord._pool_timezone()
    assert tz is not None
    assert str(tz) == "Europe/Amsterdam"


async def test_pool_timezone_invalid(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    pool_data = deepcopy(MOCK_POOL_RESPONSE)
    pool_data["timezone"] = "Invalid/Zone"
    coord._pool = Pool.from_dict(pool_data)
    tz = coord._pool_timezone()
    assert tz is None


async def test_pool_timezone_no_pool(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord._pool = None
    assert coord._pool_timezone() is None


# ------------------------------------------------------------------
# Flow rate / volume
# ------------------------------------------------------------------


async def test_get_current_flow_rate_pump_on_speed1(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = PoolCopData(device=_make_device())
    rate = coord.get_current_flow_rate()
    assert rate == 10.0  # Speed1 -> CONF_FLOW_RATE_1 = 10.0


async def test_get_current_flow_rate_pump_off(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["state"]["pumpsInfo"][0]["pumpState"] = False
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    assert coord.get_current_flow_rate() == 0.0


async def test_get_current_flow_rate_no_data(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    assert coord.get_current_flow_rate() == 0.0


async def test_get_current_flow_rate_no_pumps(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = PoolCopDevice.from_dict({"id": 1, "state": {}})
    coord.data = PoolCopData(device=device)
    assert coord.get_current_flow_rate() == 0.0


async def test_get_current_flow_rate_waste_valve(mock_config_entry):
    """Waste valve position (id=1) returns 0 — water not flowing through filter."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["state"]["pumpsInfo"][0]["valvePosition"] = "Waste"
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    assert coord.get_current_flow_rate() == 0.0


async def test_get_current_flow_rate_speed_none(mock_config_entry):
    """Speed=None (0) returns 0."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["state"]["pumpsInfo"][0]["pumpCurrentSpeed"] = "None"
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    assert coord.get_current_flow_rate() == 0.0


# ------------------------------------------------------------------
# _update_daily_volume
# ------------------------------------------------------------------


async def test_update_daily_volume_accumulates(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = PoolCopData(device=_make_device())

    # First call sets _last_flow_update
    coord._update_daily_volume()
    assert coord._daily_volume == 0.0

    # Simulate 60 seconds passing with flow rate 10 m3/h
    coord._last_flow_update = time.monotonic() - 60
    coord._update_daily_volume()
    expected = 10.0 * (60 / 3600.0)
    assert coord._daily_volume == pytest.approx(expected, abs=0.01)


async def test_update_daily_volume_resets_at_midnight(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = PoolCopData(device=_make_device())

    coord._daily_volume = 50.0
    coord._daily_volume_date = "1999-01-01"
    coord._last_flow_update = time.monotonic() - 30

    coord._update_daily_volume()
    # Should have reset to near 0 (just the 30s accumulation)
    assert coord._daily_volume < 1.0


async def test_update_daily_volume_skip_large_gap(mock_config_entry):
    """Gaps >10 min are skipped (restart scenario)."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = PoolCopData(device=_make_device())

    coord._daily_volume = 0.0
    coord._daily_volume_date = datetime.now().strftime("%Y-%m-%d")
    coord._last_flow_update = time.monotonic() - 700  # 11+ minutes

    coord._update_daily_volume()
    assert coord._daily_volume == 0.0


# ------------------------------------------------------------------
# _get_remaining_cycle_seconds
# ------------------------------------------------------------------


async def test_get_remaining_cycle_seconds_no_data(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = None
    assert coord._get_remaining_cycle_seconds(0) == 0.0


async def test_get_remaining_cycle_seconds_no_filtrations(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = PoolCopDevice.from_dict({"id": 1, "state": {}, "settings": {}})
    coord.data = PoolCopData(device=device)
    assert coord._get_remaining_cycle_seconds(0) == 0.0


async def test_get_remaining_cycle_seconds_timer_out_of_range(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = PoolCopData(device=_make_device())
    assert coord._get_remaining_cycle_seconds(5) == 0.0


async def test_get_remaining_cycle_seconds_zero_times(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["settings"]["filtrations"][0]["timers"][0]["timeOn"] = "00:00:00"
    data["settings"]["filtrations"][0]["timers"][0]["timeOff"] = "00:00:00"
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    assert coord._get_remaining_cycle_seconds(0) == 0.0


async def test_get_remaining_cycle_seconds_invalid_time(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["settings"]["filtrations"][0]["timers"][0]["timeOn"] = "invalid"
    data["settings"]["filtrations"][0]["timers"][0]["timeOff"] = "also-invalid"
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    assert coord._get_remaining_cycle_seconds(0) == 0.0


async def test_get_remaining_cycle_seconds_stop_before_start(mock_config_entry):
    """stop <= start returns 0."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["settings"]["filtrations"][0]["timers"][0]["timeOn"] = "20:00:00"
    data["settings"]["filtrations"][0]["timers"][0]["timeOff"] = "10:00:00"
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    assert coord._get_remaining_cycle_seconds(0) == 0.0


async def test_get_remaining_cycle_seconds_disabled_timer(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["settings"]["filtrations"][0]["timers"][0]["enabled"] = False
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    assert coord._get_remaining_cycle_seconds(0) == 0.0


# ------------------------------------------------------------------
# _get_flow_rate_for_speed
# ------------------------------------------------------------------


async def test_get_flow_rate_for_speed_known(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = PoolCopData(device=_make_device())
    assert coord._get_flow_rate_for_speed(2) == 15.0


async def test_get_flow_rate_for_speed_fallback_to_current(mock_config_entry):
    """Unknown speed falls back to current pump speed."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = PoolCopData(device=_make_device())
    assert coord._get_flow_rate_for_speed(99) == 10.0  # falls back to Speed1 current


async def test_get_flow_rate_for_speed_none(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = PoolCopData(device=_make_device())
    result = coord._get_flow_rate_for_speed(None)
    assert result == 10.0  # fallback to current pump speed


async def test_get_flow_rate_for_speed_last_fallback(mock_config_entry):
    """No data at all falls back to speed 1."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = None
    assert coord._get_flow_rate_for_speed(None) == 10.0


# ------------------------------------------------------------------
# planned_remaining_volume
# ------------------------------------------------------------------


async def test_planned_remaining_volume_no_data(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = None
    assert coord.planned_remaining_volume == 0.0


async def test_planned_remaining_volume_stopped(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["state"]["pumpsInfo"][0]["runningStatus"] = "Stopped"
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    assert coord.planned_remaining_volume == 0.0


async def test_planned_remaining_volume_forced_mode(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["state"]["pumpsInfo"][0]["runningStatus"] = "ForcedMode"
    data["state"]["pumpsInfo"][0]["pumpForcedRemaining"] = "02:30:00"
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    vol = coord.planned_remaining_volume
    assert vol > 0


async def test_planned_remaining_volume_forced_zero(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["state"]["pumpsInfo"][0]["runningStatus"] = "ForcedMode"
    data["state"]["pumpsInfo"][0]["pumpForcedRemaining"] = "00:00:00"
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    assert coord.planned_remaining_volume == 0.0


async def test_planned_remaining_volume_forced_invalid(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["state"]["pumpsInfo"][0]["runningStatus"] = "ForcedMode"
    data["state"]["pumpsInfo"][0]["pumpForcedRemaining"] = "invalid"
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    assert coord.planned_remaining_volume == 0.0


async def test_planned_remaining_volume_continuous(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["state"]["pumpsInfo"][0]["runningStatus"] = "TimerMode"
    data["settings"]["filtrations"][0]["filtrationMode"] = "Continuous24"
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    coord._pool = _make_pool()
    vol = coord.planned_remaining_volume
    assert vol >= 0


async def test_planned_remaining_volume_mode24h(mock_config_entry):
    """Mode24H (op_mode=9) uses remaining hours volume."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["state"]["pumpsInfo"][0]["runningStatus"] = "Mode24H"
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    coord._pool = _make_pool()
    vol = coord.planned_remaining_volume
    assert vol >= 0


async def test_planned_remaining_volume_eco_plus(mock_config_entry):
    """EcoPlusMode uses cycle timers."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["state"]["pumpsInfo"][0]["runningStatus"] = "EcoPlusMode"
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    coord._pool = _make_pool()
    vol = coord.planned_remaining_volume
    assert vol >= 0


async def test_planned_remaining_volume_timer_mode(mock_config_entry):
    """TimerMode (op_mode=4) uses cycle timers."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = PoolCopData(device=_make_device())
    coord._pool = _make_pool()
    vol = coord.planned_remaining_volume
    assert vol >= 0


async def test_planned_remaining_volume_no_mode(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = PoolCopDevice.from_dict({"id": 1, "state": {}})
    coord.data = PoolCopData(device=device)
    assert coord.planned_remaining_volume == 0.0


async def test_planned_remaining_volume_unknown_mode(mock_config_entry):
    """Unknown running status falls to return 0.0 at end of method."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["state"]["pumpsInfo"][0]["runningStatus"] = "BrandNewMode"
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    assert coord.planned_remaining_volume == 0.0


# ------------------------------------------------------------------
# _remaining_hours_volume
# ------------------------------------------------------------------


async def test_remaining_hours_volume(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = PoolCopData(device=_make_device())
    coord._pool = _make_pool()
    vol = coord._remaining_hours_volume()
    assert vol >= 0


# ------------------------------------------------------------------
# planned_remaining_turnovers / daily_volume / daily_turnovers
# ------------------------------------------------------------------


async def test_planned_remaining_turnovers_no_data(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = None
    assert coord.planned_remaining_turnovers is None


async def test_planned_remaining_turnovers_zero_volume(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["settings"]["pool"]["volume"] = 0
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    assert coord.planned_remaining_turnovers is None


async def test_daily_volume(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord._daily_volume = 12.3456
    assert coord.daily_volume == 12.346


async def test_daily_turnovers(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = PoolCopData(device=_make_device())
    coord._daily_volume = 77.0  # == pool volume
    assert coord.daily_turnovers == 1.0


async def test_daily_turnovers_no_data(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    assert coord.daily_turnovers is None


async def test_daily_turnovers_zero_pool_volume(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["settings"]["pool"]["volume"] = 0
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    assert coord.daily_turnovers is None


# ------------------------------------------------------------------
# Cycle tracking
# ------------------------------------------------------------------


async def test_update_cycle_tracking_no_pumps(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = PoolCopDevice.from_dict({"id": 1, "state": {}})
    result = coord._update_cycle_tracking(device)
    assert result["predicted_end"] is None
    assert result["elapsed_time"] is None


async def test_update_cycle_tracking_first_call(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = _make_device()
    result = coord._update_cycle_tracking(device)
    assert coord._last_operation_mode == MODE_NAME_TO_ID["TimerMode"]
    assert result["previous_mode"] is None


async def test_update_cycle_tracking_mode_transition(mock_config_entry):
    """Transition from TimerMode to ForcedMode records duration."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)

    # First call: set initial mode to TimerMode
    device_timer = _make_device()
    coord._update_cycle_tracking(device_timer)
    assert coord._last_operation_mode == 4  # TimerMode

    # Simulate time passing
    coord._current_cycle_start = time.time() - 120

    # Second call: transition to ForcedMode
    data2 = deepcopy(MOCK_DEVICE_RESPONSE)
    data2["state"]["pumpsInfo"][0]["runningStatus"] = "ForcedMode"
    device_forced = PoolCopDevice.from_dict(data2)
    result = coord._update_cycle_tracking(device_forced)

    assert coord._last_operation_mode == 2  # ForcedMode
    assert result["previous_mode"] == 4  # was TimerMode
    assert len(coord._cycle_transitions) == 1


async def test_update_cycle_tracking_elapsed_and_predicted(mock_config_entry):
    """Running in a predictable mode shows elapsed + predicted end."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord._last_operation_mode = 4  # TimerMode
    coord._current_cycle_start = time.time() - 60

    device = _make_device()
    result = coord._update_cycle_tracking(device)

    assert result["elapsed_time"] is not None
    assert result["elapsed_time"] > 50
    assert result["remaining_time"] is not None
    assert result["predicted_end"] is not None


async def test_update_cycle_tracking_transition_trims_list(mock_config_entry):
    """Transition list is trimmed to 20 entries."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)

    # Pre-fill with 20 transitions
    coord._cycle_transitions = [{"from_mode": i, "to_mode": i + 1} for i in range(20)]
    coord._last_operation_mode = 0
    coord._current_cycle_start = time.time() - 100

    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["state"]["pumpsInfo"][0]["runningStatus"] = "ForcedMode"
    device = PoolCopDevice.from_dict(data)
    coord._update_cycle_tracking(device)

    assert len(coord._cycle_transitions) <= 20


# ------------------------------------------------------------------
# _seed_cycle_durations_from_settings
# ------------------------------------------------------------------


async def test_seed_cycle_durations_from_settings(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = _make_device()
    coord._seed_cycle_durations_from_settings(device)
    # Backwash duration "00:02:30" = 150 seconds, should override default 600
    assert coord._cycle_durations[2] == 150
    # Rinse duration "00:00:20" = 20 seconds, should override default 300
    assert coord._cycle_durations[5] == 20


async def test_seed_cycle_durations_no_filtrations(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = PoolCopDevice.from_dict({"id": 1, "state": {}, "settings": {}})
    coord._seed_cycle_durations_from_settings(device)
    assert coord._cycle_durations == dict(DEFAULT_CYCLE_DURATIONS)


async def test_seed_cycle_durations_zero_time(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["settings"]["filtrations"][0]["backwashDuration"] = "00:00:00"
    data["settings"]["filtrations"][0]["rinseDuration"] = "00:00:00"
    device = PoolCopDevice.from_dict(data)
    coord._seed_cycle_durations_from_settings(device)
    # Should not override defaults
    assert coord._cycle_durations[2] == DEFAULT_CYCLE_DURATIONS[2]
    assert coord._cycle_durations[5] == DEFAULT_CYCLE_DURATIONS[5]


async def test_seed_cycle_durations_invalid_time(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["settings"]["filtrations"][0]["backwashDuration"] = "invalid"
    device = PoolCopDevice.from_dict(data)
    coord._seed_cycle_durations_from_settings(device)
    assert coord._cycle_durations[2] == DEFAULT_CYCLE_DURATIONS[2]


async def test_seed_cycle_durations_already_learned(mock_config_entry):
    """Already-learned durations are not overwritten by settings."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord._cycle_durations[2] = 999  # already learned
    device = _make_device()
    coord._seed_cycle_durations_from_settings(device)
    assert coord._cycle_durations[2] == 999


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------


async def test_save_and_load_learned_data(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord._daily_volume = 5.5
    coord._daily_volume_date = datetime.now().strftime("%Y-%m-%d")
    coord.flow_rates = {1: 12.0}

    saved_data = {}

    async def mock_save(data):
        saved_data.update(data)

    async def mock_load():
        return saved_data if saved_data else None

    coord._store = MagicMock()
    coord._store.async_save = mock_save
    coord._store.async_load = mock_load

    await coord.async_save_learned_data()
    assert "cycle_durations" in saved_data

    # Reset state
    coord._daily_volume = 0
    coord.flow_rates = {}

    await coord.async_load_learned_data()
    assert coord._daily_volume == 5.5
    assert coord.flow_rates[1] == 12.0


async def test_load_learned_data_stale_date(mock_config_entry):
    """Daily volume from a different day is not restored."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)

    async def mock_load():
        return {
            "daily_volume": 99.0,
            "daily_volume_date": "1999-01-01",
            "cycle_durations": {},
            "flow_rates": {},
        }

    coord._store = MagicMock()
    coord._store.async_load = mock_load

    await coord.async_load_learned_data()
    assert coord._daily_volume == 0.0


async def test_load_learned_data_none(mock_config_entry):
    """No stored data is a no-op."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)

    async def mock_load():
        return None

    coord._store = MagicMock()
    coord._store.async_load = mock_load

    await coord.async_load_learned_data()
    assert coord._daily_volume == 0.0


# ------------------------------------------------------------------
# Command methods
# ------------------------------------------------------------------


async def test_set_pump(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    api = AsyncMock()
    coord = _make_coordinator(hass, mock_config_entry, api)
    await coord.set_pump(on=True)
    api.set_pump.assert_called_once_with(2478, on=True)


async def test_set_pump_speed(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    api = AsyncMock()
    coord = _make_coordinator(hass, mock_config_entry, api)
    await coord.set_pump_speed("Speed3")
    api.set_pump_speed.assert_called_once_with(2478, "Speed3")


async def test_set_valve_position(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    api = AsyncMock()
    coord = _make_coordinator(hass, mock_config_entry, api)
    await coord.set_valve_position("Backwash")
    api.set_valve_position.assert_called_once_with(2478, "Backwash")


async def test_clear_alarm(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    api = AsyncMock()
    coord = _make_coordinator(hass, mock_config_entry, api)
    await coord.clear_alarm("PressureLow")
    api.clear_alarm.assert_called_once_with(2478, "PressureLow")


async def test_clear_all_alarms(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    api = AsyncMock()
    coord = _make_coordinator(hass, mock_config_entry, api)
    await coord.clear_all_alarms()
    api.clear_all_alarms.assert_called_once_with(2478)


async def test_set_auxiliary(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    api = AsyncMock()
    coord = _make_coordinator(hass, mock_config_entry, api)
    await coord.set_auxiliary("None", 4, on=True)
    api.set_auxiliary.assert_called_once_with(2478, "None", 4, on=True)


async def test_set_forced_filtration(mock_config_entry):
    hass = MagicMock()
    hass.data = {}
    api = AsyncMock()
    coord = _make_coordinator(hass, mock_config_entry, api)
    await coord.set_forced_filtration("Forced24H")
    api.set_pump_forced.assert_called_once_with(2478, "Forced24H")


# ------------------------------------------------------------------
# Time-dependent _get_remaining_cycle_seconds (lines 314-318)
# ------------------------------------------------------------------


async def test_get_remaining_cycle_seconds_now_after_stop(mock_config_entry):
    """now >= stop_dt returns 0 (cycle already ended)."""
    from datetime import datetime as dt
    from unittest.mock import patch as _patch

    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    # Timer 2: timeOn=08:00, timeOff=21:59 — set "now" to after stop
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    coord._pool = _make_pool()

    fake_now = dt(2026, 5, 25, 23, 0, 0, tzinfo=coord._pool_timezone())
    with _patch("custom_components.poolcop.coordinator.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: dt(*a, **kw)
        result = coord._get_remaining_cycle_seconds(1)
    assert result == 0.0


async def test_get_remaining_cycle_seconds_now_before_start(mock_config_entry):
    """now <= start_dt returns full cycle duration."""
    from datetime import datetime as dt
    from unittest.mock import patch as _patch

    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    coord._pool = _make_pool()

    # Timer 2: timeOn=08:00:00, timeOff=21:59:00. Set now to 06:00 (before start)
    fake_now = dt(2026, 5, 25, 6, 0, 0, tzinfo=coord._pool_timezone())
    with _patch("custom_components.poolcop.coordinator.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: dt(*a, **kw)
        result = coord._get_remaining_cycle_seconds(1)
    # Full duration: 21:59 - 08:00 = 13h59m = 50340 seconds
    assert result == 50340.0


# ------------------------------------------------------------------
# planned_remaining_volume final fallback (line 406)
# ------------------------------------------------------------------


async def test_planned_remaining_volume_unmapped_mode(mock_config_entry):
    """A mode_id that passes all checks still returns 0.0 from final fallback."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = PoolCopData(device=_make_device())
    coord._pool = _make_pool()

    # Patch _mode_id to return a mode not handled by any branch (e.g. 99)
    with patch.object(coord, "_mode_id", return_value=99):
        result = coord.planned_remaining_volume
    assert result == 0.0


# ------------------------------------------------------------------
# _remaining_hours_volume exception handler (lines 419-420)
# ------------------------------------------------------------------


async def test_remaining_hours_volume_exception(mock_config_entry):
    """Exception in datetime calculation returns 0.0."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = PoolCopData(device=_make_device())

    with patch("custom_components.poolcop.coordinator.datetime") as mock_dt:
        mock_dt.now.side_effect = OverflowError("boom")
        result = coord._remaining_hours_volume()
    assert result == 0.0


# ------------------------------------------------------------------
# _update_cycle_tracking exception handler (lines 538-540)
# ------------------------------------------------------------------


async def test_update_cycle_tracking_key_error(mock_config_entry):
    """KeyError during cycle tracking is caught silently."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord._last_operation_mode = 4
    coord._current_cycle_start = time.time() - 60

    device = _make_device()
    # Remove a cycle duration key to trigger KeyError
    del coord._cycle_durations[4]

    result = coord._update_cycle_tracking(device)
    # Should not crash, returns cycle_status dict
    assert "predicted_end" in result


# ------------------------------------------------------------------
# Pool refresh failure (lines 595-597)
# ------------------------------------------------------------------


async def test_async_update_data_pool_refresh_failure(mock_config_entry):
    """Pool refresh failure is logged but doesn't fail the update."""
    hass = MagicMock()
    hass.data = {}
    hass.async_create_task = MagicMock()
    api = AsyncMock()
    api.get_device.return_value = _make_device()
    api.get_pools.side_effect = ConnectionError("pool fetch failed")

    coord = _make_coordinator(hass, mock_config_entry, api)
    coord._pool_last_fetch = 0  # Force refresh
    coord.data = PoolCopData(device=_make_device())

    async def mock_save(data):
        pass

    coord._store = MagicMock()
    coord._store.async_save = mock_save

    result = await coord._async_update_data()
    assert result is not None
    assert result.device is not None
    # Pool refresh failed, but data was still returned


# ------------------------------------------------------------------
# Flow meter preference (_flow_meter_rate, get_current_flow_rate,
# _get_flow_rate_for_speed with physical flow meter)
# ------------------------------------------------------------------


def _make_device_with_flow_meter(flow_rate: float = 12.5) -> PoolCopDevice:
    """Build a device with hasFlowMeter=True and a flowVis entry."""
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["equipmentsInfo"]["hasFlowMeter"] = True
    data["state"]["flowVis"] = [
        {"installed": True, "pumpId": 0, "flowRate": flow_rate, "type": "FlowVis"}
    ]
    return PoolCopDevice.from_dict(data)


async def test_flow_meter_rate_installed_and_reporting(mock_config_entry):
    """_flow_meter_rate returns the reading when meter is installed and > 0."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = _make_device_with_flow_meter(12.5)
    assert coord._flow_meter_rate(device) == 12.5


async def test_flow_meter_rate_not_installed(mock_config_entry):
    """_flow_meter_rate returns None when hasFlowMeter is False."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = _make_device()  # default: hasFlowMeter=False
    assert coord._flow_meter_rate(device) is None


async def test_flow_meter_rate_installed_empty_flowvis(mock_config_entry):
    """_flow_meter_rate returns None when hasFlowMeter is True but flowVis is empty."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["equipmentsInfo"]["hasFlowMeter"] = True
    data["state"]["flowVis"] = []
    device = PoolCopDevice.from_dict(data)
    assert coord._flow_meter_rate(device) is None


async def test_flow_meter_rate_installed_zero_rate(mock_config_entry):
    """_flow_meter_rate returns None when flow meter reads 0."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = _make_device_with_flow_meter(0.0)
    assert coord._flow_meter_rate(device) is None


async def test_flow_meter_rate_installed_none_rate(mock_config_entry):
    """_flow_meter_rate returns None when flow_rate is None."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["equipmentsInfo"]["hasFlowMeter"] = True
    data["state"]["flowVis"] = [
        {"installed": True, "pumpId": 0, "flowRate": None, "type": "FlowVis"}
    ]
    device = PoolCopDevice.from_dict(data)
    assert coord._flow_meter_rate(device) is None


async def test_get_current_flow_rate_prefers_flow_meter(mock_config_entry):
    """get_current_flow_rate returns flow meter reading over configured rate."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = _make_device_with_flow_meter(12.5)
    coord.data = PoolCopData(device=device)
    rate = coord.get_current_flow_rate()
    assert rate == 12.5  # flow meter, not configured Speed1=10.0


async def test_get_current_flow_rate_fallback_when_meter_empty(mock_config_entry):
    """get_current_flow_rate falls back to configured rate when flowVis is empty."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    data = deepcopy(MOCK_DEVICE_RESPONSE)
    data["equipmentsInfo"]["hasFlowMeter"] = True
    data["state"]["flowVis"] = []
    coord.data = PoolCopData(device=PoolCopDevice.from_dict(data))
    rate = coord.get_current_flow_rate()
    assert rate == 10.0  # falls back to Speed1 configured rate


async def test_get_current_flow_rate_fallback_when_meter_zero(mock_config_entry):
    """get_current_flow_rate falls back to configured rate when meter reads 0."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = _make_device_with_flow_meter(0.0)
    coord.data = PoolCopData(device=device)
    rate = coord.get_current_flow_rate()
    assert rate == 10.0  # falls back to Speed1 configured rate


async def test_get_flow_rate_for_speed_prefers_flow_meter(mock_config_entry):
    """_get_flow_rate_for_speed returns flow meter reading over speed-based rate."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    device = _make_device_with_flow_meter(12.5)
    coord.data = PoolCopData(device=device)
    rate = coord._get_flow_rate_for_speed(2)
    assert rate == 12.5  # flow meter, not Speed2=15.0


async def test_get_flow_rate_for_speed_fallback_no_meter(mock_config_entry):
    """_get_flow_rate_for_speed uses speed-based rate when meter not installed."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    coord.data = PoolCopData(device=_make_device())
    rate = coord._get_flow_rate_for_speed(2)
    assert rate == 15.0  # Speed2 configured rate


async def test_set_heating_setpoint(mock_config_entry):
    """set_heating_setpoint delegates to API."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    await coord.set_heating_setpoint(28.5, 4, "None")
    coord.api.set_heating_setpoint.assert_called_once_with(2478, 28.5, 4, "None")


async def test_set_jet_stream(mock_config_entry):
    """set_jet_stream delegates to API."""
    hass = MagicMock()
    hass.data = {}
    coord = _make_coordinator(hass, mock_config_entry)
    await coord.set_jet_stream(on=True)
    coord.api.set_jet_stream.assert_called_once_with(2478, on=True)
