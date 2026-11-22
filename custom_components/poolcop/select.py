"""Support for PoolCop select entities."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import FILTRATION_MODES
from .coordinator import (
    SPEED_NAME_TO_LEVEL,
    VALVE_NAME_TO_ID,
    PoolCopConfigEntry,
    PoolCopDataUpdateCoordinator,
)
from .entity import PoolCopEntity

# Valve position options are the string keys from the client API
VALVE_POSITION_OPTIONS: Final = list(VALVE_NAME_TO_ID.keys())

# Speed options are the string keys from the client API
SPEED_OPTIONS: Final = list(SPEED_NAME_TO_LEVEL.keys())

FORCED_FILTRATION_OPTIONS: Final = [
    "NotForced",
    "Forced24H",
    "Forced48H",
    "Forced72H",
]

_FORCED_FILTRATION_MODES: Final = frozenset(FORCED_FILTRATION_OPTIONS[1:])


def option_key(value: str) -> str:
    """Return the translation key of an API value (EcoPlus -> eco_plus)."""
    return re.sub(r"(?<=[a-z])(?=[A-Z0-9])", "_", value).lower()


@dataclass(frozen=True)
class PoolCopSelectEntityDescriptionMixin:
    """Mixin for PoolCop select entity description."""

    async_set_fn: Callable[[PoolCopDataUpdateCoordinator, str], Awaitable[None]]
    current_fn: Callable[[PoolCopDataUpdateCoordinator], str | None]


@dataclass(frozen=True)
class PoolCopSelectEntityDescription(
    SelectEntityDescription, PoolCopSelectEntityDescriptionMixin
):
    """Class describing PoolCop select entities."""


async def _async_set_pump_speed(
    coordinator: PoolCopDataUpdateCoordinator, option: str
) -> None:
    """Set pump speed using string value (None, Speed1-Speed8)."""
    await coordinator.set_pump_speed(option)


def _get_current_pump_speed(coordinator: PoolCopDataUpdateCoordinator) -> str | None:
    """Get current pump speed as a string (None, Speed1-Speed8)."""
    pumps = coordinator.data.device.state.pumps
    if not pumps:
        return None
    pump = pumps[0]
    if not pump.pump_state:
        return "None"
    return pump.current_speed


def _get_pump_speed_options(coordinator: PoolCopDataUpdateCoordinator) -> list[str]:
    """Get pump speed options based on number of speeds supported."""
    pumps = coordinator.data.device.state.pumps
    if not pumps:
        return ["None", "Speed1"]

    # number_of_speeds is a string like "Speed1", "Speed3", etc.
    nb_speeds_str = pumps[0].number_of_speeds
    nb_level = SPEED_NAME_TO_LEVEL.get(nb_speeds_str, 1)

    # Generate options: None (off) through Speed<N>
    options = ["None"]
    for i in range(1, nb_level + 1):
        options.append(f"Speed{i}")
    return options


async def _async_set_valve_position(
    coordinator: PoolCopDataUpdateCoordinator, option: str
) -> None:
    """Set valve position using string value (Filter, Waste, etc.)."""
    await coordinator.set_valve_position(option)


def _get_current_valve_position(
    coordinator: PoolCopDataUpdateCoordinator,
) -> str | None:
    """Get current valve position as a string."""
    pumps = coordinator.data.device.state.pumps
    if not pumps:
        return None
    return pumps[0].valve_position


async def _async_set_forced_filtration(
    coordinator: PoolCopDataUpdateCoordinator, option: str
) -> None:
    """Set forced filtration mode."""
    await coordinator.set_forced_filtration(option)


def _get_current_forced_mode(
    coordinator: PoolCopDataUpdateCoordinator,
) -> str | None:
    """Get current forced filtration mode from pump filtration mode."""
    pumps = coordinator.data.device.state.pumps
    if not pumps:
        return None
    mode = pumps[0].filtration_mode
    return mode if mode in _FORCED_FILTRATION_MODES else "NotForced"


async def _async_set_filtration_mode(
    coordinator: PoolCopDataUpdateCoordinator, option: str
) -> None:
    """Set the filtration mode."""
    await coordinator.set_filtration_mode(option)


def _get_current_filtration_mode(
    coordinator: PoolCopDataUpdateCoordinator,
) -> str | None:
    """Get the filtration mode, or None while forced filtration overrides it."""
    pumps = coordinator.data.device.state.pumps
    if not pumps:
        return None
    mode = pumps[0].filtration_mode
    return mode if mode in FILTRATION_MODES else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolCopConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PoolCop select entities based on a config entry."""
    coordinator = entry.runtime_data

    entities = []

    # Add valve position entity
    entities.append(
        PoolCopSelectEntity(
            coordinator=coordinator,
            description=PoolCopSelectEntityDescription(
                key="valve_position",
                translation_key="valve_position",
                icon="mdi:valve",
                options=VALVE_POSITION_OPTIONS,
                async_set_fn=_async_set_valve_position,
                current_fn=_get_current_valve_position,
                entity_category=EntityCategory.CONFIG,
            ),
        )
    )

    # Add pump speed entity with dynamic options
    pump_speed_options = _get_pump_speed_options(coordinator)
    if pump_speed_options:
        entities.append(
            PoolCopSelectEntity(
                coordinator=coordinator,
                description=PoolCopSelectEntityDescription(
                    key="pump_speed",
                    translation_key="pump_speed",
                    icon="mdi:pump",
                    options=pump_speed_options,
                    async_set_fn=_async_set_pump_speed,
                    current_fn=_get_current_pump_speed,
                    entity_category=EntityCategory.CONFIG,
                ),
            )
        )

    entities.append(
        PoolCopSelectEntity(
            coordinator=coordinator,
            description=PoolCopSelectEntityDescription(
                key="filtration_mode",
                translation_key="filtration_mode",
                icon="mdi:air-filter",
                options=list(FILTRATION_MODES),
                async_set_fn=_async_set_filtration_mode,
                current_fn=_get_current_filtration_mode,
                entity_category=EntityCategory.CONFIG,
            ),
        )
    )

    # Add forced filtration entity
    entities.append(
        PoolCopSelectEntity(
            coordinator=coordinator,
            description=PoolCopSelectEntityDescription(
                key="forced_filtration",
                translation_key="forced_filtration",
                icon="mdi:pump",
                options=FORCED_FILTRATION_OPTIONS,
                async_set_fn=_async_set_forced_filtration,
                current_fn=_get_current_forced_mode,
                entity_category=EntityCategory.CONFIG,
            ),
        )
    )

    async_add_entities(entities)


class PoolCopSelectEntity(PoolCopEntity, SelectEntity):
    """Representation of a PoolCop select entity."""

    _attr_has_entity_name = True
    entity_description: PoolCopSelectEntityDescription

    def __init__(
        self,
        *,
        coordinator: PoolCopDataUpdateCoordinator,
        description: PoolCopSelectEntityDescription,
    ) -> None:
        """Initialize the select entity.

        The description's options are API values; the entity exposes them as
        translatable snake_case keys.
        """
        super().__init__(coordinator=coordinator, description=description)
        api_options = description.options or []
        self._to_api = {option_key(option): option for option in api_options}
        self._attr_options = list(self._to_api)

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        actual = self.entity_description.current_fn(self.coordinator)
        value = self.coordinator.resolve_pending(self.entity_description.key, actual)
        if value is None:
            return None
        key = option_key(value)
        return key if key in self._to_api else None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.async_set_fn(
            self.coordinator, self._to_api[option]
        )
        self.async_write_ha_state()
