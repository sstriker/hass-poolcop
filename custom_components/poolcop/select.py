"""Support for PoolCop select entities."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER, VALVE_POSITIONS
from .coordinator import PoolCopDataUpdateCoordinator
from .entity import PoolCopEntity

VALVE_POSITION_OPTIONS: Final = list(VALVE_POSITIONS.keys())


@dataclass
class PoolCopSelectEntityDescriptionMixin:
    """Mixin for PoolCop select entity description."""

    async_set_fn: Callable[[PoolCopDataUpdateCoordinator, str], Awaitable[None]]
    current_fn: Callable[[PoolCopDataUpdateCoordinator], str | None]


@dataclass
class PoolCopSelectEntityDescription(
    SelectEntityDescription, PoolCopSelectEntityDescriptionMixin
):
    """Class describing PoolCop select entities."""


async def _async_set_pump_speed(
    coordinator: PoolCopDataUpdateCoordinator, option: str
) -> None:
    """Set pump speed."""
    try:
        speed = int(option)
        await coordinator.set_pump_speed(speed)
    except ValueError:
        LOGGER.error("Invalid pump speed value: %s", option)


def _get_current_pump_speed(coordinator: PoolCopDataUpdateCoordinator) -> str | None:
    """Get current pump speed."""
    is_pump_on = bool(coordinator.data.status_value("status.pump"))
    if not is_pump_on:
        return "0"  # Off

    # Get current pump speed
    speed = coordinator.data.status_value("status.pumpspeed")
    if speed is None or not isinstance(speed, int):
        return None

    return str(speed)


def _get_pump_speed_options(coordinator: PoolCopDataUpdateCoordinator) -> list[str]:
    """Get pump speed options based on number of speeds supported."""
    # Get number of speeds from pump settings
    nb_speed = coordinator.data.status_value("settings.pump.nb_speed")

    # Fallback to configuration if settings not available
    if nb_speed is None or not isinstance(nb_speed, int) or nb_speed <= 0:
        # Check pump speed in configuration
        pump_type = coordinator.data.status_value("conf.pump_type")
        if pump_type == 3:  # Three speed pump
            nb_speed = 3
        elif pump_type == 2:  # Two speed pump
            nb_speed = 2
        elif pump_type == 1:  # Single speed pump
            nb_speed = 1
        else:
            nb_speed = 3  # Default to 3 speeds if unknown

    # Generate options: 0 (Off) through nb_speed
    return [str(i) for i in range(nb_speed + 1)]


async def _async_set_valve_position(
    coordinator: PoolCopDataUpdateCoordinator, option: str
) -> None:
    """Set valve position."""
    position_value = VALVE_POSITIONS.get(option.lower())
    if position_value is not None:
        await coordinator.set_valve_position(position_value)


def _get_current_valve_position(
    coordinator: PoolCopDataUpdateCoordinator,
) -> str | None:
    """Get current valve position."""
    position_value = coordinator.data.status_value("status.valveposition")
    if position_value is None:
        return None

    # Convert the numeric value back to the string name
    for position_name, value in VALVE_POSITIONS.items():
        if value == position_value:
            return position_name.capitalize()

    return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PoolCop select entities based on a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Create list of entities to add
    entities = []

    # Add valve position entity
    entities.append(
        PoolCopSelectEntity(
            coordinator=coordinator,
            description=PoolCopSelectEntityDescription(
                key="valve_position",
                name="Valve Position",
                icon="mdi:valve",
                options=[option.capitalize() for option in VALVE_POSITION_OPTIONS],
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
