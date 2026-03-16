"""The poolcop integration."""

from __future__ import annotations

from aiopoolcop import PoolCopCloudAPI
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import CONF_POOLCOP_ID, DOMAIN
from .coordinator import PoolCopDataUpdateCoordinator
from .service import async_setup_services, async_unload_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PoolCop as config entry."""
    # Get OAuth2 implementation and session
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    # Ensure token is valid
    await session.async_ensure_token_valid()
    token = session.token["access_token"]

    poolcop_id = entry.data[CONF_POOLCOP_ID]

    async def _async_refresh_token() -> str:
        """Refresh the OAuth2 token and return the new access token."""
        await session.async_ensure_token_valid()
        return session.token["access_token"]

    api = PoolCopCloudAPI(
        token=token,
        token_refresh_callback=_async_refresh_token,
    )

    coordinator = PoolCopDataUpdateCoordinator(
        hass,
        api,
        poolcop_id,
        entry,
    )

    await coordinator.async_config_entry_first_refresh()

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
        coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN].pop(
            entry.entry_id
        )
        await coordinator.api.close()

        if not hass.data[DOMAIN]:
            await async_unload_services(hass)

    return unload_ok
