"""Test PoolCop coordinator functionality."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.poolcop.coordinator import PoolCopData, PoolCopDataUpdateCoordinator
from custom_components.poolcop.const import DOMAIN


async def test_coordinator_update(hass, mock_poolcop, mock_poolcop_data):
    """Test the coordinator update method."""
    mock_poolcop.status.return_value = mock_poolcop_data
    
    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot", return_value=mock_poolcop
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass,
            api_key="test-api-key",
        )
        
        # Test successful update
        data = await coordinator._async_update_data()
        assert isinstance(data, PoolCopData)
        assert data.status == mock_poolcop_data
        mock_poolcop.status.assert_called_once()
        
        # Test data access methods
        assert data.status_value("temperature.water") == 26.5
        assert data.status_value("status.pump") == 1
        assert data.status_value("nonexistent.path") is None


async def test_coordinator_update_error(hass, mock_poolcop):
    """Test error handling in coordinator update."""
    from poolcop import PoolCopilotConnectionError
    
    mock_poolcop.status.side_effect = PoolCopilotConnectionError("Connection error")
    
    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot", return_value=mock_poolcop
    ):
        coordinator = PoolCopDataUpdateCoordinator(
            hass=hass,
            api_key="test-api-key",
        )
        
        # Test failed update
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()