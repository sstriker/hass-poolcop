"""Support for PoolCop select entities."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, VALVE_POSITIONS
from .coordinator import PoolCopDataUpdateCoordinator
from .entity import PoolCopEntity


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
    """Set pump speed."""
    await coordinator.set_pump_speed(option)


def _get_current_pump_speed(coordinator: PoolCopDataUpdateCoordinator) -> str | None:
    """Get current pump speed."""
    pump = coordinator.data.pump
    if pump is None:
        return None
    if not pump.pump_state:
        return "None"
    return pump.current_speed


async def _async_set_valve_position(
    coordinator: PoolCopDataUpdateCoordinator, option: str
) -> None:
    """Set valve position."""
    await coordinator.set_valve_position(option)


def _get_current_valve_position(
    coordinator: PoolCopDataUpdateCoordinator,
) -> str | None:
    """Get current valve position."""
    pump = coordinator.data.pump
    if pump is None:
        return None
    return pump.valve_position


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PoolCop select entities based on a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Valve position select
    entities.append(
        PoolCopSelectEntity(
            coordinator=coordinator,
            description=PoolCopSelectEntityDescription(
                key="valve_position",
                name="Valve Position",
                icon="mdi:valve",
                options=VALVE_POSITIONS,
                async_set_fn=_async_set_valve_position,
                current_fn=_get_current_valve_position,
                entity_category=EntityCategory.CONFIG,
            ),
        )
    )

    # Pump speed select — options are string speed names from cloud API
    speed_options = ["None", "Speed1", "Speed2", "Speed3"]
    # Could extend to Speed4-Speed8 based on pump config
    if coordinator.data.pump_config:
        nb_speed = coordinator.data.pump_config.get("nbSpeed", 3)
        if isinstance(nb_speed, int) and nb_speed > 0:
            speed_options = ["None"] + [f"Speed{i}" for i in range(1, nb_speed + 1)]

    entities.append(
        PoolCopSelectEntity(
            coordinator=coordinator,
            description=PoolCopSelectEntityDescription(
                key="pump_speed",
                name="Pump Speed",
                icon="mdi:pump",
                options=speed_options,
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
        await self.coordinator.async_refresh()
