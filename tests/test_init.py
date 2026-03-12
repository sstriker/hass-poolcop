"""Test PoolCop setup, unload, and migration."""

from unittest.mock import patch

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.poolcop.const import (
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
    DOMAIN,
)


async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Test setting up the PoolCop component."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "set_pump_speed")
    assert hass.services.has_service(DOMAIN, "toggle_pump")
    assert mock_config_entry.entry_id in hass.data[DOMAIN]


async def test_async_unload_entry(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Test unloading the PoolCop component."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.entry_id not in hass.data[DOMAIN]


async def test_async_setup_entry_no_unique_id(
    hass: HomeAssistant, mock_poolcop, mock_poolcop_data
):
    """Test setup fails gracefully when unique_id is None."""
    mock_poolcop.status.return_value = mock_poolcop_data
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-key"},
        unique_id=None,
        entry_id="no_uid",
        version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is False


async def test_migrate_v1_to_v2(
    hass: HomeAssistant, mock_v1_config_entry, mock_poolcop, mock_poolcop_data
):
    """Test config entry migration from v1 to v2 moves flow rates to options."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_v1_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_v1_config_entry.entry_id)
        await hass.async_block_till_done()

    # After migration, flow rates should be in options, not data
    assert mock_v1_config_entry.version == 2
    assert CONF_FLOW_RATE_1 not in mock_v1_config_entry.data
    assert CONF_FLOW_RATE_2 not in mock_v1_config_entry.data
    assert CONF_FLOW_RATE_3 not in mock_v1_config_entry.data
    assert mock_v1_config_entry.options[CONF_FLOW_RATE_1] == 10.0
    assert mock_v1_config_entry.options[CONF_FLOW_RATE_2] == 15.0
    assert mock_v1_config_entry.options[CONF_FLOW_RATE_3] == 20.0
