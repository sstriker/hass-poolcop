"""Test PoolCop setup process."""
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.poolcop.const import DOMAIN


async def test_async_setup_entry(hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data):
    """Test setting up the PoolCop component."""
    mock_poolcop.status.return_value = mock_poolcop_data

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry.data,
        entry_id=mock_config_entry.entry_id,
        unique_id=mock_config_entry.unique_id,
    )
    mock_entry.add_to_hass(hass)

    # Setup the config entry
    with patch("custom_components.poolcop.coordinator.PoolCopilot"):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Verify services were registered
    assert hass.services.has_service(DOMAIN, "set_pump_speed")
    assert hass.services.has_service(DOMAIN, "toggle_pump")

    # Test unloading the entry
    with patch("custom_components.poolcop.coordinator.PoolCopilot"):
        assert await hass.config_entries.async_unload(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Verify component is unloaded
    assert mock_entry.entry_id not in hass.data[DOMAIN]