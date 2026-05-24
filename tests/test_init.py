"""Test PoolCop setup, unload, and migration."""

from unittest.mock import AsyncMock, patch

from aiopoolcop import Pool, PoolCopDevice
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.poolcop.const import (
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
    DOMAIN,
)


async def _setup(hass, entry, api, device_data, pool_data):
    """Set up integration with mocked API."""
    api.get_device.return_value = PoolCopDevice.from_dict(device_data)
    api.get_pools.return_value = [Pool.from_dict(pool_data)]
    entry.add_to_hass(hass)

    with patch("custom_components.poolcop.PoolCopClientAPI", return_value=api):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return result


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Test setting up the PoolCop component."""
    result = await _setup(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )
    assert result is True
    assert hass.services.has_service(DOMAIN, "set_pump_speed")
    assert hass.services.has_service(DOMAIN, "toggle_pump")
    assert mock_config_entry.entry_id in hass.data[DOMAIN]


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Test unloading the PoolCop component."""
    await _setup(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    with patch("custom_components.poolcop.PoolCopClientAPI", return_value=mock_poolcop_api):
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.entry_id not in hass.data[DOMAIN]
    mock_poolcop_api.close.assert_called_once()


async def test_async_setup_entry_no_unique_id(
    hass: HomeAssistant,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Test setup fails gracefully when unique_id is None."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-key"},
        unique_id=None,
        entry_id="no_uid",
        version=2,
    )
    entry.add_to_hass(hass)

    with patch("custom_components.poolcop.PoolCopClientAPI", return_value=mock_poolcop_api):
        result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is False


async def test_migrate_v1_to_v2(
    hass: HomeAssistant,
    mock_v1_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Test config entry migration from v1 to v2 moves flow rates to options."""
    await _setup(
        hass, mock_v1_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    assert mock_v1_config_entry.version == 2
    assert CONF_FLOW_RATE_1 not in mock_v1_config_entry.data
    assert CONF_FLOW_RATE_2 not in mock_v1_config_entry.data
    assert CONF_FLOW_RATE_3 not in mock_v1_config_entry.data
    assert mock_v1_config_entry.options[CONF_FLOW_RATE_1] == 10.0
    assert mock_v1_config_entry.options[CONF_FLOW_RATE_2] == 15.0
    assert mock_v1_config_entry.options[CONF_FLOW_RATE_3] == 20.0


async def test_async_reload_entry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Test reload entry calls unload then setup."""
    from custom_components.poolcop import async_reload_entry

    await _setup(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    with (
        patch(
            "custom_components.poolcop.async_unload_entry",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_unload,
        patch(
            "custom_components.poolcop.async_setup_entry",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_setup,
    ):
        await async_reload_entry(hass, mock_config_entry)

    mock_unload.assert_called_once_with(hass, mock_config_entry)
    mock_setup.assert_called_once_with(hass, mock_config_entry)
