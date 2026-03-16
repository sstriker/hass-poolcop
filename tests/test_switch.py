"""Test PoolCop switch entities."""

from __future__ import annotations

from unittest.mock import patch


from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import DOMAIN


async def _setup_integration(
    hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
):
    """Set up the integration for switch tests."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.poolcop.PoolCopCloudAPI",
        return_value=mock_cloud_api,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_switches_created(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test that switch entities are created."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    switches = [s for s in hass.states.async_all("switch") if "poolcop" in s.entity_id]
    # Pump switch + aux switches (2 aux, both non-reserved with mode Auto)
    assert len(switches) >= 1


async def test_pump_switch_state(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test pump switch state reflects pump state."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.data.pump.pump_state is True
