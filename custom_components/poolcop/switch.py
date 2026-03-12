"""Support for PoolCop switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PoolCopDataUpdateCoordinator
from .entity import PoolCopEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PoolCop switches based on a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = [PoolCopPumpSwitch(coordinator)]

    # Dynamic aux switches from aux[] array where switchable is true
    aux_list = coordinator.data.status_value("aux") or []
    for aux in aux_list:
        if aux.get("switchable"):
            entities.append(PoolCopAuxSwitch(coordinator, aux))

    async_add_entities(entities)


class PoolCopPumpSwitch(PoolCopEntity, SwitchEntity):
    """Representation of the PoolCop pump switch."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:pump"

    def __init__(self, coordinator: PoolCopDataUpdateCoordinator) -> None:
        """Initialize the pump switch."""
        from homeassistant.helpers.entity import EntityDescription

        super().__init__(
            coordinator=coordinator,
            description=EntityDescription(key="pump_switch", name="Pump"),
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the pump is on."""
        return bool(self.coordinator.data.status_value("status.pump"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the pump on."""
        await self.coordinator.toggle_pump(turn_on=True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the pump off."""
        await self.coordinator.toggle_pump(turn_on=False)
        self.async_write_ha_state()


class PoolCopAuxSwitch(PoolCopEntity, SwitchEntity):
    """Representation of a switchable PoolCop auxiliary output."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: PoolCopDataUpdateCoordinator,
        aux_data: dict,
    ) -> None:
        """Initialize the aux switch."""
        from homeassistant.helpers.entity import EntityDescription

        self._aux_id: int = aux_data["id"]
        label = aux_data.get("label", f"Aux {self._aux_id}")

        super().__init__(
            coordinator=coordinator,
            description=EntityDescription(
                key=f"aux_{self._aux_id}",
                name=label,
            ),
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the aux output is on."""
        aux_list = self.coordinator.data.status_value("aux") or []
        for aux in aux_list:
            if aux.get("id") == self._aux_id:
                return bool(aux.get("status"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        aux_list = self.coordinator.data.status_value("aux") or []
        for aux in aux_list:
            if aux.get("id") == self._aux_id:
                attrs = {}
                if "slave" in aux:
                    attrs["slave"] = aux["slave"]
                if "days" in aux:
                    attrs["days"] = aux["days"]
                if "label" in aux:
                    attrs["label"] = aux["label"]
                return attrs
        return {}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the aux output on."""
        if not self.is_on:
            await self.coordinator.toggle_auxiliary(self._aux_id)
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the aux output off."""
        if self.is_on:
            await self.coordinator.toggle_auxiliary(self._aux_id)
            self.async_write_ha_state()
