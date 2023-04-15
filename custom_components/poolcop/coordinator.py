"""The Coordinator for PoolCop."""
from __future__ import annotations

from functools import reduce
import operator
from typing import Any, NamedTuple

from poolcop import PoolCopilot, PoolCopilotConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL


class PoolCopData(NamedTuple):
    """Class for defining data in dict."""

    status: dict[str, Any] | None
    # alarms: dict[str, Any] | None
    # commands: dict[str, Any] | None

    def status_value(self, path: str, prefix="PoolCop") -> Any:
        """Get value from a path (e.g. 'temperature.water') from the Poolcop status."""
        try:
            return reduce(operator.getitem, [prefix] + path.split("."), self.status)  # type: ignore[arg-type]
        except KeyError:
            return None


class PoolCopDataUpdateCoordinator(DataUpdateCoordinator[PoolCopData]):
    """Class to manage fetching PoolCop data from single endpoint."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
    ) -> None:
        """Initialize global PoolCop data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.poolcopilot = PoolCopilot(
            session=async_get_clientsession(hass),
            api_key=api_key,
        )

    async def _async_update_data(self) -> PoolCopData:
        """Fetch data from PoolCop."""

        try:
            status = await self.poolcopilot.status()

        except PoolCopilotConnectionError as err:
            raise UpdateFailed("Error communicating with PoolCopilot API") from err

        return PoolCopData(
            status=status,
        )
