"""Test PoolCop sensor platform."""

from datetime import datetime
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import DOMAIN, OPERATION_MODES
from custom_components.poolcop.coordinator import PoolCopData
from custom_components.poolcop.sensor import (
    _cycle_time_remaining_fn,
    _datetime_value_fn,
    _state_mapping_fn,
    _time_str_to_time_today,
    _weekday_mapping_fn,
)


async def _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data):
    """Set up the integration and return the coordinator."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return hass.data[DOMAIN][mock_config_entry.entry_id]


async def test_sensor_platform_setup(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Key sensors exist after setup."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    states = hass.states.async_all("sensor")
    sensor_keys = {s.entity_id for s in states}
    # At minimum, water temperature and operation mode should exist
    assert any("water_temperature" in s for s in sensor_keys)
    assert any("operation_mode" in s for s in sensor_keys)


async def test_water_temperature_value(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """State == '26.5'."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("sensor.poolcop_test_poolcop_id_water_temperature")
    assert state is not None
    assert state.state == "26.5"


async def test_operation_mode_enum(mock_poolcop_data):
    """Numeric 3 → 'Auto' string."""
    data = PoolCopData(status=mock_poolcop_data)
    fn = _state_mapping_fn("status.poolcop", OPERATION_MODES)
    assert fn(data) == "Auto"


