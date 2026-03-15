"""Test PoolCop coordinator functionality."""

import time
from datetime import datetime
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


async def test_rate_limit_raises_update_failed(
    hass: HomeAssistant, mock_config_entry, mock_poolcop
):
    """Rate limit raises UpdateFailed immediately."""
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


async def test_rate_limit_schedules_retry_at_token_expire(
    hass: HomeAssistant, mock_config_entry, mock_poolcop
):
    """Rate limit sets update_interval to time remaining in token window."""
    from poolcop import PoolCopilotRateLimitError

    mock_poolcop.status.side_effect = PoolCopilotRateLimitError("Rate limit")
    mock_poolcop.token_expire = time.time() + 300  # 5 minutes from now
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

    # Should schedule retry close to token expiry (~300s, allow 2s tolerance)
    assert 298 <= coordinator.update_interval.total_seconds() <= 302


async def test_rate_limit_expired_token_uses_min_interval(
    hass: HomeAssistant, mock_config_entry, mock_poolcop
):
    """Rate limit with expired token window uses MIN_UPDATE_INTERVAL."""
    from poolcop import PoolCopilotRateLimitError

    mock_poolcop.status.side_effect = PoolCopilotRateLimitError("Rate limit")
    mock_poolcop.token_expire = time.time() - 100  # already expired
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

    assert coordinator.update_interval.total_seconds() == 10  # MIN_UPDATE_INTERVAL


async def test_active_alarms_from_status(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Active alarms come from status alerts array."""
    mock_poolcop_data["PoolCop"]["alerts"] = [
        {"code": 5, "description": "alert_title_5"}
    ]
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass, api_key="test-api-key", config_entry=mock_config_entry
        )
        data = await coordinator._async_update_data()

    assert len(data.active_alarms) == 1
    assert data.active_alarms[0]["code"] == 5


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

        # Verify save includes daily_volume fields
        coordinator._daily_volume = 1.234
        coordinator._daily_volume_date = "2026-03-15"
        await coordinator.async_save_learned_data()
        coordinator._store.async_save.assert_called_once()
        saved = coordinator._store.async_save.call_args[0][0]
        assert "cycle_durations" in saved
        assert "flow_rates" in saved
        assert saved["daily_volume"] == 1.234
        assert saved["daily_volume_date"] == "2026-03-15"

        # JSON serializes int keys as strings; simulate that
        today = datetime.now().strftime("%Y-%m-%d")
        coordinator._store.async_load = AsyncMock(
            return_value={
                "cycle_durations": {"1": 9999},
                "flow_rates": {"2": 18.0},
                "daily_volume": 2.567,
                "daily_volume_date": today,
            }
        )

        # Verify load converts string keys back to int and restores daily volume
        await coordinator.async_load_learned_data()
        assert coordinator._cycle_durations[1] == 9999
        assert coordinator.flow_rates[2] == 18.0
        assert coordinator._daily_volume == 2.567


async def test_load_stale_daily_volume_discarded(
    hass: HomeAssistant, mock_config_entry, mock_poolcop
):
    """Daily volume from a previous day is not restored."""
    from unittest.mock import AsyncMock

    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass, api_key="test-api-key", config_entry=mock_config_entry
        )
        coordinator._store.async_load = AsyncMock(
            return_value={
                "cycle_durations": {},
                "flow_rates": {},
                "daily_volume": 5.0,
                "daily_volume_date": "2020-01-01",
            }
        )
        await coordinator.async_load_learned_data()
        # Stale date → volume should NOT be restored
        assert coordinator._daily_volume == 0.0


async def test_status_value_non_dict_intermediate(mock_poolcop_data):
    """Non-dict node → returns None."""
    data = PoolCopData(status=mock_poolcop_data)
    # temperature.water is a float, trying to go deeper should return None
    assert data.status_value("temperature.water.something") is None


async def test_daily_volume_date_exception(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """datetime.now() exception sets today=None without crashing."""
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

        # Mock datetime.now to raise, triggering the except branch (lines 183-184)
        with patch(
            "custom_components.poolcop.coordinator.datetime"
        ) as mock_dt:
            mock_dt.now.side_effect = RuntimeError("broken clock")
            # Should not crash — today=None means no date reset
            coordinator._update_daily_volume()

    # Verify the method completed without error
    assert coordinator._last_flow_update is not None


async def test_status_value_non_dict_node():
    """Non-dict intermediate node (list) → isinstance guard returns None."""
    data = PoolCopData(status={"PoolCop": [1, 2, 3]})
    assert data.status_value("temperature.water") is None
