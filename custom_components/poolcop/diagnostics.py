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
# Add fields that should be redacted from the coordinator data
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
    "poolcop",
    "image",
    "mac_address",
    "dns"
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Prepare the diagnostic data
    diagnostics_data = {
        "config_entry_data": async_redact_data(dict(config_entry.data), TO_REDACT),
        "coordinator_data": [],
    }

    # Create a redacted copy of the coordinator data
    if coordinator.data:
        # Make a copy of the data dictionary
        data_copy = coordinator.data._asdict()
        
        # Handle special case for status data, which is a dictionary
        if data_copy.get("status"):
            status_copy = dict(data_copy["status"])
            
            # Redact sensitive information in api_token if present
            if "api_token" in status_copy:
                status_copy["api_token"] = async_redact_data(
                    dict(status_copy["api_token"]), 
                    COORDINATOR_FIELDS_TO_REDACT
                )
            
            # Redact network information containing IP addresses
            if "PoolCop" in status_copy and "network" in status_copy["PoolCop"]:
                status_copy["PoolCop"]["network"] = async_redact_data(
                    dict(status_copy["PoolCop"]["network"]),
                    COORDINATOR_FIELDS_TO_REDACT
                )
                
            # Redact URLs in links
            if "PoolCop" in status_copy and "links" in status_copy["PoolCop"]:
                # Redact each link href
                links = status_copy["PoolCop"]["links"]
                for link_key in links:
                    if "href" in links[link_key]:
                        links[link_key] = async_redact_data(
                            dict(links[link_key]),
                            COORDINATOR_FIELDS_TO_REDACT
                        )
            
            # Completely redact Pool section as it contains personal information
            if "Pool" in status_copy:
                status_copy["Pool"] = "**REDACTED**"
                
            data_copy["status"] = status_copy
            
        # Remove the coordinator reference as it's not serializable
        if "_coordinator" in data_copy:
            del data_copy["_coordinator"]
            
        diagnostics_data["coordinator_data"] = [data_copy]

    # Add setup times if available
    if hasattr(config_entry, "runtime_data") and config_entry.runtime_data:
        diagnostics_data["setup_times"] = config_entry.runtime_data

    return diagnostics_data