async def test_sensor_extra_attrs(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """valve_position sensor has description attr."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("sensor.poolcop_test_poolcop_id_valve_position")
    if state is not None:
        assert "description" in state.attributes


async def test_datetime_value_fn_epoch_guard():
    """Pre-2000 date → None."""
    data = PoolCopData(
        status={"PoolCop": {"history": {"backwash": "1970-01-01T00:00:00+0000"}}}
    )
    fn = _datetime_value_fn("history.backwash")
    assert fn(data) is None


async def test_datetime_value_fn_valid():
    """Valid date → correct datetime."""
    data = PoolCopData(
        status={"PoolCop": {"history": {"backwash": "2023-04-15T10:30:00+0200"}}}
    )
    fn = _datetime_value_fn("history.backwash")
    result = fn(data)
    assert isinstance(result, datetime)
    assert result.year == 2023


async def test_cycle_status_sensors():
    """remaining_time reflected via _cycle_time_remaining_fn."""
    data = PoolCopData(
        status={"PoolCop": {"status": {"poolcop": 3}}},
        cycle_status={
            "remaining_time": 120.5,
            "elapsed_time": 300,
            "predicted_end": None,
        },
    )
    result = _cycle_time_remaining_fn(data)
    assert result == 120.5


async def test_weekday_mapping_fn():
    """0-6 → correct days, invalid → None."""
    fn = _weekday_mapping_fn("settings.orp.hyper_day")
    data_mon = PoolCopData(status={"PoolCop": {"settings": {"orp": {"hyper_day": 1}}}})
    assert fn(data_mon) == "Monday"

    data_dis = PoolCopData(status={"PoolCop": {"settings": {"orp": {"hyper_day": 0}}}})
    assert fn(data_dis) == "Disabled"

    data_none = PoolCopData(status={"PoolCop": {"settings": {"orp": {}}}})
    assert fn(data_none) is None

    data_invalid = PoolCopData(
        status={"PoolCop": {"settings": {"orp": {"hyper_day": 99}}}}
    )
    assert fn(data_invalid) is None


async def test_time_str_to_time_today_invalid_tz():
    """Invalid tz → fallback (still returns a datetime)."""
    result = _time_str_to_time_today("14:00:00", "Invalid/Timezone")
    # Should fallback to local timezone and still produce a result
    assert result is not None
    assert result.hour == 14


async def test_aux_timer_sensors_created(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Aux with timer in timers dict → timer entities created."""
    # Add a timer for aux4 (which is switchable with label_aux_6 = Transfer Pump)
    mock_poolcop_data["PoolCop"]["timers"]["aux4"] = {
        "enabled": 1,
        "start": "10:00:00",
        "stop": "12:00:00",
    }
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    states = hass.states.async_all("sensor")
    sensor_keys = {s.entity_id for s in states}
    # Should have transfer_pump_enabled and transfer_pump_start_time sensors
    assert any("transfer_pump_enabled" in s for s in sensor_keys)


async def test_planned_remaining_sensors_exist(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Planned remaining volume and turnovers sensors are created."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    states = hass.states.async_all("sensor")
    sensor_keys = {s.entity_id for s in states}
    assert any("planned_remaining_filter_volume" in s for s in sensor_keys)
    assert any("planned_remaining_turnovers" in s for s in sensor_keys)


async def test_planned_remaining_volume_value(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Planned remaining volume sensor reflects coordinator property."""
    coordinator = await _setup_integration(
        hass, mock_config_entry, mock_poolcop, mock_poolcop_data
    )

    state = hass.states.get("sensor.poolcop_test_poolcop_id_planned_remaining_filter_volume")
    assert state is not None
    # Value should match what coordinator returns (numeric string)
    expected = str(coordinator.planned_remaining_volume)
    assert state.state == expected


async def test_cycle_time_remaining_fn_no_remaining_time():
    """_cycle_time_remaining_fn returns None when cycle_status has no remaining_time (line 133)."""
    # In cycle mode (mode 3 = Auto) but cycle_status has no remaining_time
    data = PoolCopData(
        status={"PoolCop": {"status": {"poolcop": 3}}},
        cycle_status={},
    )
    result = _cycle_time_remaining_fn(data)
    assert result is None


async def test_cycle_time_remaining_fn_not_in_cycle_mode():
    """_cycle_time_remaining_fn returns None when not in cycle mode."""
    data = PoolCopData(
        status={"PoolCop": {"status": {"poolcop": 0}}},  # mode 0 = Stop
        cycle_status={"remaining_time": 120},
    )
    result = _cycle_time_remaining_fn(data)
    assert result is None


async def test_cycle_end_time_fn_not_in_cycle():
    """_cycle_end_time_fn returns None when not in cycle mode (line 142)."""
    from custom_components.poolcop.sensor import _cycle_end_time_fn

    data = PoolCopData(
        status={"PoolCop": {"status": {"poolcop": 0}}},
        cycle_status={"predicted_end": 9999999999},
    )
    assert _cycle_end_time_fn(data) is None


async def test_cycle_end_time_fn_with_predicted_end():
    """_cycle_end_time_fn returns datetime when predicted_end exists (lines 144-145)."""
    import time

    from custom_components.poolcop.sensor import _cycle_end_time_fn

    now_ts = time.time() + 300  # 5 minutes from now
    data = PoolCopData(
        status={"PoolCop": {"status": {"poolcop": 3}}},
        cycle_status={"predicted_end": now_ts},
    )
    result = _cycle_end_time_fn(data)
    assert isinstance(result, datetime)


async def test_cycle_elapsed_time_fn_not_in_cycle():
    """_cycle_elapsed_time_fn returns None when not in cycle mode (line 152)."""
    from custom_components.poolcop.sensor import _cycle_elapsed_time_fn

    data = PoolCopData(
        status={"PoolCop": {"status": {"poolcop": 0}}},
        cycle_status={"elapsed_time": 120},
    )
    assert _cycle_elapsed_time_fn(data) is None


async def test_cycle_elapsed_time_fn_no_elapsed():
    """_cycle_elapsed_time_fn returns None when no elapsed_time (line 154)."""
    from custom_components.poolcop.sensor import _cycle_elapsed_time_fn

    data = PoolCopData(
        status={"PoolCop": {"status": {"poolcop": 3}}},
        cycle_status={},
    )
    assert _cycle_elapsed_time_fn(data) is None

    # Also test with elapsed_time explicitly None
    data2 = PoolCopData(
        status={"PoolCop": {"status": {"poolcop": 3}}},
        cycle_status={"elapsed_time": None},
    )
    assert _cycle_elapsed_time_fn(data2) is None

    # Test with valid elapsed_time to cover line 154
    data3 = PoolCopData(
        status={"PoolCop": {"status": {"poolcop": 3}}},
        cycle_status={"elapsed_time": 300},
    )
    assert _cycle_elapsed_time_fn(data3) == 300


async def test_time_str_to_time_today_tomorrow_shift():
    """_time_str_to_time_today shifts to tomorrow when result < now and hour < 12 (line 171)."""
    from unittest.mock import patch as mock_patch

    real_datetime = datetime

    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz:
                return real_datetime(2026, 3, 14, 23, 0, 0, tzinfo=tz)
            return real_datetime(2026, 3, 14, 23, 0, 0)

    with mock_patch("custom_components.poolcop.sensor.datetime", FakeDatetime):
        result = _time_str_to_time_today("02:00:00", "UTC")

    # 02:00 < 23:00 and hour 2 < 12, so result shifts to tomorrow
    assert result is not None
    assert result.day == 15


async def test_time_str_to_time_today_falsy_input():
    """_time_str_to_time_today returns None for falsy or '00:00:00' input (line 171)."""
    assert _time_str_to_time_today("", "UTC") is None
    assert _time_str_to_time_today("00:00:00", "UTC") is None
    assert _time_str_to_time_today(None, "UTC") is None


async def test_time_str_to_time_today_value_error():
    """_time_str_to_time_today returns None for invalid time_str (lines 201-202)."""
    result = _time_str_to_time_today("invalid", "UTC")
    assert result is None

    result = _time_str_to_time_today("not:a:time", "UTC")
    assert result is None


async def test_timer_fn_exception():
    """_timer_fn handles KeyError/AttributeError (lines 215-216)."""
    from custom_components.poolcop.sensor import _timer_fn

    # Timer data that is not a dict → timer.get() would raise AttributeError
    data = PoolCopData(
        status={"PoolCop": {"timers": {"cycle1": "not_a_dict"}}},
    )
    fn = _timer_fn("cycle1", "enabled")
    result = fn(data)
    assert result is None


async def test_timer_time_fn_exception():
    """_timer_time_fn handles exceptions (lines 236-237)."""
    from custom_components.poolcop.sensor import _timer_time_fn

    # Timer data is a non-dict truthy value → .get() raises AttributeError
    data = PoolCopData(
        status={
            "PoolCop": {"timers": {"cycle1": "corrupted_data"}},
            "Pool": {"timezone": "UTC"},
        },
    )
    fn = _timer_time_fn("cycle1", "start")
    result = fn(data)
    assert result is None


async def test_weekday_mapping_fn_non_integer_value():
    """_weekday_mapping_fn returns None for non-integer value (lines 264-265)."""
    fn = _weekday_mapping_fn("settings.orp.hyper_day")
    data = PoolCopData(status={"PoolCop": {"settings": {"orp": {"hyper_day": "bad"}}}})
    assert fn(data) is None


async def test_aux_timer_fixed_function_label_skipped(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Aux with fixed-function label and timer entry → skipped (line 889)."""
    # aux1 has label_aux_17 which is in AUX_FIXED_FUNCTION_LABELS (17)
    # Add a timer for aux1 — it should be skipped
    mock_poolcop_data["PoolCop"]["timers"]["aux1"] = {
        "enabled": 1,
        "start": "10:00:00",
        "stop": "12:00:00",
    }
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    states = hass.states.async_all("sensor")
    sensor_keys = {s.entity_id for s in states}
    # Should NOT create sensors for aux1 since label_aux_17 is fixed-function
    assert not any("aux1_enabled" in s for s in sensor_keys)


async def test_sensor_available_fn_returns_false(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Sensor with available_fn that returns False → unavailable (line 944)."""
    from custom_components.poolcop.sensor import (
        PoolCopSensorEntity,
        PoolCopSensorEntityDescription,
    )

    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]

    # Create a sensor with an available_fn that always returns False
    description = PoolCopSensorEntityDescription(
        key="test_unavailable",
        name="Test Unavailable",
        value_fn=lambda data: 42,
        available_fn=lambda data: False,
    )
    sensor = PoolCopSensorEntity(coordinator=coordinator, description=description)
    # The available property should return False
    assert sensor.available is False
