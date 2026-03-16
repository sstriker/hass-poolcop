"""Test PoolCop button entities."""

from __future__ import annotations

from unittest.mock import patch


from homeassistant.core import HomeAssistant


async def _setup_integration(
    hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
):
    """Set up the integration for button tests."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.poolcop.PoolCopCloudAPI",
        return_value=mock_cloud_api,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_buttons_created(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test that button entities are created."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    buttons = [s for s in hass.states.async_all("button") if "poolcop" in s.entity_id]
    # Clear alarm button
    assert len(buttons) >= 1
