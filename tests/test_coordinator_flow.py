"""Test PoolCop coordinator flow rate and volume tracking."""

import time
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.poolcop.coordinator import (
    PoolCopData,
    PoolCopDataUpdateCoordinator,
)


def _make_status(pump=1, valve=0, speed=2, pool_volume=50):
    """Create a minimal status dict for flow rate testing."""
    return {
        "PoolCop": {
            "status": {
                "pump": pump,
                "valveposition": valve,
                "pumpspeed": speed,
                "poolcop": 3,
            },
            "conf": {"orp": 0, "pH": 0, "waterlevel": 0, "ioniser": 0, "autochlor": 0, "air": 0},
            "alerts": [],
            "settings": {"pool": {"volume": pool_volume}},
            "timers": {},
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


async def test_flow_rate_pump_on_filter(coordinator):
    """Test flow rate with pump on and valve in filter position."""
    coordinator.data = PoolCopData(status=_make_status(pump=1, valve=0, speed=2))
    assert coordinator.get_current_flow_rate() == 15.0


async def test_flow_rate_pump_off(coordinator):
    """Test flow rate is 0 when pump is off."""
    coordinator.data = PoolCopData(status=_make_status(pump=0, valve=0, speed=2))
    assert coordinator.get_current_flow_rate() == 0.0


async def test_flow_rate_valve_waste(coordinator):
    """Test flow rate is 0 when valve is in waste position."""
    coordinator.data = PoolCopData(status=_make_status(pump=1, valve=1, speed=2))
    assert coordinator.get_current_flow_rate() == 0.0


async def test_flow_rate_valve_closed(coordinator):
    """Test flow rate is 0 when valve is closed."""
    coordinator.data = PoolCopData(status=_make_status(pump=1, valve=2, speed=2))
    assert coordinator.get_current_flow_rate() == 0.0


async def test_flow_rate_valve_backwash(coordinator):
    """Test flow rate is 0 when valve is in backwash."""
    coordinator.data = PoolCopData(status=_make_status(pump=1, valve=3, speed=2))
    assert coordinator.get_current_flow_rate() == 0.0


async def test_flow_rate_valve_bypass(coordinator):
    """Test flow rate is non-zero when valve is in bypass (still flowing)."""
    coordinator.data = PoolCopData(status=_make_status(pump=1, valve=4, speed=2))
    assert coordinator.get_current_flow_rate() == 15.0


async def test_flow_rate_valve_rinse(coordinator):
    """Test flow rate is non-zero when valve is in rinse."""
    coordinator.data = PoolCopData(status=_make_status(pump=1, valve=5, speed=2))
    assert coordinator.get_current_flow_rate() == 15.0


async def test_flow_rate_speed_1(coordinator):
    """Test flow rate at speed 1."""
    coordinator.data = PoolCopData(status=_make_status(pump=1, valve=0, speed=1))
    assert coordinator.get_current_flow_rate() == 10.0


async def test_flow_rate_speed_3(coordinator):
    """Test flow rate at speed 3."""
    coordinator.data = PoolCopData(status=_make_status(pump=1, valve=0, speed=3))
    assert coordinator.get_current_flow_rate() == 20.0


async def test_flow_rate_unknown_speed(coordinator):
    """Test flow rate returns 0 for unconfigured speed."""
    coordinator.data = PoolCopData(status=_make_status(pump=1, valve=0, speed=99))
    assert coordinator.get_current_flow_rate() == 0.0


async def test_flow_rate_no_data(coordinator):
    """Test flow rate returns 0 when no data."""
    assert coordinator.get_current_flow_rate() == 0.0


async def test_daily_volume_accumulates(coordinator):
    """Test that daily volume accumulates correctly."""
    coordinator.data = PoolCopData(status=_make_status(pump=1, valve=0, speed=2))
    # flow_rate = 15 m³/h

    # Simulate two updates 120 seconds apart
    with patch("time.monotonic", return_value=1000.0):
        coordinator._update_daily_volume()

    with patch("time.monotonic", return_value=1120.0):
        coordinator._update_daily_volume()

    # 15 m³/h * (120s / 3600s) = 0.5 m³
    assert abs(coordinator.daily_volume - 0.5) < 0.001


async def test_daily_volume_zero_when_pump_off(coordinator):
    """Test that no volume accumulates when pump is off."""
    coordinator.data = PoolCopData(status=_make_status(pump=0, valve=0, speed=0))

    with patch("time.monotonic", return_value=1000.0):
        coordinator._update_daily_volume()

    with patch("time.monotonic", return_value=1120.0):
        coordinator._update_daily_volume()

    assert coordinator.daily_volume == 0.0


async def test_daily_volume_skips_large_gaps(coordinator):
    """Test that gaps > 10 minutes are skipped (restart scenario)."""
    coordinator.data = PoolCopData(status=_make_status(pump=1, valve=0, speed=2))

    with patch("time.monotonic", return_value=1000.0):
        coordinator._update_daily_volume()

    # 15 minute gap - should be skipped
    with patch("time.monotonic", return_value=1900.0):
        coordinator._update_daily_volume()

    assert coordinator.daily_volume == 0.0


async def test_daily_turnovers(coordinator):
    """Test daily turnovers calculation."""
    coordinator.data = PoolCopData(status=_make_status(pump=1, valve=0, speed=2, pool_volume=50))
    coordinator._daily_volume = 25.0  # Half the pool volume
    assert coordinator.daily_turnovers == 0.5

    coordinator._daily_volume = 50.0  # Full pool volume
    assert coordinator.daily_turnovers == 1.0

    coordinator._daily_volume = 100.0  # Two turnovers
    assert coordinator.daily_turnovers == 2.0


async def test_daily_turnovers_no_volume(coordinator):
    """Test daily turnovers returns None when pool volume is missing."""
    coordinator.data = PoolCopData(status=_make_status(pool_volume=0))
    coordinator._daily_volume = 10.0
    assert coordinator.daily_turnovers is None


async def test_daily_turnovers_no_data(coordinator):
    """Test daily turnovers returns None when no data."""
    assert coordinator.daily_turnovers is None


async def test_has_active_alarms():
    """Test has_active_alarms helper."""
    data_no_alarms = PoolCopData(status={}, active_alarms=[])
    assert data_no_alarms.has_active_alarms() is False

    data_with_alarms = PoolCopData(
        status={},
        active_alarms=[{"name": "alert_title_5", "id": "5", "date": "2025-01-01"}],
    )
    assert data_with_alarms.has_active_alarms() is True
