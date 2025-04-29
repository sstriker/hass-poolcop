"""Services for PoolCop."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import (
    DOMAIN,
    SERVICE_CLEAR_ALARM,
    SERVICE_SET_PUMP_SPEED,
    SERVICE_SET_VALVE_POSITION,
    SERVICE_TOGGLE_AUX,
    SERVICE_TOGGLE_PUMP,
    VALVE_POSITIONS,
)
from .coordinator import PoolCopDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SET_PUMP_SPEED_SCHEMA = vol.Schema(
    {
        vol.Required("speed"): vol.All(vol.Coerce(int), vol.Range(min=0, max=3)),
    }
)

TOGGLE_AUX_SCHEMA = vol.Schema(
    {
        vol.Required("aux_id"): vol.All(vol.Coerce(int), vol.Range(min=1, max=6)),
    }
)

SET_VALVE_POSITION_SCHEMA = vol.Schema(
    {
        vol.Required("position"): vol.In(
            ["filter", "waste", "closed", "backwash", "bypass", "rinse"]
        ),
    }
)


async def _async_get_targeted_coordinators(
    hass: HomeAssistant, service_call: ServiceCall
) -> list[PoolCopDataUpdateCoordinator]:
    """Get coordinators targeted by the service call."""
    entry_ids = await async_extract_config_entry_ids(hass, service_call)

    if not entry_ids:
        _LOGGER.error(
            "No config entries were specified and no poolcop entities were targeted"
        )
        return []

    coordinators = []
    for entry_id in entry_ids:
        if entry_id not in hass.data[DOMAIN]:
            continue

        coordinator = hass.data[DOMAIN][entry_id]
        if isinstance(coordinator, PoolCopDataUpdateCoordinator):
            coordinators.append(coordinator)

    return coordinators


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up PoolCop services."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_PUMP_SPEED):
        return

    async def async_set_pump_speed(service_call: ServiceCall) -> None:
        """Set the pump speed."""
        speed = service_call.data["speed"]

        coordinators = await _async_get_targeted_coordinators(hass, service_call)
        if not coordinators:
            return

        for coordinator in coordinators:
            try:
                # The library directly accepts speed levels 1, 2, or 3
                await coordinator.poolcopilot.set_pump_speed(speed)
                # Schedule refresh instead of immediate refresh to avoid API overload
                coordinator.async_schedule_refresh()
            except (ConnectionError, TimeoutError) as err:
                _LOGGER.error("Error setting pump speed: %s", err)

    async def async_toggle_pump(service_call: ServiceCall) -> None:
        """Toggle the pump state."""
        coordinators = await _async_get_targeted_coordinators(hass, service_call)
        if not coordinators:
            return

        for coordinator in coordinators:
            try:
                await coordinator.poolcopilot.toggle_pump()
                coordinator.async_schedule_refresh()
            except (ConnectionError, TimeoutError) as err:
                _LOGGER.error("Error toggling pump: %s", err)

    async def async_toggle_aux(service_call: ServiceCall) -> None:
        """Toggle an auxiliary output."""
        aux_id = service_call.data["aux_id"]

        coordinators = await _async_get_targeted_coordinators(hass, service_call)
        if not coordinators:
            return

        for coordinator in coordinators:
            try:
                await coordinator.poolcopilot.toggle_aux(aux_id)
                coordinator.async_schedule_refresh()
            except (ConnectionError, TimeoutError) as err:
                _LOGGER.error("Error toggling aux %d: %s", aux_id, err)

    async def async_set_valve_position(service_call: ServiceCall) -> None:
        """Set the valve position by name."""
        position_name = service_call.data["position"].lower()
        position_value = VALVE_POSITIONS.get(position_name)

        if position_value is None:
            _LOGGER.error("Invalid valve position name: %s", position_name)
            return

        coordinators = await _async_get_targeted_coordinators(hass, service_call)
        if not coordinators:
            return

        for coordinator in coordinators:
            try:
                await coordinator.poolcopilot.set_valve_position(position_value)
                coordinator.async_schedule_refresh()
                _LOGGER.info(
                    "Set valve position to %s (value %d)", position_name, position_value
                )
            except (ConnectionError, TimeoutError) as err:
                _LOGGER.error(
                    "Error setting valve position to %s: %s", position_name, err
                )

    async def async_clear_alarm(service_call: ServiceCall) -> None:
        """Clear active alarms."""
        coordinators = await _async_get_targeted_coordinators(hass, service_call)
        if not coordinators:
            return

        for coordinator in coordinators:
            try:
                await coordinator.poolcopilot.clear_alarm()
                coordinator.async_schedule_refresh()
            except (ConnectionError, TimeoutError) as err:
                _LOGGER.error("Error clearing alarm: %s", err)

    # Register all services
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PUMP_SPEED,
        async_set_pump_speed,
        schema=SET_PUMP_SPEED_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TOGGLE_PUMP,
        async_toggle_pump,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TOGGLE_AUX,
        async_toggle_aux,
        schema=TOGGLE_AUX_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        async_set_valve_position,
        schema=SET_VALVE_POSITION_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_ALARM,
        async_clear_alarm,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload PoolCop services."""
    if not hass.services.has_service(DOMAIN, SERVICE_SET_PUMP_SPEED):
        return

    hass.services.async_remove(DOMAIN, SERVICE_SET_PUMP_SPEED)
    hass.services.async_remove(DOMAIN, SERVICE_TOGGLE_PUMP)
    hass.services.async_remove(DOMAIN, SERVICE_TOGGLE_AUX)
    hass.services.async_remove(DOMAIN, SERVICE_SET_VALVE_POSITION)
    hass.services.async_remove(DOMAIN, SERVICE_CLEAR_ALARM)
