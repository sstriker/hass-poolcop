"""Test PoolCop sensor platform."""

from unittest.mock import patch

from aiopoolcop import Pool, PoolCopDevice
from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import DOMAIN
from custom_components.poolcop.coordinator import PoolCopData
from custom_components.poolcop.sensor import (
    _cycle_elapsed_time_fn,
    _cycle_end_time_fn,
    _cycle_time_remaining_fn,
    _time_str_to_time_today,
)


async def _setup_integration(hass, mock_config_entry, mock_poolcop_api, device_data, pool_data):
    """Set up the integration and return the coordinator."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(pool_data)]
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.poolcop.PoolCopClientAPI", return_value=mock_poolcop_api):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return hass.data[DOMAIN][mock_config_entry.entry_id]


async def test_sensor_platform_setup(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Key sensors exist after setup."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("sensor")
    sensor_keys = {s.entity_id for s in states}
    assert any("water_temperature" in s for s in sensor_keys)
    assert any("running_status" in s for s in sensor_keys)


async def test_water_temperature_value(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Water temperature should be 27.2."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("sensor") if "water_temperature" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "27.2"


async def test_ph_value(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """pH should be 7.5."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("sensor") if s.entity_id.endswith("_ph")]
    assert len(states) >= 1
    assert states[0].state == "7.5"


async def test_running_status_value(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Running status should be timer_mode slug."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("sensor") if "running_status" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "timer_mode"


async def test_valve_position_sensor(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Valve position should be 'filter' slug."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("sensor") if "valve_position" in s.entity_id and "select" not in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "filter"


async def test_planned_remaining_sensors_exist(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Planned remaining volume and turnovers sensors are created."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("sensor")
    sensor_keys = {s.entity_id for s in states}
    assert any("planned_remaining" in s for s in sensor_keys)


async def test_cycle_time_remaining_fn_no_cycle_mode():
    """Returns None when not in cycle mode."""
    device = PoolCopDevice.from_dict({
        "id": 1,
        "state": {
            "pumpsInfo": [{"runningStatus": "Stopped", "pumpState": False}],
        },
    })
    data = PoolCopData(device=device, cycle_status={"remaining_time": 120})
    assert _cycle_time_remaining_fn(data) is None


async def test_cycle_time_remaining_fn_in_cycle():
    """Returns remaining time when in cycle mode."""
    device = PoolCopDevice.from_dict({
        "id": 1,
        "state": {
            "pumpsInfo": [{"runningStatus": "TimerMode", "pumpState": True}],
        },
    })
    data = PoolCopData(
        device=device,
        cycle_status={"remaining_time": 120.5, "elapsed_time": 300, "predicted_end": None},
    )
    assert _cycle_time_remaining_fn(data) == 120.5


async def test_cycle_elapsed_time_fn():
    """Returns None when not in cycle, value when in cycle."""
    device_stopped = PoolCopDevice.from_dict({
        "id": 1,
        "state": {"pumpsInfo": [{"runningStatus": "Stopped"}]},
    })
    data_stopped = PoolCopData(device=device_stopped, cycle_status={"elapsed_time": 120})
    assert _cycle_elapsed_time_fn(data_stopped) is None

    device_timer = PoolCopDevice.from_dict({
        "id": 1,
        "state": {"pumpsInfo": [{"runningStatus": "TimerMode"}]},
    })
    data_timer = PoolCopData(device=device_timer, cycle_status={"elapsed_time": 300})
    assert _cycle_elapsed_time_fn(data_timer) == 300


async def test_cycle_end_time_fn_not_in_cycle():
    """Returns None when not in cycle mode."""
    device = PoolCopDevice.from_dict({
        "id": 1,
        "state": {"pumpsInfo": [{"runningStatus": "Stopped"}]},
    })
    data = PoolCopData(device=device, cycle_status={"predicted_end": 9999999999})
    assert _cycle_end_time_fn(data) is None


async def test_time_str_to_time_today_invalid_tz():
    """Invalid tz falls back to local timezone."""
    result = _time_str_to_time_today("14:00:00", "Invalid/Timezone")
    assert result is not None
    assert result.hour == 14


async def test_time_str_to_time_today_falsy_input():
    """Falsy or 00:00:00 returns None."""
    assert _time_str_to_time_today("", "UTC") is None
    assert _time_str_to_time_today("00:00:00", "UTC") is None
    assert _time_str_to_time_today(None, "UTC") is None


async def test_time_str_to_time_today_value_error():
    """Invalid time string returns None."""
    assert _time_str_to_time_today("invalid", "UTC") is None
    assert _time_str_to_time_today("not:a:time", "UTC") is None
