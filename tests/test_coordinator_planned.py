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
      5=Manual, 6=Paused, 7=External, 8=Eco+, 9=Continuous
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
                "filter": {"timer": 1},
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
    """op_mode=8 (Eco+) uses same timer logic as Timer/Auto."""
    status = _make_status(
        op_mode=8,
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
    """op_mode=9 (Continuous) -> remaining hours × flow rate."""
    status = _make_status(op_mode=9, pump_speed=2)
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


async def test_forced_mode_uses_remaining_hours(coordinator):
    """op_mode=2 (Forced) -> forced.remaining_hours × flow rate."""
    status = _make_status(op_mode=2, pump_speed=2, forced_remaining=10)
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
