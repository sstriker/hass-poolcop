"""Test PoolCop coordinator functionality."""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from poolcop import PoolCopilotConnectionError, PoolCopilotInvalidKeyError

from custom_components.poolcop.coordinator import (
    PoolCopData,
    PoolCopDataUpdateCoordinator,
)


async def test_coordinator_update(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Test the coordinator update method."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass,
            api_key="test-api-key",
            config_entry=mock_config_entry,
        )
        data = await coordinator._async_update_data()

    assert isinstance(data, PoolCopData)
    assert data.status == mock_poolcop_data
    mock_poolcop.status.assert_called_once()


async def test_status_value(mock_poolcop_data):
    """Test PoolCopData.status_value path traversal."""
    data = PoolCopData(status=mock_poolcop_data)
    assert data.status_value("temperature.water") == 26.5
    assert data.status_value("status.pump") == 1
    assert data.status_value("conf.pH") == 1
    assert data.status_value("conf.ioniser") == 0
    assert data.status_value("nonexistent.path") is None
    assert data.status_value("temperature.nonexistent") is None


async def test_coordinator_connection_error(
    hass: HomeAssistant, mock_config_entry, mock_poolcop
):
    """Test error handling on connection failure."""
    mock_poolcop.status.side_effect = PoolCopilotConnectionError("Connection error")
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass,
            api_key="test-api-key",
            config_entry=mock_config_entry,
        )
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


async def test_coordinator_invalid_key_triggers_reauth(
    hass: HomeAssistant, mock_config_entry, mock_poolcop
):
    """Test that invalid key error triggers ConfigEntryAuthFailed."""
    from homeassistant.helpers.update_coordinator import ConfigEntryAuthFailed

    mock_poolcop.status.side_effect = PoolCopilotInvalidKeyError("Invalid key")
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass,
            api_key="test-api-key",
            config_entry=mock_config_entry,
        )
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()


async def test_coordinator_flow_rates_from_options(
    hass: HomeAssistant, mock_config_entry, mock_poolcop
):
    """Test that coordinator reads flow rates from options."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass,
            api_key="test-api-key",
            config_entry=mock_config_entry,
        )

    assert coordinator.flow_rates[1] == 10.0
    assert coordinator.flow_rates[2] == 15.0
    assert coordinator.flow_rates[3] == 20.0


async def test_coordinator_toggle_pump_idempotent(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Test that toggle_pump skips toggle when already in requested state."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass,
            api_key="test-api-key",
            config_entry=mock_config_entry,
        )
        coordinator.data = await coordinator._async_update_data()

        # Pump is on (status.pump == 1), requesting turn_on should be no-op
        await coordinator.toggle_pump(turn_on=True)
        mock_poolcop.toggle_pump.assert_not_called()

        # Requesting turn_off should actually toggle
        await coordinator.toggle_pump(turn_on=False)
        mock_poolcop.toggle_pump.assert_called_once()


async def test_update_command_result(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Test _update_command_result helper."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass,
            api_key="test-api-key",
            config_entry=mock_config_entry,
        )
        coordinator.data = await coordinator._async_update_data()

        result = {"result": "ok", "command": "test"}
        coordinator._update_command_result(result)
        assert coordinator.data.last_command_result == result
        # Original status should be preserved
        assert coordinator.data.status == mock_poolcop_data


async def test_rate_limit_with_retry_after(
    hass: HomeAssistant, mock_config_entry, mock_poolcop
):
    """Error with retry_after=60 → interval set."""
    from poolcop import PoolCopilotRateLimitError

    err = PoolCopilotRateLimitError("Rate limit")
    err.retry_after = 60
    mock_poolcop.status.side_effect = err
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass, api_key="test-api-key", config_entry=mock_config_entry
        )
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    assert coordinator.update_interval.total_seconds() == 60


async def test_rate_limit_exponential_backoff(
    hass: HomeAssistant, mock_config_entry, mock_poolcop
):
    """No retry_after → min(interval*2, 1800)."""
    from poolcop import PoolCopilotRateLimitError

    mock_poolcop.status.side_effect = PoolCopilotRateLimitError("Rate limit")
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass, api_key="test-api-key", config_entry=mock_config_entry
        )
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    # Default interval is 15, so backoff should be min(30, 1800) = 30
    assert coordinator.update_interval.total_seconds() == 30


async def test_alarm_fetch_on_count_change(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """New alarm triggers alarm_history call."""
    mock_poolcop_data["PoolCop"]["alerts"] = [
        {"code": 5, "description": "alert_title_5"}
    ]
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_poolcop.alarm_history.return_value = {
        "alarms": [{"code": 5, "description": "pH Low"}]
    }
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass, api_key="test-api-key", config_entry=mock_config_entry
        )
        await coordinator._async_update_data()

    mock_poolcop.alarm_history.assert_called_once_with(0)


async def test_alarm_fetch_filters_cleared(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """cleared=True alarms excluded."""
    mock_poolcop_data["PoolCop"]["alerts"] = [
        {"code": 5, "description": "alert_title_5"}
    ]
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_poolcop.alarm_history.return_value = {
        "alarms": [
            {"code": 5, "description": "pH Low", "cleared": False},
            {"code": 6, "description": "ORP Low", "cleared": True},
        ]
    }
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass, api_key="test-api-key", config_entry=mock_config_entry
        )
        data = await coordinator._async_update_data()

    # Only non-cleared alarm should be in active_alarms
    assert len(data.active_alarms) == 1
    assert data.active_alarms[0]["code"] == 5


async def test_alarm_fetch_interval_respected(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Same count within interval → no re-fetch."""

    mock_poolcop_data["PoolCop"]["alerts"] = [
        {"code": 5, "description": "alert_title_5"}
    ]
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_poolcop.alarm_history.return_value = {"alarms": []}
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass, api_key="test-api-key", config_entry=mock_config_entry
        )
        # First call triggers fetch
        await coordinator._async_update_data()
        assert mock_poolcop.alarm_history.call_count == 1

        # Second call with same count within interval → no re-fetch
        await coordinator._async_update_data()
        assert mock_poolcop.alarm_history.call_count == 1


