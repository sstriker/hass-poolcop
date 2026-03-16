"""Test PoolCop setup process."""

from __future__ import annotations

from unittest.mock import patch


from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import DOMAIN


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test setting up the PoolCop component."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.PoolCopCloudAPI",
        return_value=mock_cloud_api,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify coordinator is stored
    assert mock_config_entry.entry_id in hass.data[DOMAIN]

    # Verify services were registered
    assert hass.services.has_service(DOMAIN, "set_pump_speed")
    assert hass.services.has_service(DOMAIN, "set_pump")
    assert hass.services.has_service(DOMAIN, "set_aux")


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.PoolCopCloudAPI",
        return_value=mock_cloud_api,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify cleanup
    assert mock_config_entry.entry_id not in hass.data.get(DOMAIN, {})
    mock_cloud_api.close.assert_called_once()
