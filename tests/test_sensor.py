"""Test PoolCop sensor entities."""

from __future__ import annotations

from unittest.mock import patch


from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import DOMAIN

from .conftest import make_pump_info, make_state


async def _setup_integration(
    hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
):
    """Set up the integration for sensor tests."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.poolcop.PoolCopCloudAPI",
        return_value=mock_cloud_api,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_water_temperature_sensor(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test water temperature sensor."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    # The entity_id format depends on HA entity naming
    # Check all sensor states
    sensors = [s for s in hass.states.async_all("sensor") if "poolcop" in s.entity_id]
    # Verify we have sensors registered
    assert len(sensors) > 0


async def test_sensor_values(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test that sensor entities are created."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    # Check coordinator has data
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.data is not None
    assert coordinator.data.state.water_temperature == 26.5
    assert coordinator.data.state.ph == 7.2
    assert coordinator.data.state.orp == 650


async def test_sensor_with_pump_off(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test sensors when pump is off."""
    mock_cloud_api.get_state.return_value = make_state(
        pumps=[make_pump_info(pump_state=False, current_speed="None")]
    )
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.data.pump.pump_state is False
    assert coordinator.get_current_flow_rate() == 0.0


async def test_settings_sensors(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test settings sensors read from config endpoints."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.data.pool_config is not None
    assert coordinator.data.pool_config["volume"] == 50.0
    assert coordinator.data.pump_config is not None
    assert coordinator.data.pump_config["nbSpeed"] == 3