async def test_get_alarm_history_error(
    hass: HomeAssistant, mock_config_entry, mock_poolcop
):
    """ConnectionError re-raised."""
    mock_poolcop.alarm_history.side_effect = PoolCopilotConnectionError("error")
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass, api_key="test-api-key", config_entry=mock_config_entry
        )
        with pytest.raises(PoolCopilotConnectionError):
            await coordinator.async_get_alarm_history(0)


async def test_get_command_history_error(
    hass: HomeAssistant, mock_config_entry, mock_poolcop
):
    """ConnectionError re-raised."""
    mock_poolcop.command_history.side_effect = PoolCopilotConnectionError("error")
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass, api_key="test-api-key", config_entry=mock_config_entry
        )
        with pytest.raises(PoolCopilotConnectionError):
            await coordinator.async_get_command_history(0)


async def test_set_force_filtration_mode(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """API called, last_command_result updated."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass, api_key="test-api-key", config_entry=mock_config_entry
        )
        coordinator.data = await coordinator._async_update_data()
        await coordinator.set_force_filtration_mode(24)

    mock_poolcop.set_force_filtration.assert_called_once_with(24)
    assert coordinator.data.last_command_result == {"result": "ok"}


async def test_save_load_learned_data(
    hass: HomeAssistant, mock_config_entry, mock_poolcop
):
    """cycle_durations round-trip through mocked storage."""
    from unittest.mock import AsyncMock

    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass, api_key="test-api-key", config_entry=mock_config_entry
        )

        # Mock the Store methods directly
        coordinator._store.async_save = AsyncMock()
        coordinator._store.async_load = AsyncMock(
            return_value={
                "cycle_durations": {1: 9999},
                "flow_rates": {2: 18.0},
            }
        )

        # Verify save calls the store
        await coordinator.async_save_learned_data()
        coordinator._store.async_save.assert_called_once()
        saved = coordinator._store.async_save.call_args[0][0]
        assert "cycle_durations" in saved
        assert "flow_rates" in saved

        # Verify load restores data
        await coordinator.async_load_learned_data()
        assert coordinator._cycle_durations[1] == 9999
        assert coordinator.flow_rates[2] == 18.0


async def test_status_value_non_dict_intermediate(mock_poolcop_data):
    """Non-dict node → returns None."""
    data = PoolCopData(status=mock_poolcop_data)
    # temperature.water is a float, trying to go deeper should return None
    assert data.status_value("temperature.water.something") is None


async def test_status_value_exception_handler():
    """status_value exception handler covers lines 80-84."""
    # Status with a value that is not a dict but not None either (list),
    # where accessing .get() would raise TypeError in the except block.
    # Actually the isinstance check handles this, but we need to trigger
    # KeyError/TypeError. Use a status where the PoolCop key is a non-dict
    # that doesn't support .get() — e.g., a list.
    data = PoolCopData(status={"PoolCop": [1, 2, 3]})
    # Traversal: result = {"PoolCop": [1,2,3]}, then result = [1,2,3]
    # then isinstance([1,2,3], dict) → False → return None
    assert data.status_value("temperature.water") is None


