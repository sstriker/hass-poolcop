"""Test PoolCop device tracker entities."""

from __future__ import annotations

from unittest.mock import patch


from homeassistant.core import HomeAssistant


from .conftest import make_pool


async def _setup_integration(
    hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
):
    """Set up the integration for device tracker tests."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.poolcop.PoolCopCloudAPI",
        return_value=mock_cloud_api,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_device_tracker_created(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test that device tracker entity is created when pool has location."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    trackers = [
        s for s in hass.states.async_all("device_tracker") if "poolcop" in s.entity_id
    ]
    assert len(trackers) >= 1


async def test_device_tracker_not_created_without_location(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test that device tracker is not created when pool has no location."""

    mock_cloud_api.get_pool.return_value = make_pool(latitude=None, longitude=None)
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    trackers = [
        s for s in hass.states.async_all("device_tracker") if "poolcop" in s.entity_id
    ]
    assert len(trackers) == 0
