"""Test planned remaining volume/turnovers coordinator logic."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.poolcop.coordinator import (
    PoolCopData,
    PoolCopDataUpdateCoordinator,
)


def _make_status(
    op_mode=3,
    filter_timer=1,
    cycle1_enabled=1,
    cycle1_start="08:00:00",
    cycle1_stop="12:00:00",
    cycle2_enabled=0,
    cycle2_start="00:00:00",
    cycle2_stop="00:00:00",
    speed_cycle1=2,
    speed_cycle2=1,
    pool_volume=50,
    pump_speed=2,
    forced_mode=0,
    forced_remaining=0,
):
    """Create a status dict for planned-volume testing.

    op_mode maps to status.poolcop (the actual operating mode):
      0=Stop, 1=Freeze, 2=Forced, 3=Auto, 4=Timer,
      5=Manual, 6=Paused, 7=External, 8=Water Level Management, 9=24/24
    filter_timer maps to settings.filter.timer (the configured filter timer mode):
      0=STOP, 1=TIMER, 2=ECO+, 3=VOLUME, 4=CONTINUOUS,
      5-7=FORCE 24/48/72H, 8=24/24 Always On, 9=No Pump
    """
    return {
        "PoolCop": {
            "status": {
                "pump": 1,
                "valveposition": 0,
                "pumpspeed": pump_speed,
                "poolcop": op_mode,
                "forced": {
                    "mode": forced_mode,
                    "remaining_hours": forced_remaining,
                },
            },
            "settings": {
                "pool": {"volume": pool_volume},
                "filter": {"timer": filter_timer},
                "pump": {
                    "speed_cycle1": speed_cycle1,
                    "speed_cycle2": speed_cycle2,
                },
            },
            "timers": {
                "cycle1": {
                    "enabled": cycle1_enabled,
                    "start": cycle1_start,
                    "stop": cycle1_stop,
                },
                "cycle2": {
                    "enabled": cycle2_enabled,
                    "start": cycle2_start,
                    "stop": cycle2_stop,
                },
            },
            "conf": {"orp": 0, "pH": 0, "waterlevel": 0, "ioniser": 0, "autochlor": 0, "air": 0},
            "alerts": [],
        },
        "Pool": {
            "timezone": "UTC",
        },
    }


@pytest.fixture
async def coordinator(hass: HomeAssistant, mock_config_entry, mock_poolcop):
    """Create a coordinator for testing."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coord = PoolCopDataUpdateCoordinator(
            hass=hass, api_key="test", config_entry=mock_config_entry
        )
    return coord


def _freeze_time(hour, minute=0, tz=timezone.utc):
    """Return a fixed datetime for mocking."""
    return datetime(2026, 3, 14, hour, minute, 0, tzinfo=tz)


async def test_auto_mode_both_cycles_future(coordinator):
    """Both cycles ahead of now -> full volume from both (op_mode=3 Auto)."""
    status = _make_status(
        op_mode=3,
        cycle1_enabled=1, cycle1_start="14:00:00", cycle1_stop="18:00:00",
        cycle2_enabled=1, cycle2_start="20:00:00", cycle2_stop="22:00:00",
        speed_cycle1=2, speed_cycle2=1,
    )
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    # cycle1: 4h * 15 m³/h = 60, cycle2: 2h * 10 m³/h = 20
    assert vol == 80.0


async def test_timer_mode_cycle1_in_progress(coordinator):
    """Mid-cycle1 -> partial remaining volume (op_mode=4 Timer)."""
    status = _make_status(
        op_mode=4,
        cycle1_enabled=1, cycle1_start="08:00:00", cycle1_stop="12:00:00",
        speed_cycle1=2,
    )
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    # 2h remaining * 15 m³/h = 30
    assert vol == 30.0


