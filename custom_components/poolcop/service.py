"""Services for PoolCop."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    DOMAIN,
    LOGGER,
    SERVICE_CLEAR_ALARM,
    SERVICE_SET_AUX,
    SERVICE_SET_PUMP,
    SERVICE_SET_PUMP_SPEED,
    SERVICE_SET_VALVE_POSITION,
    VALVE_POSITIONS,
)
from .coordinator import PoolCopDataUpdateCoordinator

SET_PUMP_SPEED_SCHEMA = vol.Schema(
    {
        vol.Required("speed"): str,
    }
)

SET_PUMP_SCHEMA = vol.Schema(
    {
        vol.Required("on"): bool,
    }
)

SET_AUX_SCHEMA = vol.Schema(
    {
        vol.Required("module"): str,
        vol.Required("aux"): str,
        vol.Required("on"): bool,
    }
)

SET_VALVE_POSITION_SCHEMA = vol.Schema(
    {
        vol.Required("position"): vol.In(VALVE_POSITIONS),
    }
)

CLEAR_ALARM_SCHEMA = vol.Schema(
    {
        vol.Optional("code"): str,
    }
)


def _get_coordinators(hass: HomeAssistant) -> list[PoolCopDataUpdateCoordinator]:
    """Get all PoolCop coordinators."""
    return [
        value
        for value in hass.data.get(DOMAIN, {}).values()
        if isinstance(value, PoolCopDataUpdateCoordinator)
    ]


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
            except Exception as err:
                LOGGER.error("Error setting pump speed: %s", err)

    async def async_set_pump(service_call: ServiceCall) -> None:
        """Turn pump on or off."""
        on = service_call.data["on"]
        for coordinator in _get_coordinators(hass):
            try:
                await coordinator.set_pump(on=on)
                await coordinator.async_refresh()
            except Exception as err:
                LOGGER.error("Error setting pump: %s", err)

    async def async_set_aux(service_call: ServiceCall) -> None:
        """Set an auxiliary output on or off."""
        module = service_call.data["module"]
        aux = service_call.data["aux"]
        on = service_call.data["on"]
        for coordinator in _get_coordinators(hass):
            try:
                await coordinator.set_auxiliary(module, aux, on=on)
                await coordinator.async_refresh()
            except Exception as err:
                LOGGER.error("Error setting auxiliary %s/%s: %s", module, aux, err)

    async def async_set_valve_position(service_call: ServiceCall) -> None:
        """Set the valve position."""
        position = service_call.data["position"]
        for coordinator in _get_coordinators(hass):
            try:
                await coordinator.set_valve_position(position)
                await coordinator.async_refresh()
            except Exception as err:
                LOGGER.error("Error setting valve position: %s", err)

    async def async_clear_alarm(service_call: ServiceCall) -> None:
        """Clear alarms."""
        code = service_call.data.get("code")
        for coordinator in _get_coordinators(hass):
            try:
                if code:
                    await coordinator.clear_alarm(code)
                else:
                    await coordinator.clear_all_alarms()
                await coordinator.async_refresh()
            except Exception as err:
                LOGGER.error("Error clearing alarm: %s", err)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PUMP_SPEED,
        async_set_pump_speed,
        schema=SET_PUMP_SPEED_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PUMP, async_set_pump, schema=SET_PUMP_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_AUX, async_set_aux, schema=SET_AUX_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        async_set_valve_position,
        schema=SET_VALVE_POSITION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_ALARM, async_clear_alarm, schema=CLEAR_ALARM_SCHEMA
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload PoolCop services."""
    if not hass.services.has_service(DOMAIN, SERVICE_SET_PUMP_SPEED):
        return

    hass.services.async_remove(DOMAIN, SERVICE_SET_PUMP_SPEED)
    hass.services.async_remove(DOMAIN, SERVICE_SET_PUMP)
    hass.services.async_remove(DOMAIN, SERVICE_SET_AUX)
    hass.services.async_remove(DOMAIN, SERVICE_SET_VALVE_POSITION)
    hass.services.async_remove(DOMAIN, SERVICE_CLEAR_ALARM)
