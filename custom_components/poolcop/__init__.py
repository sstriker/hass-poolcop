"""The poolcop integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
    DOMAIN,
    LOGGER,
)
from .coordinator import PoolCopDataUpdateCoordinator
from .service import async_setup_services, async_unload_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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
        LOGGER.debug("Migration to version 2 complete")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PoolCop as config entry."""
    api_key: str = entry.data[CONF_API_KEY]
    if entry.unique_id is None:
        return False
    poolcop_id: str = entry.unique_id

    LOGGER.debug("PoolCop ID: %s", poolcop_id)

    coordinator = PoolCopDataUpdateCoordinator(
        hass,
        api_key,
        entry,
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await coordinator.poolcopilot.close()
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options updates to reload flow rates
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await async_setup_services(hass)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options updates."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

        if not hass.data[DOMAIN]:
            await async_unload_services(hass)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
