"""Test PoolCop service functionality."""

from __future__ import annotations

from unittest.mock import patch


from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import (
    DOMAIN,
    SERVICE_CLEAR_ALARM,
    SERVICE_SET_AUX,
    SERVICE_SET_PUMP,
    SERVICE_SET_PUMP_SPEED,
    SERVICE_SET_VALVE_POSITION,
)


async def _setup_integration(
    hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
):
    """Set up the integration for service tests."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.poolcop.PoolCopCloudAPI",
        return_value=mock_cloud_api,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_service_set_pump(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test the set_pump service."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PUMP,
        {"on": True},
        blocking=True,
    )
    mock_cloud_api.set_pump.assert_called_with(12345, on=True)


async def test_service_set_pump_speed(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test the set_pump_speed service."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PUMP_SPEED,
        {"speed": "Speed2"},
        blocking=True,
    )
    mock_cloud_api.set_pump_speed.assert_called_with(12345, "Speed2")


async def test_service_set_valve_position(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test the set_valve_position service."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        {"position": "Backwash"},
        blocking=True,
    )
    mock_cloud_api.set_valve_position.assert_called_with(12345, "Backwash")


async def test_service_set_aux(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test the set_aux service."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_AUX,
        {"module": "AuxModule1", "aux": "Aux1", "on": True},
        blocking=True,
    )
    mock_cloud_api.set_auxiliary.assert_called_with(
        12345, "AuxModule1", "Aux1", on=True
    )


async def test_service_clear_alarm(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test the clear_alarm service."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_ALARM,
        {"code": "AL01"},
        blocking=True,
    )
    mock_cloud_api.clear_alarm.assert_called_with(12345, "AL01")


async def test_service_clear_alarm_all(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test the clear_alarm service without code clears all."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_ALARM,
        {},
        blocking=True,
    )
    # Should call clear_alarm for each active alarm
    mock_cloud_api.clear_alarm.assert_called()
