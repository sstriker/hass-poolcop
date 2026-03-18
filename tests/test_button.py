"""Test PoolCop button platform."""

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


async def test_clear_alarm_button_setup(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Button entity exists."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("button.poolcop_test_poolcop_id_clear_alarm")
    assert state is not None


async def test_clear_alarm_button_press(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Calls clear_alarm() + async_refresh()."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.poolcop_test_poolcop_id_clear_alarm"},
        blocking=True,
    )
    mock_poolcop.clear_alarm.assert_called()
