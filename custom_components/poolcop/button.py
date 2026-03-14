"""Support for PoolCop buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PoolCopDataUpdateCoordinator
from .entity import PoolCopEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PoolCop buttons based on a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PoolCopClearAlarmButton(coordinator)])


class PoolCopClearAlarmButton(PoolCopEntity, ButtonEntity):  # type: ignore[misc]
    """Button to clear PoolCop alarms."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:alert-remove"

    def __init__(self, coordinator: PoolCopDataUpdateCoordinator) -> None:
        """Initialize the clear alarm button."""
        super().__init__(
            coordinator=coordinator,
            description=EntityDescription(key="clear_alarm", name="Clear Alarm"),
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.clear_alarm()
        await self.coordinator.async_refresh()
