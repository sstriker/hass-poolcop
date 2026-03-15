"""Test PoolCop coordinator cycle tracking."""

import time
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.poolcop.coordinator import (
    DEFAULT_CYCLE_DURATIONS,
    PoolCopDataUpdateCoordinator,
)


def _make_status(mode: int) -> dict:
    """Build minimal status dict with the given operation mode."""
    return {
        "PoolCop": {
            "status": {"poolcop": mode, "pump": 1, "valveposition": 0, "pumpspeed": 2},
            "conf": {},
            "alarms": {"count": 0},
            "network": {"version": "1.0"},
            "aux": [],
            "settings": {"pump": {"nb_speed": 3}, "pool": {"volume": 50}},
            "timers": {},
        },
    }


@pytest.fixture
async def coordinator(hass: HomeAssistant, mock_config_entry, mock_poolcop):
    """Return a coordinator wired to the mock."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coord = PoolCopDataUpdateCoordinator(
            hass=hass, api_key="test-key", config_entry=mock_config_entry
        )
    return coord


# ── Cycle transition & EMA ──────────────────────────────────────────


async def test_cycle_transition_updates_ema(coordinator):
    """Mode change 1→2 triggers EMA: 0.3*actual + 0.7*old."""
    now = time.time()
    coordinator._last_operation_mode = 1
    coordinator._current_cycle_start = now - 3600  # 1h in mode 1

    status = _make_status(2)
    result = coordinator._update_cycle_tracking(status)

    old_dur = DEFAULT_CYCLE_DURATIONS[1]  # 7200
    expected = 0.3 * 3600 + 0.7 * old_dur
    assert abs(coordinator._cycle_durations[1] - expected) < 2
    assert result is not None


async def test_cycle_transition_records_history(coordinator):
    """Transition is appended to _cycle_transitions."""
    now = time.time()
    coordinator._last_operation_mode = 1
    coordinator._current_cycle_start = now - 100

    coordinator._update_cycle_tracking(_make_status(2))

    assert len(coordinator._cycle_transitions) == 1
    t = coordinator._cycle_transitions[0]
    assert t["from_mode"] == 1
    assert t["to_mode"] == 2


async def test_cycle_transitions_capped_at_20(coordinator):
    """21st transition pops the oldest."""
    now = time.time()
    # Pre-populate 20 transitions
    coordinator._cycle_transitions = [
        {"from_mode": 0, "to_mode": 1, "duration": 10, "timestamp": now}
    ] * 20
    coordinator._last_operation_mode = 3
    coordinator._current_cycle_start = now - 50

    coordinator._update_cycle_tracking(_make_status(4))

    assert len(coordinator._cycle_transitions) == 20
    assert coordinator._cycle_transitions[-1]["from_mode"] == 3


async def test_cycle_transition_idle_no_ema(coordinator):
    """Idle modes (0, 6, 7) don't update cycle durations."""
    now = time.time()
    coordinator._last_operation_mode = 0
    coordinator._current_cycle_start = now - 500

    old_durations = coordinator._cycle_durations.copy()
    coordinator._update_cycle_tracking(_make_status(1))

    assert coordinator._cycle_durations[0] == old_durations[0]


async def test_cycle_elapsed_and_remaining(coordinator):
    """Verify elapsed_time and remaining_time in cycle_status."""
    now = time.time()
    coordinator._last_operation_mode = 1
    coordinator._current_cycle_start = now - 1000

    result = coordinator._update_cycle_tracking(_make_status(1))

    assert result["elapsed_time"] is not None
    assert result["elapsed_time"] >= 1000
    assert result["remaining_time"] is not None


async def test_cycle_tracking_malformed_data(coordinator):
    """Missing keys → caught, returns dict."""
    result = coordinator._update_cycle_tracking({})
    assert isinstance(result, dict)
    assert result["predicted_end"] is None


async def test_cycle_no_transition_same_mode(coordinator):
    """Same mode twice → no transition recorded."""
    coordinator._last_operation_mode = 3
    coordinator._current_cycle_start = time.time() - 100

    coordinator._update_cycle_tracking(_make_status(3))
    assert len(coordinator._cycle_transitions) == 0