async def test_timer_mode_cycle1_done(coordinator):
    """Past stop -> 0 for cycle1 (op_mode=4 Timer)."""
    status = _make_status(
        op_mode=4,
        cycle1_enabled=1, cycle1_start="06:00:00", cycle1_stop="08:00:00",
        speed_cycle1=2,
    )
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    assert vol == 0.0


async def test_timer_mode_cycle2_disabled(coordinator):
    """Only cycle1 contributes when cycle2 is disabled (op_mode=4 Timer)."""
    status = _make_status(
        op_mode=4,
        cycle1_enabled=1, cycle1_start="14:00:00", cycle1_stop="18:00:00",
        cycle2_enabled=0,
        speed_cycle1=2,
    )
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    # 4h * 15 = 60
    assert vol == 60.0


async def test_eco_mode_uses_timers(coordinator):
    """ECO+ filter mode (timer=2) with Auto running status uses timer logic."""
    status = _make_status(
        op_mode=3,
        cycle1_enabled=1, cycle1_start="14:00:00", cycle1_stop="16:00:00",
        speed_cycle1=2,
    )
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    # 2h * 15 = 30
    assert vol == 30.0


async def test_stop_mode_returns_zero(coordinator):
    """op_mode=0 (Stop) -> 0.0."""
    status = _make_status(op_mode=0)
    coordinator.data = PoolCopData(status=status)
    assert coordinator.planned_remaining_volume == 0.0


async def test_paused_mode_returns_zero(coordinator):
    """op_mode=6 (Paused) -> 0.0."""
    status = _make_status(op_mode=6)
    coordinator.data = PoolCopData(status=status)
    assert coordinator.planned_remaining_volume == 0.0


async def test_manual_mode_returns_zero(coordinator):
    """op_mode=5 (Manual) -> 0.0 (unpredictable)."""
    status = _make_status(op_mode=5)
    coordinator.data = PoolCopData(status=status)
    assert coordinator.planned_remaining_volume == 0.0


