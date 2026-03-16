"""Test PoolCop diagnostics."""

from __future__ import annotations

from unittest.mock import patch


from homeassistant.core import HomeAssistant

from custom_components.poolcop.diagnostics import async_get_config_entry_diagnostics


async def _setup_integration(
    hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
):
    """Set up the integration for diagnostics tests."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.poolcop.PoolCopCloudAPI",
        return_value=mock_cloud_api,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_diagnostics(
    hass: HomeAssistant,
    mock_config_entry,
    mock_cloud_api,
    mock_oauth2_session,
    mock_storage,
):
    """Test diagnostics returns expected data."""
    await _setup_integration(
        hass, mock_config_entry, mock_cloud_api, mock_oauth2_session
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert "config_entry" in diagnostics
    assert "coordinator" in diagnostics
    assert "data" in diagnostics

    # Verify sensitive data is redacted
    config_data = diagnostics["config_entry"]["data"]
    assert (
        config_data.get("token") == "**REDACTED**"
        or "access_token" not in str(config_data).lower()
    )

    # Verify data structure
    assert "device" in diagnostics["data"]
    assert "state" in diagnostics["data"]
    assert "alarms" in diagnostics["data"]
    assert "auxiliaries" in diagnostics["data"]
