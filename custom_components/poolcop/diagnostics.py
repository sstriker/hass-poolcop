"""Diagnostics support for PoolCop."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import PoolCopDataUpdateCoordinator

TO_REDACT = {CONF_API_KEY}
FIELDS_TO_REDACT = {
    "latitude",
    "longitude",
    "nickname",
    "uuid",
    "mac",
    "address1",
    "address2",
    "zip_code",
    "city",
    "country",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    diagnostics_data: dict[str, Any] = {
        "config_entry": {
            "data": async_redact_data(dict(config_entry.data), TO_REDACT),
            "options": dict(config_entry.options),
            "unique_id": config_entry.unique_id,
            "version": config_entry.version,
        },
        "coordinator": {
            "flow_rates": coordinator.flow_rates,
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
        },
    }

    if coordinator.data:
        device_dict = asdict(coordinator.data.device)
        device_dict = async_redact_data(device_dict, FIELDS_TO_REDACT)

        pool_dict = None
        if coordinator.data.pool:
            pool_dict = asdict(coordinator.data.pool)
            pool_dict = async_redact_data(pool_dict, FIELDS_TO_REDACT)

        diagnostics_data["data"] = {
            "device": device_dict,
            "pool": pool_dict,
            "cycle_status": coordinator.data.cycle_status,
        }

    return diagnostics_data