async def test_continuous_mode_remaining_hours(coordinator):
    """filter_timer=4 (CONTINUOUS 23h/day) -> remaining hours × flow rate."""
    status = _make_status(op_mode=9, filter_timer=4, pump_speed=2)
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(20, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    # 4h remaining * 15 m³/h = 60
    assert vol == 60.0


async def test_always_on_mode(coordinator):
    """filter_timer=8 (24/24 Always On) -> remaining hours × flow rate."""
    status = _make_status(op_mode=9, filter_timer=8, pump_speed=2)
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(20, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    # 4h remaining * 15 m³/h = 60
    assert vol == 60.0


async def test_always_on_overrides_op_mode(coordinator):
    """filter_timer=8 (24/24) takes priority even if op_mode is Auto (3)."""
    status = _make_status(
        op_mode=3, filter_timer=8,
        cycle1_enabled=1, cycle1_start="14:00:00", cycle1_stop="16:00:00",
        pump_speed=2,
    )
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(20, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    # Should use remaining hours (4h * 15 = 60), NOT cycle timers (which would give 0)
    assert vol == 60.0


async def test_forced_mode_uses_remaining_hours(coordinator):
    """op_mode=2 (Forced) -> forced.remaining_hours × flow rate."""
    status = _make_status(op_mode=2, filter_timer=1, pump_speed=2, forced_remaining=10)
    coordinator.data = PoolCopData(status=status)

    vol = coordinator.planned_remaining_volume
    # 10h * 15 m³/h = 150
    assert vol == 150.0


async def test_forced_mode_zero_remaining(coordinator):
    """op_mode=2 (Forced) with 0 remaining hours -> 0.0."""
    status = _make_status(op_mode=2, pump_speed=2, forced_remaining=0)
    coordinator.data = PoolCopData(status=status)
    assert coordinator.planned_remaining_volume == 0.0


async def test_no_flow_rates_returns_zero(coordinator):
    """No configured flow rates -> 0.0."""
    coordinator.flow_rates = {}  # Clear all flow rates

    status = _make_status(
        op_mode=4, cycle1_start="14:00:00", cycle1_stop="18:00:00",
    )
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    assert vol == 0.0


async def test_turnovers_normal(coordinator):
    """volume / pool_volume gives correct turnovers."""
    status = _make_status(
        op_mode=4,
        cycle1_enabled=1, cycle1_start="14:00:00", cycle1_stop="18:00:00",
        speed_cycle1=2, pool_volume=50,
    )
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        turnovers = coordinator.planned_remaining_turnovers

    # 60 m³ / 50 m³ = 1.2
    assert turnovers == 1.2


async def test_turnovers_no_pool_volume(coordinator):
    """No pool volume -> None."""
    status = _make_status(op_mode=4, pool_volume=0)
    coordinator.data = PoolCopData(status=status)
    assert coordinator.planned_remaining_turnovers is None


# --- Edge case / branch coverage tests ---


async def test_no_data_returns_zero(coordinator):
    """No coordinator data -> 0.0 for volume, None for turnovers."""
    coordinator.data = None
    assert coordinator.planned_remaining_volume == 0.0
    assert coordinator.planned_remaining_turnovers is None


async def test_none_op_mode_returns_zero(coordinator):
    """op_mode missing from status -> 0.0."""
    status = _make_status()
    del status["PoolCop"]["status"]["poolcop"]
    coordinator.data = PoolCopData(status=status)
    assert coordinator.planned_remaining_volume == 0.0


async def test_unknown_op_mode_returns_zero(coordinator):
    """Unrecognised op_mode (e.g. 99) -> 0.0."""
    status = _make_status(op_mode=99)
    coordinator.data = PoolCopData(status=status)
    assert coordinator.planned_remaining_volume == 0.0


async def test_cycle_with_zero_times(coordinator):
    """Cycle enabled but times 00:00:00 -> 0 remaining."""
    status = _make_status(
        op_mode=4,
        cycle1_enabled=1, cycle1_start="00:00:00", cycle1_stop="00:00:00",
    )
    coordinator.data = PoolCopData(status=status)
    assert coordinator.planned_remaining_volume == 0.0


async def test_cycle_stop_before_start(coordinator):
    """Cycle where stop < start (overnight) -> 0 remaining."""
    status = _make_status(
        op_mode=4,
        cycle1_enabled=1, cycle1_start="22:00:00", cycle1_stop="06:00:00",
    )
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(23, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    assert vol == 0.0


async def test_cycle_invalid_time_string(coordinator):
    """Cycle with unparsable time string -> 0 remaining."""
    status = _make_status(
        op_mode=4,
        cycle1_enabled=1, cycle1_start="bad", cycle1_stop="also_bad",
    )
    coordinator.data = PoolCopData(status=status)
    assert coordinator.planned_remaining_volume == 0.0


async def test_get_remaining_cycle_no_data(coordinator):
    """_get_remaining_cycle_seconds with no data -> 0."""
    coordinator.data = None
    assert coordinator._get_remaining_cycle_seconds("cycle1") == 0.0


async def test_flow_rate_fallback_to_pumpspeed(coordinator):
    """When speed_cycle has no matching flow rate, fall back to pumpspeed."""
    status = _make_status(
        op_mode=4,
        cycle1_enabled=1, cycle1_start="14:00:00", cycle1_stop="18:00:00",
        speed_cycle1=99,  # No flow rate configured for speed 99
        pump_speed=2,     # Fallback to pumpspeed=2 -> 15 m³/h
    )
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    # Falls back to pumpspeed 2 -> 15 m³/h * 4h = 60
    assert vol == 60.0


async def test_flow_rate_fallback_unknown_speeds(coordinator):
    """When both speed_cycle and pumpspeed are unconfigured -> 0."""
    status = _make_status(
        op_mode=4,
        cycle1_enabled=1, cycle1_start="14:00:00", cycle1_stop="18:00:00",
        speed_cycle1=99,  # Unknown - no flow rate for 99
        pump_speed=99,    # Also unknown
    )
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    # pumpspeed fallback returns 0.0 (no rate for speed 99)
    assert vol == 0.0


async def test_flow_rate_fallback_to_speed1(coordinator):
    """When pumpspeed is missing from status, fall back to speed 1."""
    status = _make_status(
        op_mode=4,
        cycle1_enabled=1, cycle1_start="14:00:00", cycle1_stop="18:00:00",
        speed_cycle1=99,  # Unknown
    )
    del status["PoolCop"]["status"]["pumpspeed"]  # No pumpspeed at all
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    # Falls back to speed 1 -> 10 m³/h * 4h = 40
    assert vol == 40.0


async def test_forced_mode_invalid_speed(coordinator):
    """Forced mode with non-integer pumpspeed -> fallback still works."""
    status = _make_status(op_mode=2, forced_remaining=5)
    status["PoolCop"]["status"]["pumpspeed"] = "bad"
    coordinator.data = PoolCopData(status=status)

    vol = coordinator.planned_remaining_volume
    # Falls back: "bad" -> ValueError -> speed=None -> pumpspeed fallback
    # pumpspeed is "bad" again -> ValueError -> speed 1 -> 10 m³/h * 5h = 50
    assert vol == 50.0


async def test_cycle_speed_invalid(coordinator):
    """Timer mode with non-integer speed_cycle -> fallback works."""
    status = _make_status(
        op_mode=4,
        cycle1_enabled=1, cycle1_start="14:00:00", cycle1_stop="18:00:00",
    )
    status["PoolCop"]["settings"]["pump"]["speed_cycle1"] = "bad"
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    # speed "bad" -> ValueError -> None -> fallback to pumpspeed 2 -> 15 * 4 = 60
    assert vol == 60.0


async def test_cycle_no_speed_setting(coordinator):
    """Timer mode with missing speed_cycle key -> fallback to pumpspeed."""
    status = _make_status(
        op_mode=4,
        cycle1_enabled=1, cycle1_start="14:00:00", cycle1_stop="18:00:00",
    )
    del status["PoolCop"]["settings"]["pump"]["speed_cycle1"]
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    # speed_cycle1 missing -> None -> fallback to pumpspeed 2 -> 15 * 4 = 60
    assert vol == 60.0


async def test_continuous_mode_bad_timezone(coordinator):
    """Continuous mode with invalid timezone -> still calculates."""
    status = _make_status(op_mode=9, pump_speed=2)
    status["Pool"]["timezone"] = "Invalid/Zone"
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(20, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    # Falls back to no tz, 4h * 15 = 60
    assert vol == 60.0


async def test_continuous_mode_bad_pumpspeed(coordinator):
    """Continuous mode with non-integer pumpspeed -> fallback to speed 1."""
    status = _make_status(op_mode=9)
    status["PoolCop"]["status"]["pumpspeed"] = "bad"
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(20, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    # pumpspeed "bad" -> ValueError -> None -> speed 1 -> 10 * 4 = 40
    assert vol == 40.0


async def test_continuous_mode_datetime_exception(coordinator):
    """Continuous mode when datetime.now raises -> 0.0."""
    status = _make_status(op_mode=9)
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.side_effect = OSError("clock error")
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    assert vol == 0.0


async def test_cycle_bad_timezone_fallback(coordinator):
    """Cycle timer with invalid timezone -> falls back, still works."""
    status = _make_status(
        op_mode=4,
        cycle1_enabled=1, cycle1_start="14:00:00", cycle1_stop="18:00:00",
    )
    status["Pool"]["timezone"] = "Bogus/TZ"
    coordinator.data = PoolCopData(status=status)

    with patch(
        "custom_components.poolcop.coordinator.datetime",
        wraps=datetime,
    ) as mock_dt:
        mock_dt.now.return_value = _freeze_time(10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        vol = coordinator.planned_remaining_volume

    # Timezone fallback to None, still calculates: 4h * 15 = 60
    assert vol == 60.0
