"""Services for PoolCop."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall

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
        vol.Required("speed"): vol.All(vol.Coerce(int), vol.In([0, 1, 2, 3])),
    }
)

SET_VALVE_POSITION_SCHEMA = vol.Schema(
    {
        vol.Required("position"): vol.In(list(VALVE_POSITIONS.keys())),
    }
)

TOGGLE_AUX_SCHEMA = vol.Schema(
    {
        vol.Required("aux_id"): vol.All(vol.Coerce(int), vol.Range(min=1, max=15)),
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up PoolCop services."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_PUMP_SPEED):
        return

    async def async_set_pump_speed(service_call: ServiceCall) -> None:
        """Set the pump speed."""
        speed = service_call.data["speed"]

        coordinators = [
            value
            for value in hass.data[DOMAIN].values()
            if isinstance(value, PoolCopDataUpdateCoordinator)
        ]

        for coordinator in coordinators:
            try:
                await coordinator.set_pump_speed(speed)
                await coordinator.async_refresh()
            except (ConnectionError, TimeoutError) as err:
                _LOGGER.error("Error setting pump speed: %s", err)

    async def async_toggle_pump(service_call: ServiceCall) -> None:
        """Toggle the pump state."""
        coordinators = [
            value
            for value in hass.data[DOMAIN].values()
            if isinstance(value, PoolCopDataUpdateCoordinator)
        ]

        for coordinator in coordinators:
            try:
                # Get current pump state
                pump_state = bool(coordinator.data.status_value("status.pump"))
                # Toggle it by setting the opposite state
                await coordinator.toggle_pump(not pump_state)
                await coordinator.async_refresh()
            except (ConnectionError, TimeoutError, KeyError, TypeError) as err:
                _LOGGER.error("Error toggling pump: %s", err)

    async def async_toggle_aux(service_call: ServiceCall) -> None:
        """Toggle an auxiliary output."""
        aux_id = service_call.data["aux_id"]

        coordinators = [
            value
            for value in hass.data[DOMAIN].values()
            if isinstance(value, PoolCopDataUpdateCoordinator)
        ]

        for coordinator in coordinators:
            try:
                await coordinator.toggle_auxiliary(aux_id)
                await coordinator.async_refresh()
            except (ConnectionError, TimeoutError) as err:
                _LOGGER.error("Error toggling auxiliary %s: %s", aux_id, err)

    async def async_set_valve_position(service_call: ServiceCall) -> None:
        """Set the valve position."""
        position_name = service_call.data["position"]
        position_value = VALVE_POSITIONS.get(position_name.lower())

        if position_value is None:
            _LOGGER.error("Invalid valve position: %s", position_name)
            return

        coordinators = [
            value
            for value in hass.data[DOMAIN].values()
            if isinstance(value, PoolCopDataUpdateCoordinator)
        ]

        for coordinator in coordinators:
            try:
                await coordinator.set_valve_position(position_value)
                await coordinator.async_refresh()
            except (ConnectionError, TimeoutError) as err:
                _LOGGER.error("Error setting valve position: %s", err)

    async def async_clear_alarm(service_call: ServiceCall) -> None:
        """Clear active alarms."""
        coordinators = [
            value
            for value in hass.data[DOMAIN].values()
            if isinstance(value, PoolCopDataUpdateCoordinator)
        ]

        for coordinator in coordinators:
            try:
                await coordinator.clear_alarm()
                await coordinator.async_refresh()
            except (ConnectionError, TimeoutError) as err:
                _LOGGER.error("Error clearing alarm: %s", err)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PUMP_SPEED,
        async_set_pump_speed,
        schema=SET_PUMP_SPEED_SCHEMA,
    )

    hass.services.async_register(DOMAIN, SERVICE_TOGGLE_PUMP, async_toggle_pump)

    hass.services.async_register(
        DOMAIN, SERVICE_TOGGLE_AUX, async_toggle_aux, schema=TOGGLE_AUX_SCHEMA
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        async_set_valve_position,
        schema=SET_VALVE_POSITION_SCHEMA,
    )

    hass.services.async_register(DOMAIN, SERVICE_CLEAR_ALARM, async_clear_alarm)


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload PoolCop services."""
    if not hass.services.has_service(DOMAIN, SERVICE_SET_PUMP_SPEED):
        return

    hass.services.async_remove(DOMAIN, SERVICE_SET_PUMP_SPEED)
    hass.services.async_remove(DOMAIN, SERVICE_TOGGLE_PUMP)
    hass.services.async_remove(DOMAIN, SERVICE_TOGGLE_AUX)
    hass.services.async_remove(DOMAIN, SERVICE_SET_VALVE_POSITION)
    hass.services.async_remove(DOMAIN, SERVICE_CLEAR_ALARM)
