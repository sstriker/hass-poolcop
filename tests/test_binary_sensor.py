"""Test PoolCop binary sensor platform."""

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


async def test_binary_sensor_setup(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Core binary sensors exist: pump, active_alarm."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("binary_sensor")
    entity_ids = {s.entity_id for s in states}
    assert any("pump" in e for e in entity_ids)
    assert any("active_alarm" in e for e in entity_ids)


async def test_pump_binary_sensor_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Pump is on (pumpState=True) -> state 'on'."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if s.entity_id.endswith("_pump")]
    assert len(states) >= 1
    assert states[0].state == "on"


async def test_active_alarm_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Alarm present -> active_alarm is on."""
    # mock_device_data already has alarms: ["PressureLowPump1"]
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if "active_alarm" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "on"
    assert states[0].attributes.get("alarm_count", 0) >= 1


async def test_active_alarm_off(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """No alarms -> active_alarm is off."""
    mock_device_data["state"]["alarms"] = []
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if "active_alarm" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "off"


async def test_pump_icon(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Pump on -> mdi:pump icon."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if s.entity_id.endswith("_pump")]
    assert len(states) >= 1
    assert states[0].attributes.get("icon") == "mdi:pump"
