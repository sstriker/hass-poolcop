"""Actions (services) for PoolCop."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from datetime import time
from typing import Any

import probatio as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    DOMAIN,
    FILTRATION_MODES,
    SERVICE_CLEAR_ALARM,
    SERVICE_SET_FILTRATION_MODE,
    SERVICE_SET_FILTRATION_TIMERS,
    SERVICE_SET_PUMP_SPEED,
    SERVICE_SET_VALVE_POSITION,
    SERVICE_STOP_BACKWASH,
    SERVICE_TOGGLE_AUX,
    SERVICE_TOGGLE_PUMP,
)
from .coordinator import PoolCopConfigEntry, PoolCopDataUpdateCoordinator

VALVE_OPTIONS = ["Filter", "Waste", "Closed", "Backwash", "Bypass", "Rinse"]
MAX_SPEED = 8

ATTR_SPEED = "speed"
ATTR_POSITION = "position"
ATTR_AUX_ID = "aux_id"
ATTR_MODULE = "module"
ATTR_ALARM_CODE = "alarm_code"
ATTR_MODE = "mode"
TIMER_FIELDS = {
    0: ("cycle_1_start", "cycle_1_end", "cycle_1_enabled"),
    1: ("cycle_2_start", "cycle_2_end", "cycle_2_enabled"),
}


def _speed(value: Any) -> str:
    """Accept 0-8 or None/Speed1-Speed8 and return the API value."""
    if isinstance(value, str) and not value.strip().isdigit():
        for option in ("None", *(f"Speed{i}" for i in range(1, MAX_SPEED + 1))):
            if value.strip().lower() == option.lower():
                return option
        raise vol.Invalid(f"invalid speed: {value}")
    level = vol.All(vol.Coerce(int), vol.Range(min=0, max=MAX_SPEED))(value)
    return "None" if level == 0 else f"Speed{level}"


def _case_insensitive(options: list[str]) -> Callable[[Any], str]:
    """Return a validator mapping any casing (and snake_case) onto options."""
    lookup = {option.lower(): option for option in options}

    def validate(value: Any) -> str:
        key = str(value).replace("_", "").lower()
        if key not in lookup:
            raise vol.Invalid(f"must be one of {', '.join(options)}")
        return lookup[key]

    return validate


BASE_SCHEMA = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string})

SET_PUMP_SPEED_SCHEMA = BASE_SCHEMA.extend({vol.Required(ATTR_SPEED): _speed})
SET_VALVE_POSITION_SCHEMA = BASE_SCHEMA.extend(
    {vol.Required(ATTR_POSITION): _case_insensitive(VALVE_OPTIONS)}
)
TOGGLE_AUX_SCHEMA = BASE_SCHEMA.extend(
    {
        vol.Required(ATTR_AUX_ID): vol.All(vol.Coerce(int), vol.Range(min=1, max=15)),
        vol.Optional(ATTR_MODULE, default="None"): cv.string,
    }
)
CLEAR_ALARM_SCHEMA = BASE_SCHEMA.extend({vol.Optional(ATTR_ALARM_CODE): cv.string})
SET_FILTRATION_MODE_SCHEMA = BASE_SCHEMA.extend(
    {vol.Required(ATTR_MODE): _case_insensitive(FILTRATION_MODES)}
)
SET_FILTRATION_TIMERS_SCHEMA = BASE_SCHEMA.extend(
    {
        vol.Optional(ATTR_MODE): _case_insensitive(FILTRATION_MODES),
        **{
            vol.Optional(name): cv.time if not name.endswith("enabled") else cv.boolean
            for fields in TIMER_FIELDS.values()
            for name in fields
        },
    }
)


@callback
def _async_get_coordinator(
    hass: HomeAssistant, call: ServiceCall
) -> PoolCopDataUpdateCoordinator:
    """Return the coordinator of the targeted (or only) PoolCop."""
    if entry_id := call.data.get(ATTR_CONFIG_ENTRY_ID):
        entry: PoolCopConfigEntry | None = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_found",
                translation_placeholders={"entry_id": entry_id},
            )
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_loaded",
                translation_placeholders={"title": entry.title},
            )
        return entry.runtime_data

    loaded: list[PoolCopConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    if len(loaded) != 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_required" if loaded else "no_loaded_entries",
        )
    return loaded[0].runtime_data


async def _async_set_pump_speed(
    coordinator: PoolCopDataUpdateCoordinator, call: ServiceCall
) -> None:
    await coordinator.set_pump_speed(call.data[ATTR_SPEED])


async def _async_toggle_pump(
    coordinator: PoolCopDataUpdateCoordinator, call: ServiceCall
) -> None:
    pumps = coordinator.data.device.state.pumps
    current = coordinator.resolve_pending(
        "pump", pumps[0].pump_state if pumps else False
    )
    await coordinator.set_pump(on=not current)


async def _async_toggle_aux(
    coordinator: PoolCopDataUpdateCoordinator, call: ServiceCall
) -> None:
    aux_id: int = call.data[ATTR_AUX_ID]
    module: str = call.data[ATTR_MODULE]
    ports = coordinator.data.device.state.auxiliaries.get(module, {})
    current = coordinator.resolve_pending(
        f"aux_{module}_{aux_id}", ports.get(f"Aux{aux_id}", False)
    )
    await coordinator.set_auxiliary(module, aux_id, on=not current)


async def _async_set_valve_position(
    coordinator: PoolCopDataUpdateCoordinator, call: ServiceCall
) -> None:
    await coordinator.set_valve_position(call.data[ATTR_POSITION])


async def _async_clear_alarm(
    coordinator: PoolCopDataUpdateCoordinator, call: ServiceCall
) -> None:
    if code := call.data.get(ATTR_ALARM_CODE):
        await coordinator.clear_alarm(code)
    else:
        await coordinator.clear_all_alarms()


async def _async_stop_backwash(
    coordinator: PoolCopDataUpdateCoordinator, call: ServiceCall
) -> None:
    await coordinator.stop_backwash()


async def _async_set_filtration_mode(
    coordinator: PoolCopDataUpdateCoordinator, call: ServiceCall
) -> None:
    await coordinator.set_filtration_mode(call.data[ATTR_MODE])


async def _async_set_filtration_timers(
    coordinator: PoolCopDataUpdateCoordinator, call: ServiceCall
) -> None:
    changes: dict[int, dict[str, Any]] = {}
    for index, (start, end, enabled) in TIMER_FIELDS.items():
        change: dict[str, Any] = {}
        if start in call.data:
            change["time_on"] = _format_time(call.data[start])
        if end in call.data:
            change["time_off"] = _format_time(call.data[end])
        if enabled in call.data:
            change["enabled"] = call.data[enabled]
        if change:
            changes[index] = change

    mode: str | None = call.data.get(ATTR_MODE)
    if not changes and mode is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="nothing_to_change"
        )
    if mode is None:
        filtrations = coordinator.data.device.settings.filtrations
        current = filtrations[0].filtration_mode if filtrations else None
        mode = current if current in FILTRATION_MODES else "Timer"

    await coordinator.set_filtration_timers(
        mode, coordinator.filtration_timers_with(changes)
    )


def _format_time(value: time) -> str:
    return value.strftime("%H:%M:%S")


SERVICES: dict[
    str,
    tuple[
        vol.Schema,
        Callable[[PoolCopDataUpdateCoordinator, ServiceCall], Awaitable[None]],
    ],
] = {
    SERVICE_SET_PUMP_SPEED: (SET_PUMP_SPEED_SCHEMA, _async_set_pump_speed),
    SERVICE_TOGGLE_PUMP: (BASE_SCHEMA, _async_toggle_pump),
    SERVICE_TOGGLE_AUX: (TOGGLE_AUX_SCHEMA, _async_toggle_aux),
    SERVICE_SET_VALVE_POSITION: (SET_VALVE_POSITION_SCHEMA, _async_set_valve_position),
    SERVICE_CLEAR_ALARM: (CLEAR_ALARM_SCHEMA, _async_clear_alarm),
    SERVICE_STOP_BACKWASH: (BASE_SCHEMA, _async_stop_backwash),
    SERVICE_SET_FILTRATION_MODE: (
        SET_FILTRATION_MODE_SCHEMA,
        _async_set_filtration_mode,
    ),
    SERVICE_SET_FILTRATION_TIMERS: (
        SET_FILTRATION_TIMERS_SCHEMA,
        _async_set_filtration_timers,
    ),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the PoolCop actions."""

    def _make_handler(
        handler: Callable[[PoolCopDataUpdateCoordinator, ServiceCall], Awaitable[None]],
    ) -> Callable[[ServiceCall], Coroutine[Any, Any, None]]:
        async def _async_handle(call: ServiceCall) -> None:
            coordinator = _async_get_coordinator(hass, call)
            await handler(coordinator, call)
            coordinator.async_update_listeners()

        return _async_handle

    for name, (schema, handler) in SERVICES.items():
        hass.services.async_register(
            DOMAIN, name, _make_handler(handler), schema=schema
        )
