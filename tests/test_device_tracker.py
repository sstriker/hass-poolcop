"""Test PoolCop device tracker platform."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import DOMAIN


async def _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data):
    """Set up the integration and return the coordinator."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return hass.data[DOMAIN][mock_config_entry.entry_id]


async def test_tracker_with_coords(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """lat/lon → tracker entity."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("device_tracker.test_pool_pool")
    assert state is not None
    assert state.attributes.get("latitude") == 48.86
    assert state.attributes.get("longitude") == 2.35


async def test_tracker_no_coords(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """No coords → no entity."""
    del mock_poolcop_data["Pool"]
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("device_tracker.test_pool_pool")
    assert state is None


async def test_tracker_properties(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """source_type, icon, extra attrs."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("device_tracker.test_pool_pool")
    assert state is not None
    assert state.attributes.get("source_type") == "gps"
    assert state.attributes.get("icon") == "mdi:pool"
    assert state.attributes.get("timezone") == "Europe/Amsterdam"
    assert state.attributes.get("nickname") == "Test Pool"
