"""Test PoolCop sensor platform."""

from unittest.mock import patch

from aiopoolcop import Pool, PoolCopDevice
from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import DOMAIN
from custom_components.poolcop.coordinator import PoolCopData
from custom_components.poolcop.sensor import (
    _aux_timer_enabled_fn,
    _aux_timer_time_fn,
    _cycle_elapsed_time_fn,
    _cycle_end_time_fn,
    _cycle_time_remaining_fn,
    _filtration,
    _filtration_timer_enabled_fn,
    _filtration_timer_time_fn,
    _is_cycle_mode,
    _parse_datetime,
    _pool_timezone,
    _slugify_enum,
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


async def test_parse_datetime_none_and_empty():
    """None and empty string return None."""
    assert _parse_datetime(None) is None
    assert _parse_datetime("") is None


async def test_parse_datetime_epoch_rejected():
    """Year < 2000 returns None."""
    assert _parse_datetime("1970-01-01T00:00:00") is None
    assert _parse_datetime("1999-12-31T23:59:59") is None


async def test_parse_datetime_invalid_string():
    """Non-ISO string returns None."""
    assert _parse_datetime("not-a-date") is None


async def test_parse_datetime_invalid_timezone():
    """Invalid tz name falls back to UTC."""
    result = _parse_datetime("2026-05-16T22:28:00", "Invalid/TZ")
    assert result is not None
    assert result.tzinfo is not None


async def test_parse_datetime_naive_gets_pool_tz():
    """Naive datetime gets pool timezone applied."""
    result = _parse_datetime("2026-05-16T22:28:00", "Europe/Amsterdam")
    assert result is not None
    assert str(result.tzinfo) == "Europe/Amsterdam"


async def test_parse_datetime_aware_kept():
    """Already-aware datetime is not changed."""
    result = _parse_datetime("2026-05-16T22:28:00+05:00", "Europe/Amsterdam")
    assert result is not None
    assert result.utcoffset().total_seconds() == 5 * 3600


async def test_slugify_enum_unknown_value():
    """Unknown value falls back to lower-case."""
    assert _slugify_enum("UnknownNew", {"Known": "known"}) == "unknownnew"


async def test_slugify_enum_none():
    """None value returns None."""
    assert _slugify_enum(None, {"Known": "known"}) is None


async def test_is_cycle_mode_unknown_status():
    """Unknown running status returns False."""
    device = PoolCopDevice.from_dict({
        "id": 1,
        "state": {"pumpsInfo": [{"runningStatus": "BrandNewMode"}]},
    })
    data = PoolCopData(device=device, cycle_status={})
    assert _is_cycle_mode(data) is False


async def test_is_cycle_mode_no_pumps():
    """No pumps returns False."""
    device = PoolCopDevice.from_dict({"id": 1, "state": {}})
    data = PoolCopData(device=device, cycle_status={})
    assert _is_cycle_mode(data) is False


async def test_cycle_end_time_fn_in_cycle():
    """Returns datetime when in cycle with predicted_end."""
    import time

    ts = time.time() + 3600
    device = PoolCopDevice.from_dict({
        "id": 1,
        "state": {"pumpsInfo": [{"runningStatus": "TimerMode", "pumpState": True}]},
    })
    pool = Pool.from_dict({"id": 1, "timezone": "UTC"})
    data = PoolCopData(
        device=device, pool=pool,
        cycle_status={"predicted_end": ts, "elapsed_time": 100, "remaining_time": 3600},
    )
    result = _cycle_end_time_fn(data)
    assert result is not None
    assert result.tzinfo is not None


async def test_cycle_end_time_fn_invalid_tz():
    """Invalid pool timezone falls back to UTC."""
    import time

    ts = time.time() + 3600
    device = PoolCopDevice.from_dict({
        "id": 1,
        "state": {"pumpsInfo": [{"runningStatus": "TimerMode", "pumpState": True}]},
    })
    pool = Pool.from_dict({"id": 1, "timezone": "Invalid/Zone"})
    data = PoolCopData(
        device=device, pool=pool,
        cycle_status={"predicted_end": ts, "elapsed_time": 100, "remaining_time": 3600},
    )
    result = _cycle_end_time_fn(data)
    assert result is not None
    assert result.tzinfo is not None


async def test_cycle_end_time_fn_no_pool():
    """No pool data uses UTC."""
    import time

    ts = time.time() + 3600
    device = PoolCopDevice.from_dict({
        "id": 1,
        "state": {"pumpsInfo": [{"runningStatus": "TimerMode", "pumpState": True}]},
    })
    data = PoolCopData(
        device=device, pool=None,
        cycle_status={"predicted_end": ts, "elapsed_time": 100, "remaining_time": 3600},
    )
    result = _cycle_end_time_fn(data)
    assert result is not None


# ------------------------------------------------------------------
# _filtration helpers
# ------------------------------------------------------------------


async def test_filtration_returns_none_no_filtrations():
    """No filtrations returns None."""
    device = PoolCopDevice.from_dict({"id": 1, "state": {}, "settings": {}})
    data = PoolCopData(device=device)
    assert _filtration(data) is None


async def test_filtration_timer_enabled_no_filtrations():
    """No filtrations returns 'Disabled'."""
    device = PoolCopDevice.from_dict({"id": 1, "state": {}, "settings": {}})
    data = PoolCopData(device=device)
    fn = _filtration_timer_enabled_fn(0)
    assert fn(data) == "Disabled"


async def test_filtration_timer_enabled_out_of_range():
    """Timer index out of range returns 'Disabled'."""
    from conftest import MOCK_DEVICE_RESPONSE
    from copy import deepcopy

    device = PoolCopDevice.from_dict(deepcopy(MOCK_DEVICE_RESPONSE))
    data = PoolCopData(device=device)
    fn = _filtration_timer_enabled_fn(99)
    assert fn(data) == "Disabled"


async def test_filtration_timer_time_no_filtrations():
    """No filtrations returns None."""
    device = PoolCopDevice.from_dict({"id": 1, "state": {}, "settings": {}})
    data = PoolCopData(device=device)
    fn = _filtration_timer_time_fn(0, "time_on")
    assert fn(data) is None


async def test_filtration_timer_time_out_of_range():
    """Timer index out of range returns None."""
    from conftest import MOCK_DEVICE_RESPONSE
    from copy import deepcopy

    device = PoolCopDevice.from_dict(deepcopy(MOCK_DEVICE_RESPONSE))
    data = PoolCopData(device=device, pool=Pool.from_dict({"id": 1, "timezone": "UTC"}))
    fn = _filtration_timer_time_fn(99, "time_on")
    assert fn(data) is None


async def test_filtration_timer_time_disabled():
    """Disabled timer returns None."""
    from conftest import MOCK_DEVICE_RESPONSE
    from copy import deepcopy

    device_data = deepcopy(MOCK_DEVICE_RESPONSE)
    device_data["settings"]["filtrations"][0]["timers"][0]["enabled"] = False
    device = PoolCopDevice.from_dict(device_data)
    data = PoolCopData(device=device, pool=Pool.from_dict({"id": 1, "timezone": "UTC"}))
    fn = _filtration_timer_time_fn(0, "time_on")
    assert fn(data) is None


async def test_filtration_timer_time_empty_string():
    """Empty time string returns None."""
    from conftest import MOCK_DEVICE_RESPONSE
    from copy import deepcopy

    device_data = deepcopy(MOCK_DEVICE_RESPONSE)
    device_data["settings"]["filtrations"][0]["timers"][0]["timeOn"] = ""
    device = PoolCopDevice.from_dict(device_data)
    data = PoolCopData(device=device, pool=Pool.from_dict({"id": 1, "timezone": "UTC"}))
    fn = _filtration_timer_time_fn(0, "time_on")
    assert fn(data) is None


async def test_filtration_timer_time_valid():
    """Valid timer time returns datetime."""
    from conftest import MOCK_DEVICE_RESPONSE
    from copy import deepcopy

    device = PoolCopDevice.from_dict(deepcopy(MOCK_DEVICE_RESPONSE))
    data = PoolCopData(device=device, pool=Pool.from_dict({"id": 1, "timezone": "UTC"}))
    fn = _filtration_timer_time_fn(0, "time_on")
    result = fn(data)
    # Timer 0 time_on is "23:59:00" — should return a datetime
    assert result is not None
    assert result.hour == 23


# ------------------------------------------------------------------
# _aux_timer helpers
# ------------------------------------------------------------------


async def test_aux_timer_enabled_active():
    """Aux with active timer returns 'Enabled'."""
    from conftest import MOCK_DEVICE_RESPONSE
    from copy import deepcopy

    device_data = deepcopy(MOCK_DEVICE_RESPONSE)
    device_data["settings"]["auxs"]["None"]["Aux4"]["timers"] = [
        {"id": 1, "timeOn": "08:00:00", "timeOff": "20:00:00"}
    ]
    device = PoolCopDevice.from_dict(device_data)
    data = PoolCopData(device=device)
    fn = _aux_timer_enabled_fn("Aux4")
    assert fn(data) == "Enabled"


async def test_aux_timer_enabled_inactive():
    """Aux with 00:00:00 timer returns 'Disabled'."""
    from conftest import MOCK_DEVICE_RESPONSE
    from copy import deepcopy

    device = PoolCopDevice.from_dict(deepcopy(MOCK_DEVICE_RESPONSE))
    data = PoolCopData(device=device)
    fn = _aux_timer_enabled_fn("Aux4")
    assert fn(data) == "Disabled"


async def test_aux_timer_enabled_not_found():
    """Aux ID not found returns 'Disabled'."""
    from conftest import MOCK_DEVICE_RESPONSE
    from copy import deepcopy

    device = PoolCopDevice.from_dict(deepcopy(MOCK_DEVICE_RESPONSE))
    data = PoolCopData(device=device)
    fn = _aux_timer_enabled_fn("NonExistent")
    assert fn(data) == "Disabled"


async def test_aux_timer_time_valid():
    """Aux with valid timer returns datetime."""
    from conftest import MOCK_DEVICE_RESPONSE
    from copy import deepcopy

    device_data = deepcopy(MOCK_DEVICE_RESPONSE)
    device_data["settings"]["auxs"]["None"]["Aux4"]["timers"] = [
        {"id": 1, "timeOn": "14:00:00", "timeOff": "18:00:00"}
    ]
    device = PoolCopDevice.from_dict(device_data)
    data = PoolCopData(device=device, pool=Pool.from_dict({"id": 1, "timezone": "UTC"}))
    fn = _aux_timer_time_fn("Aux4", 0, "time_on")
    result = fn(data)
    assert result is not None
    assert result.hour == 14


async def test_aux_timer_time_zero():
    """Aux with 00:00:00 timer returns None."""
    from conftest import MOCK_DEVICE_RESPONSE
    from copy import deepcopy

    device = PoolCopDevice.from_dict(deepcopy(MOCK_DEVICE_RESPONSE))
    data = PoolCopData(device=device, pool=Pool.from_dict({"id": 1, "timezone": "UTC"}))
    fn = _aux_timer_time_fn("Aux4", 0, "time_on")
    assert fn(data) is None


async def test_aux_timer_time_out_of_range():
    """Timer index out of range returns None."""
    from conftest import MOCK_DEVICE_RESPONSE
    from copy import deepcopy

    device = PoolCopDevice.from_dict(deepcopy(MOCK_DEVICE_RESPONSE))
    data = PoolCopData(device=device, pool=Pool.from_dict({"id": 1, "timezone": "UTC"}))
    fn = _aux_timer_time_fn("Aux4", 99, "time_on")
    assert fn(data) is None


async def test_aux_timer_time_not_found():
    """Aux ID not found returns None."""
    from conftest import MOCK_DEVICE_RESPONSE
    from copy import deepcopy

    device = PoolCopDevice.from_dict(deepcopy(MOCK_DEVICE_RESPONSE))
    data = PoolCopData(device=device, pool=Pool.from_dict({"id": 1, "timezone": "UTC"}))
    fn = _aux_timer_time_fn("NonExistent", 0, "time_on")
    assert fn(data) is None


# ------------------------------------------------------------------
# _pool_timezone
# ------------------------------------------------------------------


async def test_pool_timezone_with_pool():
    """Pool with timezone returns it."""
    pool = Pool.from_dict({"id": 1, "timezone": "America/New_York"})
    data = PoolCopData(device=PoolCopDevice.from_dict({"id": 1, "state": {}}), pool=pool)
    assert _pool_timezone(data) == "America/New_York"


async def test_pool_timezone_no_pool():
    """No pool returns 'UTC'."""
    data = PoolCopData(device=PoolCopDevice.from_dict({"id": 1, "state": {}}), pool=None)
    assert _pool_timezone(data) == "UTC"


# ------------------------------------------------------------------
# Aux timer sensor creation (integration test for lines 950/953)
# ------------------------------------------------------------------


async def test_aux_timer_sensors_created(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Aux with timers creates timer sensors (skip fixed-function labels)."""
    mock_device_data["settings"]["auxs"]["None"]["Aux4"]["timers"] = [
        {"id": 1, "timeOn": "08:00:00", "timeOff": "20:00:00"}
    ]
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("sensor")
    # Aux timer sensors have entity IDs like poolcop_2478_transferpump_start_time
    aux_timer = [s for s in states if "transferpump" in s.entity_id and "start_time" in s.entity_id]
    assert len(aux_timer) >= 1


async def test_aux_timer_sensors_skip_fixed_function(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Fixed-function aux (label_aux_16 = Waste Valve) timers are skipped."""
    mock_device_data["settings"]["auxs"]["None"]["Aux4"]["label"] = "label_aux_16"
    mock_device_data["settings"]["auxs"]["None"]["Aux4"]["timers"] = [
        {"id": 1, "timeOn": "08:00:00", "timeOff": "20:00:00"}
    ]
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("sensor")
    # Fixed-function label_aux_16 (Waste Valve) sensors should not exist
    aux_timer = [s for s in states if "waste_valve" in s.entity_id and "start_time" in s.entity_id]
    assert len(aux_timer) == 0


async def test_aux_no_timers_no_sensors(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Aux with empty timers creates no timer sensors."""
    mock_device_data["settings"]["auxs"]["None"]["Aux4"]["timers"] = []
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("sensor")
    aux_timer = [s for s in states if "transferpump" in s.entity_id and "start_time" in s.entity_id]
    assert len(aux_timer) == 0


# ------------------------------------------------------------------
# Exception handlers in timer time functions (sensor.py lines 298-300, 346-354)
# ------------------------------------------------------------------


async def test_filtration_timer_time_tz_error():
    """AttributeError in _time_str_to_time_today is caught, returns None."""
    from conftest import MOCK_DEVICE_RESPONSE
    from copy import deepcopy
    from unittest.mock import patch as _patch

    device = PoolCopDevice.from_dict(deepcopy(MOCK_DEVICE_RESPONSE))
    data = PoolCopData(device=device, pool=Pool.from_dict({"id": 1, "timezone": "UTC"}))
    fn = _filtration_timer_time_fn(0, "time_on")

    with _patch(
        "custom_components.poolcop.sensor._time_str_to_time_today",
        side_effect=AttributeError("tz error"),
    ):
        result = fn(data)
    assert result is None


async def test_aux_timer_time_tz_error():
    """AttributeError in _time_str_to_time_today for aux timer is caught."""
    from conftest import MOCK_DEVICE_RESPONSE
    from copy import deepcopy
    from unittest.mock import patch as _patch

    device_data = deepcopy(MOCK_DEVICE_RESPONSE)
    device_data["settings"]["auxs"]["None"]["Aux4"]["timers"] = [
        {"id": 1, "timeOn": "14:00:00", "timeOff": "18:00:00"}
    ]
    device = PoolCopDevice.from_dict(device_data)
    data = PoolCopData(device=device, pool=Pool.from_dict({"id": 1, "timezone": "UTC"}))
    fn = _aux_timer_time_fn("Aux4", 0, "time_on")

    with _patch(
        "custom_components.poolcop.sensor._time_str_to_time_today",
        side_effect=KeyError("tz error"),
    ):
        result = fn(data)
    assert result is None
