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
