"""Support for PoolCop select entities."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import (
    SPEED_NAME_TO_LEVEL,
    VALVE_NAME_TO_ID,
    PoolCopDataUpdateCoordinator,
)
from .entity import PoolCopEntity

# Valve position options are the string keys from the client API
VALVE_POSITION_OPTIONS: Final = list(VALVE_NAME_TO_ID.keys())

# Speed options are the string keys from the client API
SPEED_OPTIONS: Final = list(SPEED_NAME_TO_LEVEL.keys())


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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PoolCop select entities based on a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Add valve position entity
    entities.append(
        PoolCopSelectEntity(
            coordinator=coordinator,
            description=PoolCopSelectEntityDescription(
                key="valve_position",
                name="Valve Position",
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
                    name="Pump Speed",
                    icon="mdi:pump",
                    options=pump_speed_options,
                    async_set_fn=_async_set_pump_speed,
                    current_fn=_get_current_pump_speed,
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
        """Initialize the select entity."""
        super().__init__(coordinator=coordinator, description=description)

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self.entity_description.current_fn(self.coordinator)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.async_set_fn(self.coordinator, option)
        self.async_write_ha_state()
