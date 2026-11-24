"""Helpers shared by the PoolCop integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiopoolcop import PoolCopClientAPI
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, REQUEST_TIMEOUT

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

# One client per API key: the Client API allows one request per second per
# key, and the client spaces the requests made through it.
DATA_CLIENTS: HassKey[dict[str, PoolCopClientAPI]] = HassKey(f"{DOMAIN}_clients")


@callback
def async_get_client(hass: HomeAssistant, api_key: str) -> PoolCopClientAPI:
    """Return the shared client for an API key."""
    clients = hass.data.setdefault(DATA_CLIENTS, {})
    if (client := clients.get(api_key)) is None:
        client = clients[api_key] = PoolCopClientAPI(
            api_key=api_key,
            session=async_get_clientsession(hass),
            request_timeout=REQUEST_TIMEOUT,
        )
    return client


@callback
def async_release_client(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Forget the client of an unloaded entry unless another entry uses it."""
    api_key = entry.data[CONF_API_KEY]
    for other in hass.config_entries.async_entries(DOMAIN):
        if (
            other.entry_id != entry.entry_id
            and other.state is ConfigEntryState.LOADED
            and other.data.get(CONF_API_KEY) == api_key
        ):
            return
    hass.data.get(DATA_CLIENTS, {}).pop(api_key, None)
