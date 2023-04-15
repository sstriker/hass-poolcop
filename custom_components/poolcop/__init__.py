"""The poolcop integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, LOGGER
from .coordinator import PoolCopDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PoolCop as config entry."""
    api_key: str = entry.data[CONF_API_KEY]
    # name: str = entry.data[CONF_NAME]
    assert entry.unique_id is not None
    poolcop_id: str = entry.unique_id
    # forecast: bool = entry.options.get(CONF_FORECAST, False)

    LOGGER.debug("PoolCop ID: %s", poolcop_id)

    coordinator = PoolCopDataUpdateCoordinator(
        hass,
        api_key,
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await coordinator.poolcopilot.close()
        raise

    # entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
