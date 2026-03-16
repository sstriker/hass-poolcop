"""Test PoolCop coordinator functionality."""

from __future__ import annotations


import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from aiopoolcop import (
    PoolCopCloudAuthError,
    PoolCopCloudConnectionError,
    PoolCopCloudRateLimitError,
)

from custom_components.poolcop.coordinator import (
    PoolCopData,
    PoolCopDataUpdateCoordinator,
)

from .conftest import make_alarm, make_state, make_pump_info


async def test_coordinator_update(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test the coordinator update method."""
    mock_config_entry.add_to_hass(hass)

    coordinator = PoolCopDataUpdateCoordinator(
        hass, mock_cloud_api, 12345, mock_config_entry
    )
    data = await coordinator._async_update_data()

    assert isinstance(data, PoolCopData)
    assert data.state.water_temperature == 26.5
    assert data.state.ph == 7.2
    assert data.pump is not None
    assert data.pump.pump_state is True
    assert data.device.nickname == "My PoolCop"
    assert data.pool is not None
    assert data.pool.nickname == "My Pool"

    mock_cloud_api.get_state.assert_called_once_with(12345)
    mock_cloud_api.get_alarms.assert_called_once_with(12345)
    mock_cloud_api.get_auxiliaries.assert_called_once_with(12345)


async def test_coordinator_auth_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_storage,
):
    """Test auth error raises ConfigEntryAuthFailed."""
    from homeassistant.helpers.update_coordinator import ConfigEntryAuthFailed

    mock_cloud_api.get_state.side_effect = PoolCopCloudAuthError("Token expired")
    mock_config_entry.add_to_hass(hass)

    coordinator = PoolCopDataUpdateCoordinator(
        hass, mock_cloud_api, 12345, mock_config_entry
    )
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_connection_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_storage,
):
    """Test connection error raises UpdateFailed."""
    mock_cloud_api.get_state.side_effect = PoolCopCloudConnectionError(
        "Connection failed"
    )
    mock_config_entry.add_to_hass(hass)

    coordinator = PoolCopDataUpdateCoordinator(
        hass, mock_cloud_api, 12345, mock_config_entry
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_rate_limit_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_storage,
):
    """Test rate limit error raises UpdateFailed and adjusts interval."""
    err = PoolCopCloudRateLimitError("Rate limited")
    err.retry_after = 120
    mock_cloud_api.get_state.side_effect = err
    mock_config_entry.add_to_hass(hass)

    coordinator = PoolCopDataUpdateCoordinator(
        hass, mock_cloud_api, 12345, mock_config_entry
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert coordinator.update_interval.total_seconds() == 120


async def test_coordinator_flow_rates(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_storage,
):
    """Test flow rate initialization from config entry options."""
    mock_config_entry.add_to_hass(hass)

    coordinator = PoolCopDataUpdateCoordinator(
        hass, mock_cloud_api, 12345, mock_config_entry
    )
    assert coordinator.flow_rates == {
        "Speed1": 10.0,
        "Speed2": 15.0,
        "Speed3": 20.0,
    }


async def test_get_current_flow_rate(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_storage,
):
    """Test current flow rate calculation."""
    mock_config_entry.add_to_hass(hass)

    coordinator = PoolCopDataUpdateCoordinator(
        hass, mock_cloud_api, 12345, mock_config_entry
    )

    # No data yet
    assert coordinator.get_current_flow_rate() == 0.0

    # After update
    coordinator.data = await coordinator._async_update_data()
    # Pump is on at Speed1, valve at Filter -> flow_rate_1 = 10.0
    assert coordinator.get_current_flow_rate() == 10.0


async def test_get_current_flow_rate_pump_off(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_storage,
):
    """Test flow rate is 0 when pump is off."""
    mock_cloud_api.get_state.return_value = make_state(
        pumps=[make_pump_info(pump_state=False)]
    )
    mock_config_entry.add_to_hass(hass)

    coordinator = PoolCopDataUpdateCoordinator(
        hass, mock_cloud_api, 12345, mock_config_entry
    )
    coordinator.data = await coordinator._async_update_data()
    assert coordinator.get_current_flow_rate() == 0.0


async def test_get_current_flow_rate_valve_closed(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_storage,
):
    """Test flow rate is 0 when valve is in non-flowing position."""
    mock_cloud_api.get_state.return_value = make_state(
        pumps=[make_pump_info(valve_position="Closed")]
    )
    mock_config_entry.add_to_hass(hass)

    coordinator = PoolCopDataUpdateCoordinator(
        hass, mock_cloud_api, 12345, mock_config_entry
    )
    coordinator.data = await coordinator._async_update_data()
    assert coordinator.get_current_flow_rate() == 0.0


async def test_coordinator_commands(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_storage,
):
    """Test coordinator command methods."""
    mock_config_entry.add_to_hass(hass)

    coordinator = PoolCopDataUpdateCoordinator(
        hass, mock_cloud_api, 12345, mock_config_entry
    )

    await coordinator.set_pump(on=True)
    mock_cloud_api.set_pump.assert_called_once_with(12345, on=True)

    await coordinator.set_pump_speed("Speed2")
    mock_cloud_api.set_pump_speed.assert_called_once_with(12345, "Speed2")

    await coordinator.set_valve_position("Backwash")
    mock_cloud_api.set_valve_position.assert_called_once_with(12345, "Backwash")

    await coordinator.set_auxiliary("AuxModule1", "Aux1", on=True)
    mock_cloud_api.set_auxiliary.assert_called_once_with(
        12345, "AuxModule1", "Aux1", on=True
    )

    await coordinator.clear_alarm("AL01")
    mock_cloud_api.clear_alarm.assert_called_once_with(12345, "AL01")


async def test_coordinator_clear_all_alarms(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_storage,
):
    """Test clearing all active alarms."""
    mock_config_entry.add_to_hass(hass)

    coordinator = PoolCopDataUpdateCoordinator(
        hass, mock_cloud_api, 12345, mock_config_entry
    )
    coordinator.data = await coordinator._async_update_data()

    await coordinator.clear_all_alarms()
    mock_cloud_api.clear_alarm.assert_called_once_with(12345, "AL01")


async def test_coordinator_clear_all_alarms_skips_inactive(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_storage,
):
    """Test clear_all_alarms skips inactive alarms."""
    mock_cloud_api.get_alarms.return_value = [
        make_alarm(active=True, code="AL01"),
        make_alarm(active=False, code="AL02", id=2),
    ]
    mock_config_entry.add_to_hass(hass)

    coordinator = PoolCopDataUpdateCoordinator(
        hass, mock_cloud_api, 12345, mock_config_entry
    )
    coordinator.data = await coordinator._async_update_data()

    await coordinator.clear_all_alarms()
    # Only AL01 should be cleared
    mock_cloud_api.clear_alarm.assert_called_once_with(12345, "AL01")


async def test_coordinator_config_fetch(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_storage,
):
    """Test that config endpoints are fetched on first update."""
    mock_config_entry.add_to_hass(hass)

    coordinator = PoolCopDataUpdateCoordinator(
        hass, mock_cloud_api, 12345, mock_config_entry
    )
    data = await coordinator._async_update_data()

    # Configs should be fetched on first call (last_config_fetch == 0)
    assert data.pump_config is not None
    assert data.pump_config["nbSpeed"] == 3
    assert data.pool_config is not None
    assert data.pool_config["volume"] == 50.0
    mock_cloud_api.get_pump_config.assert_called_once_with(12345)


async def test_coordinator_daily_volume(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_storage,
):
    """Test daily volume tracking."""
    mock_config_entry.add_to_hass(hass)

    coordinator = PoolCopDataUpdateCoordinator(
        hass, mock_cloud_api, 12345, mock_config_entry
    )
    # Initial volume is 0
    assert coordinator.daily_volume == 0.0

    # After first update, volume is still 0 (no elapsed time yet)
    await coordinator._async_update_data()
    assert coordinator.daily_volume == 0.0


async def test_coordinator_daily_turnovers(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_storage,
):
    """Test daily turnover calculation."""
    mock_config_entry.add_to_hass(hass)

    coordinator = PoolCopDataUpdateCoordinator(
        hass, mock_cloud_api, 12345, mock_config_entry
    )
    # No data yet
    assert coordinator.daily_turnovers is None

    coordinator.data = await coordinator._async_update_data()
    # Volume is 0, pool_config volume is 50, so turnovers = 0/50 = 0
    assert coordinator.daily_turnovers == 0.0


async def test_coordinator_save_load_learned_data(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_storage,
):
    """Test saving and loading learned data."""
    mock_config_entry.add_to_hass(hass)

    coordinator = PoolCopDataUpdateCoordinator(
        hass, mock_cloud_api, 12345, mock_config_entry
    )
    await coordinator.async_save_learned_data()
    mock_storage.async_save.assert_called_once()

    await coordinator.async_load_learned_data()
    mock_storage.async_load.assert_called_once()


def test_poolcop_data_has_active_alarms(
    mock_poolcop_state, mock_poolcop_device, mock_pool
):
    """Test PoolCopData.has_active_alarms()."""
    data = PoolCopData(
        device=mock_poolcop_device,
        state=mock_poolcop_state,
        alarms=[make_alarm(active=True)],
        auxiliaries=[],
        pool=mock_pool,
    )
    assert data.has_active_alarms() is True

    data_no_alarms = PoolCopData(
        device=mock_poolcop_device,
        state=mock_poolcop_state,
        alarms=[make_alarm(active=False)],
        auxiliaries=[],
        pool=mock_pool,
    )
    assert data_no_alarms.has_active_alarms() is False


def test_poolcop_data_pump_property(mock_poolcop_state, mock_poolcop_device, mock_pool):
    """Test PoolCopData.pump property."""
    data = PoolCopData(
        device=mock_poolcop_device,
        state=mock_poolcop_state,
        alarms=[],
        auxiliaries=[],
        pool=mock_pool,
    )
    assert data.pump is not None
    assert data.pump.pump_state is True

    # No pumps
    state_no_pumps = make_state(pumps=[])
    data_no_pump = PoolCopData(
        device=mock_poolcop_device,
        state=state_no_pumps,
        alarms=[],
        auxiliaries=[],
        pool=mock_pool,
    )
    assert data_no_pump.pump is None
