"""Test PoolCop diagnostics."""

from unittest.mock import patch

from aiopoolcop import Pool, PoolCopDevice
from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import DOMAIN
from custom_components.poolcop.diagnostics import async_get_config_entry_diagnostics


async def _setup_coordinator(hass, mock_config_entry, mock_poolcop_api, device_data, pool_data):
    """Set up integration and return the coordinator."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(pool_data)]
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.poolcop.PoolCopClientAPI", return_value=mock_poolcop_api):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return hass.data[DOMAIN][mock_config_entry.entry_id]


async def test_diagnostics_basic(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Returns config_entry + coordinator + data keys."""
    await _setup_coordinator(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert "config_entry" in result
    assert "coordinator" in result
    assert "data" in result
    assert result["config_entry"]["version"] == 2


async def test_diagnostics_redacts_api_key(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """api_key is redacted."""
    await _setup_coordinator(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert result["config_entry"]["data"]["api_key"] == "**REDACTED**"


async def test_diagnostics_redacts_device_pii(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Device PII fields (uuid, mac, nickname) are redacted."""
    await _setup_coordinator(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    device = result["data"]["device"]
    assert device.get("uuid") == "**REDACTED**"
    assert device.get("mac") == "**REDACTED**"
    assert device.get("nickname") == "**REDACTED**"


async def test_diagnostics_redacts_pool_data(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Pool PII fields (lat, lon, nickname) are redacted."""
    await _setup_coordinator(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    pool = result["data"]["pool"]
    assert pool is not None
    assert pool.get("latitude") == "**REDACTED**"
    assert pool.get("longitude") == "**REDACTED**"
    assert pool.get("nickname") == "**REDACTED**"


async def test_diagnostics_no_data(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """coordinator.data=None does not crash."""
    await _setup_coordinator(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    coordinator.data = None

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert "config_entry" in result
    assert "data" not in result
