"""Diagnostics support for PoolCop."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import PoolCopDataUpdateCoordinator

TO_REDACT = {CONF_API_KEY}
COORDINATOR_FIELDS_TO_REDACT = {
    "token",
    "apikey",
    "poolcop_api_id",
    "poolcop_id",
    "ip",
    "remote",
    "href",
    "id",
    "latitude",
    "longitude",
    "nickname",
    "image",
    "mac_address",
    "dns",
    "email",
    "uuid",
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
            "update_interval_seconds": coordinator.update_interval.total_seconds(),
        },
    }

    if coordinator.data:
        data_copy = coordinator.data._asdict()

        if data_copy.get("status"):
            status_copy = dict(data_copy["status"])

            if "api_token" in status_copy:
                status_copy["api_token"] = async_redact_data(
                    dict(status_copy["api_token"]), COORDINATOR_FIELDS_TO_REDACT
                )

            if "PoolCop" in status_copy and "network" in status_copy["PoolCop"]:
                status_copy["PoolCop"]["network"] = async_redact_data(
                    dict(status_copy["PoolCop"]["network"]),
                    COORDINATOR_FIELDS_TO_REDACT,
                )

            if "PoolCop" in status_copy and "links" in status_copy["PoolCop"]:
                links = status_copy["PoolCop"]["links"]
                for link_key in links:
                    if isinstance(links[link_key], dict) and "href" in links[link_key]:
                        links[link_key] = async_redact_data(
                            dict(links[link_key]), COORDINATOR_FIELDS_TO_REDACT
                        )

            if "Pool" in status_copy:
                status_copy["Pool"] = "**REDACTED**"

            data_copy["status"] = status_copy

        diagnostics_data["data"] = data_copy

    return diagnostics_data
