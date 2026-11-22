"""Test PoolCop button platform."""

from unittest.mock import patch

from aiopoolcop import Pool, PoolCopDevice
from homeassistant.core import HomeAssistant


async def _setup_integration(
    hass, mock_config_entry, mock_poolcop_api, device_data, pool_data
):
    """Set up the integration and return the coordinator."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(pool_data)]
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.helpers.PoolCopClientAPI",
        return_value=mock_poolcop_api,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry.runtime_data


async def test_clear_alarm_button_setup(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Clear alarm button entity exists."""
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [
        s for s in hass.states.async_all("button") if "clear_alarm" in s.entity_id
    ]
    assert len(states) >= 1


async def test_clear_alarm_button_press(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Pressing calls clear_all_alarms."""
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    button = next(
        s for s in hass.states.async_all("button") if "clear_alarm" in s.entity_id
    )
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": button.entity_id},
        blocking=True,
    )
    mock_poolcop_api.clear_all_alarms.assert_called_once_with(2478)
