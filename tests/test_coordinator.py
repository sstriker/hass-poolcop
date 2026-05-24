"""Test PoolCop coordinator functionality."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from aiopoolcop import (
    Pool,
    PoolCopClientAuthError,
    PoolCopClientConnectionError,
    PoolCopClientRateLimitError,
    PoolCopDevice,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import ConfigEntryAuthFailed, UpdateFailed

from custom_components.poolcop.coordinator import (
    PoolCopData,
    PoolCopDataUpdateCoordinator,
)


def _make_coordinator(hass, api, config_entry):
    """Create a coordinator with mocked storage."""
    coordinator = PoolCopDataUpdateCoordinator(
        hass, api, 2478, config_entry
    )
    coordinator._store.async_save = AsyncMock()
    coordinator._store.async_load = AsyncMock(return_value=None)
    return coordinator


async def test_coordinator_update(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Test the coordinator update method."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(mock_device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(mock_pool_data)]
    mock_config_entry.add_to_hass(hass)

    coordinator = _make_coordinator(hass, mock_poolcop_api, mock_config_entry)
    data = await coordinator._async_update_data()

    assert isinstance(data, PoolCopData)
    assert data.device.id == 2478
    assert data.device.state.water_temperature == 27.2
    mock_poolcop_api.get_device.assert_called_once_with(2478)


async def test_coordinator_connection_error(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api
):
    """Test error handling on connection failure."""
    mock_poolcop_api.get_device.side_effect = PoolCopClientConnectionError("Connection error")
    mock_config_entry.add_to_hass(hass)

    coordinator = _make_coordinator(hass, mock_poolcop_api, mock_config_entry)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_auth_error_triggers_reauth(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api
):
    """Test that auth error triggers ConfigEntryAuthFailed."""
    mock_poolcop_api.get_device.side_effect = PoolCopClientAuthError("Invalid key")
    mock_config_entry.add_to_hass(hass)

    coordinator = _make_coordinator(hass, mock_poolcop_api, mock_config_entry)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_rate_limit_raises_update_failed(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api
):
    """Rate limit raises UpdateFailed."""
    mock_poolcop_api.get_device.side_effect = PoolCopClientRateLimitError(
        "Rate limit", retry_after=60
    )
    mock_config_entry.add_to_hass(hass)

    coordinator = _make_coordinator(hass, mock_poolcop_api, mock_config_entry)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    # Should adjust update_interval based on retry_after
    assert coordinator.update_interval.total_seconds() == 60


async def test_coordinator_flow_rates_from_options(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api
):
    """Test that coordinator reads flow rates from options."""
    mock_config_entry.add_to_hass(hass)

    coordinator = _make_coordinator(hass, mock_poolcop_api, mock_config_entry)

    assert coordinator.flow_rates[1] == 10.0
    assert coordinator.flow_rates[2] == 15.0
    assert coordinator.flow_rates[3] == 20.0


async def test_coordinator_set_pump(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Test set_pump delegates to API."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(mock_device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(mock_pool_data)]
    mock_config_entry.add_to_hass(hass)

    coordinator = _make_coordinator(hass, mock_poolcop_api, mock_config_entry)
    coordinator.data = await coordinator._async_update_data()

    await coordinator.set_pump(on=False)
    mock_poolcop_api.set_pump.assert_called_once_with(2478, on=False)


async def test_coordinator_set_valve_position(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Test set_valve_position delegates to API."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(mock_device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(mock_pool_data)]
    mock_config_entry.add_to_hass(hass)

    coordinator = _make_coordinator(hass, mock_poolcop_api, mock_config_entry)
    coordinator.data = await coordinator._async_update_data()

    await coordinator.set_valve_position("Backwash")
    mock_poolcop_api.set_valve_position.assert_called_once_with(2478, "Backwash")


async def test_coordinator_clear_all_alarms(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Test clear_all_alarms delegates to API."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(mock_device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(mock_pool_data)]
    mock_config_entry.add_to_hass(hass)

    coordinator = _make_coordinator(hass, mock_poolcop_api, mock_config_entry)
    coordinator.data = await coordinator._async_update_data()

    await coordinator.clear_all_alarms()
    mock_poolcop_api.clear_all_alarms.assert_called_once_with(2478)


async def test_save_load_learned_data(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api
):
    """Cycle durations round-trip through mocked storage."""
    mock_config_entry.add_to_hass(hass)
    coordinator = _make_coordinator(hass, mock_poolcop_api, mock_config_entry)

    # Save
    coordinator._daily_volume = 1.234
    coordinator._daily_volume_date = "2026-03-15"
    await coordinator.async_save_learned_data()
    coordinator._store.async_save.assert_called_once()
    saved = coordinator._store.async_save.call_args[0][0]
    assert "cycle_durations" in saved
    assert "flow_rates" in saved
    assert saved["daily_volume"] == 1.234
    assert saved["daily_volume_date"] == "2026-03-15"

    # Load
    today = datetime.now().strftime("%Y-%m-%d")
    coordinator._store.async_load = AsyncMock(
        return_value={
            "cycle_durations": {"1": 9999},
            "flow_rates": {"2": 18.0},
            "daily_volume": 2.567,
            "daily_volume_date": today,
        }
    )
    await coordinator.async_load_learned_data()
    assert coordinator._cycle_durations[1] == 9999
    assert coordinator.flow_rates[2] == 18.0
    assert coordinator._daily_volume == 2.567


async def test_load_stale_daily_volume_discarded(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api
):
    """Daily volume from a previous day is not restored."""
    mock_config_entry.add_to_hass(hass)
    coordinator = _make_coordinator(hass, mock_poolcop_api, mock_config_entry)

    coordinator._store.async_load = AsyncMock(
        return_value={
            "cycle_durations": {},
            "flow_rates": {},
            "daily_volume": 5.0,
            "daily_volume_date": "2020-01-01",
        }
    )
    await coordinator.async_load_learned_data()
    assert coordinator._daily_volume == 0.0


async def test_daily_volume_date_exception(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """datetime.now() exception does not crash _update_daily_volume."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(mock_device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(mock_pool_data)]
    mock_config_entry.add_to_hass(hass)

    coordinator = _make_coordinator(hass, mock_poolcop_api, mock_config_entry)
    coordinator.data = await coordinator._async_update_data()

    with patch("custom_components.poolcop.coordinator.datetime") as mock_dt:
        mock_dt.now.side_effect = RuntimeError("broken clock")
        coordinator._update_daily_volume()

    assert coordinator._last_flow_update is not None


async def test_set_forced_filtration(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Test set_forced_filtration delegates to API."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(mock_device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(mock_pool_data)]
    mock_config_entry.add_to_hass(hass)

    coordinator = _make_coordinator(hass, mock_poolcop_api, mock_config_entry)
    coordinator.data = await coordinator._async_update_data()

    await coordinator.set_forced_filtration("Forced24H")
    mock_poolcop_api.set_pump_forced.assert_called_once_with(2478, "Forced24H")
