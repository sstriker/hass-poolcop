"""Support for PoolCop switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import AUX_LABEL_ICONS, DOMAIN
from .coordinator import PoolCopDataUpdateCoordinator
from .entity import PoolCopEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PoolCop switches based on a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = [PoolCopPumpSwitch(coordinator)]

    # Dynamic aux switches from auxiliaries list
    for aux in coordinator.data.auxiliaries:
        if aux.is_reserved:
            continue
        # Only create switches for switchable aux (mode != "Off" and not reserved)
        if aux.mode and aux.mode not in ("Off", "Slave"):
            entities.append(PoolCopAuxSwitch(coordinator, aux))

    async_add_entities(entities)


class PoolCopPumpSwitch(PoolCopEntity, SwitchEntity):  # type: ignore[misc]
    """Representation of the PoolCop pump switch."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:pump"

    def __init__(self, coordinator: PoolCopDataUpdateCoordinator) -> None:
        """Initialize the pump switch."""
        super().__init__(
            coordinator=coordinator,
            description=EntityDescription(key="pump_switch", name="Pump"),
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the pump is on."""
        pump = self.coordinator.data.pump
        return pump.pump_state if pump else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the pump on."""
        await self.coordinator.set_pump(on=True)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the pump off."""
        await self.coordinator.set_pump(on=False)
        await self.coordinator.async_refresh()


class PoolCopAuxSwitch(PoolCopEntity, SwitchEntity):  # type: ignore[misc]
    """Representation of a switchable PoolCop auxiliary output."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: PoolCopDataUpdateCoordinator,
        aux,
    ) -> None:
        """Initialize the aux switch."""
        self._module_id = aux.module_id
        self._aux_channel = aux.aux_channel
        label = (
            aux.friendly_name or aux.label or f"Aux {aux.module_id}/{aux.aux_channel}"
        )
        self._label = aux.label

        # Cloud API uses module/aux string identifiers
        self._module_str = f"AuxModule{aux.module_id}"
        self._aux_str = f"Aux{aux.aux_channel}"

        super().__init__(
            coordinator=coordinator,
            description=EntityDescription(
                key=f"aux_{aux.module_id}_{aux.aux_channel}",
                name=label,
            ),
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the aux output is on."""
        state_auxes = self.coordinator.data.state.auxiliaries
        if (
            self._module_str in state_auxes
            and self._aux_str in state_auxes[self._module_str]
        ):
            return state_auxes[self._module_str][self._aux_str]
        for aux in self.coordinator.data.auxiliaries:
            if (
                aux.module_id == self._module_id
                and aux.aux_channel == self._aux_channel
            ):
                return aux.status
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        for aux in self.coordinator.data.auxiliaries:
            if (
                aux.module_id == self._module_id
                and aux.aux_channel == self._aux_channel
            ):
                attrs: dict[str, Any] = {}
                if aux.mode:
                    attrs["mode"] = aux.mode
                if aux.label:
                    attrs["label"] = aux.label
                return attrs
        return {}

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        icons = AUX_LABEL_ICONS.get(self._label or "")
        if icons:
            return icons[0] if self.is_on else icons[1]
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the aux output on."""
        await self.coordinator.set_auxiliary(self._module_str, self._aux_str, on=True)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the aux output off."""
        await self.coordinator.set_auxiliary(self._module_str, self._aux_str, on=False)
        await self.coordinator.async_refresh()
