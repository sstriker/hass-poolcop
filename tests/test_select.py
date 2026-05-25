"""Test PoolCop select platform."""

from unittest.mock import patch

from aiopoolcop import Pool, PoolCopDevice
from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import DOMAIN


async def _setup_integration(hass, mock_config_entry, mock_poolcop_api, device_data, pool_data):
    """Set up the integration and return the coordinator."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(pool_data)]
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.poolcop.PoolCopClientAPI", return_value=mock_poolcop_api):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return hass.data[DOMAIN][mock_config_entry.entry_id]


async def test_valve_position_setup(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Valve position entity exists with correct options."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("select") if "valve_position" in s.entity_id]
    assert len(states) >= 1
    state = states[0]
    assert "Filter" in state.attributes.get("options", [])
    assert "Backwash" in state.attributes.get("options", [])


async def test_valve_position_current(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Valve position 'Filter' from mock data."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("select") if "valve_position" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "Filter"


async def test_valve_position_set(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Selecting 'Backwash' calls set_valve_position."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    valve_select = [s for s in hass.states.async_all("select") if "valve_position" in s.entity_id][0]
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": valve_select.entity_id, "option": "Backwash"},
        blocking=True,
    )
    mock_poolcop_api.set_valve_position.assert_called_once_with(2478, "Backwash")


async def test_pump_speed_options_3_speed(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """numberOfSpeeds=Speed3 -> options ['None', 'Speed1', 'Speed2', 'Speed3']."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("select") if "pump_speed" in s.entity_id]
    assert len(states) >= 1
    assert states[0].attributes.get("options") == ["None", "Speed1", "Speed2", "Speed3"]


async def test_pump_speed_current(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Current speed = Speed1."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("select") if "pump_speed" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "Speed1"


async def test_pump_speed_set(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Selecting 'Speed3' calls set_pump_speed."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    speed_select = [s for s in hass.states.async_all("select") if "pump_speed" in s.entity_id][0]
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": speed_select.entity_id, "option": "Speed3"},
        blocking=True,
    )
    mock_poolcop_api.set_pump_speed.assert_called_once_with(2478, "Speed3")


async def test_pump_speed_no_pumps(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """No pumps -> speed options fall back to ['None', 'Speed1']."""
    mock_device_data["state"]["pumpsInfo"] = []
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("select") if "pump_speed" in s.entity_id]
    assert len(states) >= 1
    assert states[0].attributes.get("options") == ["None", "Speed1"]


async def test_pump_speed_pump_off_shows_none(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Pump off -> current option is 'None'."""
    mock_device_data["state"]["pumpsInfo"][0]["pumpState"] = False
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("select") if "pump_speed" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "None"


async def test_valve_position_no_pumps(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """No pumps -> valve position returns None."""
    mock_device_data["state"]["pumpsInfo"] = []
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("select") if "valve_position" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "unknown"
