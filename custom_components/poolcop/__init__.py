"""The PoolCop integration."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
    DOMAIN,
    ISSUE_NEW_API_KEY,
    LOGGER,
    REMOVED_ENTITY_KEYS,
    RENAMED_ENTITY_KEYS,
)
from .coordinator import PoolCopConfigEntry, PoolCopDataUpdateCoordinator
from .helpers import async_get_client, async_release_client
from .service import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.GEO_LOCATION,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the PoolCop actions."""
    async_setup_services(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: PoolCopConfigEntry) -> bool:
    """Migrate config entry from older versions."""
    if entry.version == 1:
        LOGGER.debug("Migrating config entry from version 1 to 2")
        # Move flow_rates from data to options
        new_data = dict(entry.data)
        new_options = dict(entry.options)

        for key in (CONF_FLOW_RATE_1, CONF_FLOW_RATE_2, CONF_FLOW_RATE_3):
            if key in new_data:
                new_options.setdefault(key, new_data.pop(key))

        hass.config_entries.async_update_entry(
            entry, data=new_data, options=new_options, version=2
        )

    if entry.version == 2:
        # 2.x used the PoolCopilot API. The PoolCop device ID is the same in
        # the Client API, so entities keep their IDs, but the stored API key
        # does not work any more and some entities no longer exist.
        LOGGER.debug("Migrating config entry from version 2 to 3")
        _async_migrate_entities_v3(hass, entry)
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{ISSUE_NEW_API_KEY}_{entry.entry_id}",
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_NEW_API_KEY,
            translation_placeholders={"title": entry.title},
            learn_more_url="https://github.com/sstriker/hass-poolcop#getting-an-api-key",
        )
        hass.config_entries.async_update_entry(entry, version=3)

    LOGGER.debug("Migration to version %s complete", entry.version)
    return True


@callback
def _async_migrate_entities_v3(hass: HomeAssistant, entry: PoolCopConfigEntry) -> None:
    """Rename and remove entities that changed between 2.x and 3.0."""
    registry = er.async_get(hass)
    prefix = f"{DOMAIN}_{entry.unique_id}_"
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if not reg_entry.unique_id.startswith(prefix):
            continue
        key = reg_entry.unique_id.removeprefix(prefix)
        if (reg_entry.domain, key) in REMOVED_ENTITY_KEYS:
            LOGGER.debug("Removing entity %s (no longer provided)", reg_entry.entity_id)
            registry.async_remove(reg_entry.entity_id)
        elif (new_key := RENAMED_ENTITY_KEYS.get((reg_entry.domain, key))) is not None:
            new_unique_id = f"{prefix}{new_key}"
            if registry.async_get_entity_id(reg_entry.domain, DOMAIN, new_unique_id):
                registry.async_remove(reg_entry.entity_id)
            else:
                registry.async_update_entity(
                    reg_entry.entity_id, new_unique_id=new_unique_id
                )


async def async_setup_entry(hass: HomeAssistant, entry: PoolCopConfigEntry) -> bool:
    """Set up PoolCop as config entry."""
    if entry.unique_id is None:
        return False

    device_id = int(entry.unique_id)
    LOGGER.debug("PoolCop device ID: %d", device_id)

    api = async_get_client(hass, entry.data[CONF_API_KEY])
    coordinator = PoolCopDataUpdateCoordinator(hass, api, device_id, entry)
    await coordinator.async_config_entry_first_refresh()

    # The key works, so the 2.x migration notice is no longer relevant.
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_NEW_API_KEY}_{entry.entry_id}")

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload when options (flow rates, map mode) change
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: PoolCopConfigEntry
) -> None:
    """Handle options updates."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PoolCopConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_save_learned_data()
        async_release_client(hass, entry)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: PoolCopConfigEntry) -> None:
    """Clean up when a config entry is removed."""
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_NEW_API_KEY}_{entry.entry_id}")
