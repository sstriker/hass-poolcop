"""Diagnostics support for PoolCop."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import PoolCopDataUpdateCoordinator

TO_REDACT = {"token", "access_token", "refresh_token"}
DATA_TO_REDACT = {
    "id",
    "pool_id",
    "user_id",
    "uuid",
    "mac",
    "latitude",
    "longitude",
    "nickname",
    "email",
    "firstname",
    "lastname",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

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
        data = coordinator.data
        device_info = {
            "id": "**REDACTED**",
            "nickname": "**REDACTED**",
            "is_connected": data.device.is_connected,
            "is_fully_connected": data.device.is_fully_connected,
        }

        state_info = {
            "status": data.state.status,
            "water_temperature": data.state.water_temperature,
            "air_temperature": data.state.air_temperature,
            "ph": data.state.ph,
            "orp": data.state.orp,
            "battery_voltage": data.state.battery_voltage,
            "mains_power_lost": data.state.mains_power_lost,
            "pumps_count": len(data.state.pumps),
            "water_level_installed": data.state.water_level.installed,
            "water_level_state": data.state.water_level.state,
        }

        if data.pump:
            state_info["pump"] = {
                "current_speed": data.pump.current_speed,
                "valve_position": data.pump.valve_position,
                "pump_state": data.pump.pump_state,
                "pressure": data.pump.pressure,
            }

        alarm_info = [
            {
                "code": a.code,
                "severity": a.severity,
                "label": a.label,
                "is_active": a.is_active,
            }
            for a in data.alarms
        ]

        aux_info = [
            {
                "module_id": a.module_id,
                "aux_channel": a.aux_channel,
                "mode": a.mode,
                "label": a.label,
                "is_reserved": a.is_reserved,
                "status": a.status,
            }
            for a in data.auxiliaries
        ]

        diagnostics_data["data"] = {
            "device": device_info,
            "state": state_info,
            "alarms": alarm_info,
            "auxiliaries": aux_info,
            "has_pool": data.pool is not None,
            "has_pump_config": data.pump_config is not None,
            "has_filter_config": data.filter_config is not None,
            "has_equipments": data.equipments is not None,
        }

    return diagnostics_data
