"""Test PoolCop service functionality."""

from unittest.mock import patch

from aiopoolcop import Pool, PoolCopDevice
from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import (
    DOMAIN,
    SERVICE_CLEAR_ALARM,
    SERVICE_SET_PUMP_SPEED,
    SERVICE_SET_VALVE_POSITION,
    SERVICE_TOGGLE_AUX,
    SERVICE_TOGGLE_PUMP,
)


async def _setup(hass, mock_config_entry, mock_poolcop_api, device_data, pool_data):
    """Set up integration."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(pool_data)]
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.poolcop.PoolCopClientAPI", return_value=mock_poolcop_api):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_service_toggle_pump(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Toggle pump service calls set_pump."""
    await _setup(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    await hass.services.async_call(DOMAIN, SERVICE_TOGGLE_PUMP, {}, blocking=True)
    # Pump is on (pumpState=True), so toggle should set on=False
    mock_poolcop_api.set_pump.assert_called_once_with(2478, on=False)


async def test_service_set_pump_speed(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Set pump speed service calls set_pump_speed."""
    await _setup(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_PUMP_SPEED, {"speed": "Speed2"}, blocking=True
    )
    mock_poolcop_api.set_pump_speed.assert_called_once_with(2478, "Speed2")


async def test_service_toggle_aux(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Toggle aux service calls set_auxiliary."""
    # Aux1 is True in mock data, so toggle should set on=False
    await _setup(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE_AUX, {"aux_id": 1}, blocking=True
    )
    mock_poolcop_api.set_auxiliary.assert_called_once_with(2478, "None", 1, on=False)


async def test_service_set_valve_position(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Set valve position service calls set_valve_position."""
    await _setup(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_VALVE_POSITION, {"position": "Filter"}, blocking=True
    )
    mock_poolcop_api.set_valve_position.assert_called_once_with(2478, "Filter")


async def test_service_clear_alarm(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Clear alarm service calls clear_all_alarms."""
    await _setup(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    await hass.services.async_call(DOMAIN, SERVICE_CLEAR_ALARM, {}, blocking=True)
    mock_poolcop_api.clear_all_alarms.assert_called_once_with(2478)


async def test_service_error_handling(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """ConnectionError is logged, not raised."""
    await _setup(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    mock_poolcop_api.set_pump_speed.side_effect = ConnectionError("offline")

    # Should not raise
    await hass.services.async_call(
        DOMAIN, SERVICE_SET_PUMP_SPEED, {"speed": "Speed2"}, blocking=True
    )


async def test_service_registration_idempotent(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Double register does not crash."""
    from custom_components.poolcop.service import async_setup_services

    await _setup(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    await async_setup_services(hass)
    assert hass.services.has_service(DOMAIN, SERVICE_SET_PUMP_SPEED)


async def test_service_unload_not_registered(hass: HomeAssistant):
    """Unload when not registered does not crash."""
    from custom_components.poolcop.service import async_unload_services

    await async_unload_services(hass)
    assert not hass.services.has_service(DOMAIN, SERVICE_SET_PUMP_SPEED)
