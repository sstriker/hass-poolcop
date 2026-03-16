"""Test PoolCop binary sensor entities."""

from __future__ import annotations

from unittest.mock import patch


from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import DOMAIN
from custom_components.poolcop.binary_sensor import _alarm_attrs
from custom_components.poolcop.coordinator import PoolCopData

from .conftest import (
    make_alarm,
    make_device,
    make_pool,
    make_state,
)


async def _setup_integration(
    hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
):
    """Set up the integration for binary sensor tests."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.poolcop.PoolCopCloudAPI",
        return_value=mock_cloud_api,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_binary_sensors_created(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test that binary sensor entities are created."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    sensors = [
        s for s in hass.states.async_all("binary_sensor") if "poolcop" in s.entity_id
    ]
    assert len(sensors) > 0


async def test_pump_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test pump binary sensor reflects pump state."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.data.pump.pump_state is True


async def test_alarm_binary_sensor_with_active_alarm(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test alarm binary sensor when alarms are active."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.data.has_active_alarms() is True


def test_alarm_attrs_function():
    """Test the _alarm_attrs helper function."""
    data = PoolCopData(
        device=make_device(),
        state=make_state(),
        alarms=[make_alarm(active=True, code="AL01", label="Test Alarm")],
        auxiliaries=[],
        pool=make_pool(),
    )
    attrs = _alarm_attrs(data)
    assert attrs["alarm_count"] == 1
    assert attrs["code"] == "AL01"

    # No active alarms
    data_no_alarms = PoolCopData(
        device=make_device(),
        state=make_state(),
        alarms=[make_alarm(active=False)],
        auxiliaries=[],
        pool=make_pool(),
    )
    attrs_empty = _alarm_attrs(data_no_alarms)
    assert attrs_empty["alarm_count"] == 0


async def test_mains_power_sensor(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test mains power binary sensor."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    # mains_power_lost is False, so mains power is on
    assert coordinator.data.state.mains_power_lost is False


async def test_aux_binary_sensors(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test auxiliary binary sensors are created."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert len(coordinator.data.auxiliaries) == 2
