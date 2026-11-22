"""Support for PoolCop buttons."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PoolCopConfigEntry, PoolCopDataUpdateCoordinator
from .entity import PoolCopEntity


@dataclass(frozen=True, kw_only=True)
class PoolCopButtonEntityDescription(ButtonEntityDescription):
    """Class describing PoolCop buttons."""

    press_fn: Callable[[PoolCopDataUpdateCoordinator], Awaitable[None]]


BUTTONS: tuple[PoolCopButtonEntityDescription, ...] = (
    PoolCopButtonEntityDescription(
        key="clear_alarm",
        translation_key="clear_alarm",
        icon="mdi:alert-remove",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda coordinator: coordinator.clear_all_alarms(),
    ),
    PoolCopButtonEntityDescription(
        key="stop_backwash",
        translation_key="stop_backwash",
        icon="mdi:stop-circle-outline",
        press_fn=lambda coordinator: coordinator.stop_backwash(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolCopConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PoolCop buttons based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        PoolCopButton(coordinator=coordinator, description=description)
        for description in BUTTONS
    )


class PoolCopButton(PoolCopEntity, ButtonEntity):
    """A PoolCop command button."""

    entity_description: PoolCopButtonEntityDescription

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(self.coordinator)
