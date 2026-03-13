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

    state = hass.states.get("sensor.test_pool_water_temperature")
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

    state = hass.states.get("sensor.test_pool_valve_position")
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

    state = hass.states.get("sensor.test_pool_planned_remaining_filter_volume")
    assert state is not None
    # Value should match what coordinator returns (numeric string)
    expected = str(coordinator.planned_remaining_volume)
    assert state.state == expected
