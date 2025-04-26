"""Test PoolCop service functionality."""
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.poolcop.const import DOMAIN, SERVICE_SET_PUMP_SPEED, SERVICE_TOGGLE_PUMP

async def test_service_toggle_pump(hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data):
    """Test the toggle_pump service."""
    mock_poolcop.status.return_value = mock_poolcop_data

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry.data,
        entry_id=mock_config_entry.entry_id,
        unique_id=mock_config_entry.unique_id,
    )
    mock_entry.add_to_hass(hass)

    # Setup the config entry
    with patch("custom_components.poolcop.coordinator.PoolCopilot", return_value=mock_poolcop):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Call the service
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TOGGLE_PUMP,
        {},
        blocking=True,
    )

    # Assert toggle_pump was called with no parameters
    mock_poolcop.toggle_pump.assert_called_once_with()