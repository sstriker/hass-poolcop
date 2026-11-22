"""Test PoolCop setup, unload, and migration."""

from unittest.mock import patch

from aiopoolcop import Pool, PoolCopClientAuthError, PoolCopDevice
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.poolcop.const import (
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
    DOMAIN,
)
from custom_components.poolcop.helpers import DATA_CLIENTS

CLIENT = "custom_components.poolcop.helpers.PoolCopClientAPI"


async def _setup(hass, entry, api, device_data, pool_data):
    """Set up integration with mocked API."""
    api.get_device.return_value = PoolCopDevice.from_dict(device_data)
    api.get_pools.return_value = [Pool.from_dict(pool_data)]
    entry.add_to_hass(hass)

    with patch(CLIENT, return_value=api):
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
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.device_id == 2478
    for service in (
        "set_pump_speed",
        "toggle_pump",
        "toggle_aux",
        "set_valve_position",
        "clear_alarm",
        "stop_backwash",
        "set_filtration_mode",
        "set_filtration_timers",
    ):
        assert hass.services.has_service(DOMAIN, service)


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Unloading saves learned data and forgets the client."""
    await _setup(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )
    assert hass.data[DATA_CLIENTS]

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.data[DATA_CLIENTS] == {}
    # Actions stay registered (they report that no PoolCop is loaded)
    assert hass.services.has_service(DOMAIN, "toggle_pump")


async def test_entries_share_client_per_key(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Two PoolCops on one key share one client; it is kept while one is loaded."""
    second = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: mock_config_entry.data[CONF_API_KEY], "pump_speeds": 3},
        unique_id="3001",
        entry_id="second",
        version=3,
    )
    await _setup(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )
    second.add_to_hass(hass)
    with patch(CLIENT) as client_cls:
        assert await hass.config_entries.async_setup(second.entry_id)
        await hass.async_block_till_done()
    client_cls.assert_not_called()
    assert second.runtime_data.api is mock_config_entry.runtime_data.api

    assert await hass.config_entries.async_unload(second.entry_id)
    assert len(hass.data[DATA_CLIENTS]) == 1


async def test_async_setup_entry_no_unique_id(
    hass: HomeAssistant,
    mock_poolcop_api,
):
    """Test setup fails gracefully when unique_id is None."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-key"},
        unique_id=None,
        entry_id="no_uid",
        version=3,
    )
    entry.add_to_hass(hass)

    with patch(CLIENT, return_value=mock_poolcop_api):
        result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is False


async def test_setup_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """A rejected key starts the reauth flow."""
    mock_poolcop_api.get_device.side_effect = PoolCopClientAuthError("403")
    mock_config_entry.add_to_hass(hass)
    with patch(CLIENT, return_value=mock_poolcop_api):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_migrate_v1_to_v3(
    hass: HomeAssistant,
    mock_v1_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Version 1 entries move flow rates to options and end at version 3."""
    await _setup(
        hass, mock_v1_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    assert mock_v1_config_entry.version == 3
    for key in (CONF_FLOW_RATE_1, CONF_FLOW_RATE_2, CONF_FLOW_RATE_3):
        assert key not in mock_v1_config_entry.data
    assert mock_v1_config_entry.options[CONF_FLOW_RATE_1] == 10.0
    assert mock_v1_config_entry.options[CONF_FLOW_RATE_2] == 15.0
    assert mock_v1_config_entry.options[CONF_FLOW_RATE_3] == 20.0


async def test_migrate_v2_to_v3(
    hass: HomeAssistant,
    mock_v2_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """2.x entries keep their entities, lose removed ones and get a repair issue."""
    entry = mock_v2_config_entry
    entry.add_to_hass(hass)
    registry = er.async_get(hass)

    def add(domain: str, key: str, unique_prefix: str = "poolcop_2478_") -> str:
        return registry.async_get_or_create(
            domain,
            DOMAIN,
            f"{unique_prefix}{key}",
            config_entry=entry,
            suggested_object_id=f"striker_{key}",
        ).entity_id

    kept = add("sensor", "temperature_water")
    removed = add("sensor", "ioniser")
    removed_binary = add("binary_sensor", "watervalve")
    renamed = add("sensor", "poolcop")
    other_prefix = add("sensor", "ioniser", unique_prefix="something_else_")

    # The old key no longer works: setup fails and asks for a new key
    mock_poolcop_api.get_device.side_effect = PoolCopClientAuthError("403")
    with patch(CLIENT, return_value=mock_poolcop_api):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.version == 3
    assert registry.async_get(kept) is not None
    assert registry.async_get(removed) is None
    assert registry.async_get(removed_binary) is None
    assert registry.async_get(other_prefix) is not None
    renamed_entry = registry.async_get(renamed)
    assert renamed_entry is not None
    assert renamed_entry.unique_id == "poolcop_2478_running_status"

    issue_id = f"new_api_key_{entry.entry_id}"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_placeholders == {"title": "Striker"}
    assert entry.state is ConfigEntryState.SETUP_ERROR

    # With a working key the issue goes away
    mock_poolcop_api.get_device.side_effect = None
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(mock_device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(mock_pool_data)]
    with patch(CLIENT, return_value=mock_poolcop_api):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_migrate_v2_rename_conflict(
    hass: HomeAssistant, mock_v2_config_entry, mock_poolcop_api
):
    """An old entity whose new unique ID already exists is removed."""
    entry = mock_v2_config_entry
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "sensor", DOMAIN, "poolcop_2478_poolcop", config_entry=entry
    ).entity_id
    new = registry.async_get_or_create(
        "sensor", DOMAIN, "poolcop_2478_running_status", config_entry=entry
    ).entity_id
    mock_poolcop_api.get_device.side_effect = PoolCopClientAuthError("403")
    with patch(CLIENT, return_value=mock_poolcop_api):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert registry.async_get(old) is None
    assert registry.async_get(new) is not None


async def test_migrate_from_future_version_fails(hass: HomeAssistant):
    """Entries from a newer version are not loaded."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "k"}, unique_id="2478", version=4
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_remove_entry_deletes_issue(
    hass: HomeAssistant, mock_v2_config_entry, mock_poolcop_api
):
    """Removing a migrated entry removes its repair issue."""
    entry = mock_v2_config_entry
    entry.add_to_hass(hass)
    mock_poolcop_api.get_device.side_effect = PoolCopClientAuthError("403")
    with patch(CLIENT, return_value=mock_poolcop_api):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    issue_id = f"new_api_key_{entry.entry_id}"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id)

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_options_update_reloads(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Changing options reloads the entry."""
    await _setup(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )
    with patch(
        "custom_components.poolcop.async_setup_entry", return_value=True
    ) as mock_setup:
        hass.config_entries.async_update_entry(
            mock_config_entry, options={CONF_FLOW_RATE_1: 5.0}
        )
        await hass.async_block_till_done()
    assert mock_setup.called
