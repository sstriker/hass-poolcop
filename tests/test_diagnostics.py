"""Test PoolCop diagnostics."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import DOMAIN
from custom_components.poolcop.diagnostics import async_get_config_entry_diagnostics


async def _setup_coordinator(hass, mock_config_entry, mock_poolcop, mock_poolcop_data):
    """Set up integration and return the coordinator."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return hass.data[DOMAIN][mock_config_entry.entry_id]


async def test_diagnostics_basic(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Returns config_entry + coordinator + data keys."""
    await _setup_coordinator(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert "config_entry" in result
    assert "coordinator" in result
    assert "data" in result
    assert result["config_entry"]["version"] == 2


async def test_diagnostics_redacts_api_key(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """api_key → '**REDACTED**'."""
    await _setup_coordinator(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert result["config_entry"]["data"]["api_key"] == "**REDACTED**"


async def test_diagnostics_redacts_pool_data(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """lat, lon, nickname redacted in Pool section."""
    await _setup_coordinator(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    pool = result["data"]["status"].get("Pool", {})
    assert pool.get("latitude") == "**REDACTED**"
    assert pool.get("longitude") == "**REDACTED**"
    assert pool.get("nickname") == "**REDACTED**"


async def test_diagnostics_redacts_network(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """ip, mac_address, etc. redacted in network section."""
    # Add network fields to trigger redaction
    mock_poolcop_data["PoolCop"]["network"]["ip"] = "192.168.1.100"
    mock_poolcop_data["PoolCop"]["network"]["mac_address"] = "AA:BB:CC:DD:EE:FF"
    await _setup_coordinator(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    network = result["data"]["status"]["PoolCop"]["network"]
    assert network.get("ip") == "**REDACTED**"
    assert network.get("mac_address") == "**REDACTED**"


async def test_diagnostics_redacts_links(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """href fields redacted in links section."""
    mock_poolcop_data["PoolCop"]["links"] = {
        "self": {"href": "https://example.com/pool/42"},
    }
    await _setup_coordinator(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    links = result["data"]["status"]["PoolCop"]["links"]
    assert links["self"]["href"] == "**REDACTED**"


async def test_diagnostics_no_data(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """coordinator.data=None → no crash."""
    await _setup_coordinator(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    coordinator.data = None

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert "config_entry" in result
    assert "data" not in result
