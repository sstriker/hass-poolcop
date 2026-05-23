"""Services for PoolCop."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    DOMAIN,
    LOGGER,
    SERVICE_CLEAR_ALARM,
    SERVICE_SET_PUMP_SPEED,
    SERVICE_SET_VALVE_POSITION,
    SERVICE_TOGGLE_AUX,
    SERVICE_TOGGLE_PUMP,
)
from .coordinator import PoolCopDataUpdateCoordinator

VALVE_OPTIONS = ["Filter", "Waste", "Closed", "Backwash", "Bypass", "Rinse"]
SPEED_OPTIONS = ["None", "Speed1", "Speed2", "Speed3", "Speed4", "Speed5", "Speed6", "Speed7", "Speed8"]

SET_PUMP_SPEED_SCHEMA = vol.Schema(
    {
        vol.Required("speed"): vol.In(SPEED_OPTIONS),
    }
)

SET_VALVE_POSITION_SCHEMA = vol.Schema(
    {
        vol.Required("position"): vol.In(VALVE_OPTIONS),
    }
)

TOGGLE_AUX_SCHEMA = vol.Schema(
    {
        vol.Required("aux_id"): vol.All(vol.Coerce(int), vol.Range(min=1, max=6)),
        vol.Optional("module", default="None"): str,
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up PoolCop services."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_PUMP_SPEED):
        return

    async def async_set_pump_speed(service_call: ServiceCall) -> None:
        """Set the pump speed."""
        speed = service_call.data["speed"]

        for coordinator in _get_coordinators(hass):
            try:
                await coordinator.set_pump_speed(speed)
                await coordinator.async_refresh()
            except (ConnectionError, TimeoutError) as err:
                LOGGER.error("Error setting pump speed: %s", err)

    async def async_toggle_pump(service_call: ServiceCall) -> None:
        """Toggle the pump state."""
        for coordinator in _get_coordinators(hass):
            try:
                pump = coordinator.data.device.state.pumps[0] if coordinator.data.device.state.pumps else None
                current_state = pump.pump_state if pump else False
                await coordinator.set_pump(on=not current_state)
                await coordinator.async_refresh()
            except (ConnectionError, TimeoutError) as err:
                LOGGER.error("Error toggling pump: %s", err)

    async def async_toggle_aux(service_call: ServiceCall) -> None:
        """Toggle an auxiliary output."""
        aux_id = service_call.data["aux_id"]
        module = service_call.data.get("module", "None")

        for coordinator in _get_coordinators(hass):
            try:
                # Get current state
                aux_states = coordinator.data.device.state.auxiliaries.get(module, {})
                current = aux_states.get(f"Aux{aux_id}", False)
                await coordinator.set_auxiliary(module, aux_id, on=not current)
                await coordinator.async_refresh()
            except (ConnectionError, TimeoutError) as err:
                LOGGER.error("Error toggling auxiliary %s: %s", aux_id, err)

    async def async_set_valve_position(service_call: ServiceCall) -> None:
        """Set the valve position."""
        position = service_call.data["position"]

        for coordinator in _get_coordinators(hass):
            try:
                await coordinator.set_valve_position(position)
                await coordinator.async_refresh()
            except (ConnectionError, TimeoutError) as err:
                LOGGER.error("Error setting valve position: %s", err)

    async def async_clear_alarm(service_call: ServiceCall) -> None:
        """Clear all active alarms."""
        for coordinator in _get_coordinators(hass):
            try:
                await coordinator.clear_all_alarms()
                await coordinator.async_refresh()
            except (ConnectionError, TimeoutError) as err:
                LOGGER.error("Error clearing alarms: %s", err)

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


def _get_coordinators(hass: HomeAssistant) -> list[PoolCopDataUpdateCoordinator]:
    """Get all PoolCop coordinators."""
    return [
        value
        for value in hass.data[DOMAIN].values()
        if isinstance(value, PoolCopDataUpdateCoordinator)
    ]


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload PoolCop services."""
    if not hass.services.has_service(DOMAIN, SERVICE_SET_PUMP_SPEED):
        return

    hass.services.async_remove(DOMAIN, SERVICE_SET_PUMP_SPEED)
    hass.services.async_remove(DOMAIN, SERVICE_TOGGLE_PUMP)
    hass.services.async_remove(DOMAIN, SERVICE_TOGGLE_AUX)
    hass.services.async_remove(DOMAIN, SERVICE_SET_VALVE_POSITION)
    hass.services.async_remove(DOMAIN, SERVICE_CLEAR_ALARM)
