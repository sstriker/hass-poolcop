"""Support for PoolCop switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import AUX_LABEL_ICONS, DOMAIN, aux_display_name, aux_label_id
from .coordinator import PoolCopDataUpdateCoordinator
from .entity import PoolCopEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PoolCop switches based on a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = [PoolCopPumpSwitch(coordinator)]

    if coordinator.data.device.equipments_info.has_jet_stream:
        entities.append(PoolCopJetStreamSwitch(coordinator))

    # Dynamic aux switches: not reserved and not slaved
    for aux in coordinator.data.device.settings.auxs:
        if not aux.is_reserved and not aux.is_slave:
            entities.append(PoolCopAuxSwitch(coordinator, aux))

    async_add_entities(entities)


class PoolCopPumpSwitch(PoolCopEntity, SwitchEntity):  # type: ignore[misc]
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
        pumps = self.coordinator.data.device.state.pumps
        if pumps:
            return pumps[0].pump_state
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the pump on."""
        await self.coordinator.set_pump(on=True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the pump off."""
        await self.coordinator.set_pump(on=False)
        await self.coordinator.async_request_refresh()


class PoolCopJetStreamSwitch(PoolCopEntity, SwitchEntity):  # type: ignore[misc]
    """Representation of the PoolCop jet stream switch."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:waves-arrow-right"

    def __init__(self, coordinator: PoolCopDataUpdateCoordinator) -> None:
        """Initialize the jet stream switch."""
        from homeassistant.helpers.entity import EntityDescription

        super().__init__(
            coordinator=coordinator,
            description=EntityDescription(key="jet_stream_switch", name="Jet Stream"),
        )

    @property
    def is_on(self) -> bool:
        """Return true if the jet stream is running."""
        return self.coordinator.data.device.state.jet_stream.is_running

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the jet stream on."""
        await self.coordinator.set_jet_stream(on=True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the jet stream off."""
        await self.coordinator.set_jet_stream(on=False)
        await self.coordinator.async_request_refresh()


class PoolCopAuxSwitch(PoolCopEntity, SwitchEntity):  # type: ignore[misc]
    """Representation of a switchable PoolCop auxiliary output."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: PoolCopDataUpdateCoordinator,
        aux: "AuxSettings",
    ) -> None:
        """Initialize the aux switch."""
        from homeassistant.helpers.entity import EntityDescription

        self._aux_channel: int = aux.aux_channel
        self._module: str = aux.module
        self._aux_id_str: str = f"Aux{aux.aux_channel}"
        api_label = aux.label or ""
        label = aux_display_name(api_label, aux.aux_channel)
        self._label_id = aux_label_id(api_label)

        super().__init__(
            coordinator=coordinator,
            description=EntityDescription(
                key=f"aux_{aux.aux_channel}",
                name=label,
            ),
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the aux output is on."""
        auxiliaries = self.coordinator.data.device.state.auxiliaries
        module_ports = auxiliaries.get(self._module)
        if module_ports is not None:
            return module_ports.get(self._aux_id_str)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        for aux in self.coordinator.data.device.settings.auxs:
            if aux.aux_channel == self._aux_channel and aux.module == self._module:
                attrs: dict[str, Any] = {}
                if aux.days_of_week:
                    attrs["days"] = aux.days_of_week
                if aux.label:
                    attrs["label"] = aux.label
                if aux.friendly_name:
                    attrs["friendly_name"] = aux.friendly_name
                if aux.mode:
                    attrs["mode"] = aux.mode
                return attrs
        return {}

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        icons = (
            AUX_LABEL_ICONS.get(self._label_id) if self._label_id is not None else None
        )
        if icons:
            return icons[0] if self.is_on else icons[1]
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the aux output on."""
        if not self.is_on:
            await self.coordinator.set_auxiliary(
                self._module, self._aux_channel, on=True
            )
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the aux output off."""
        if self.is_on:
            await self.coordinator.set_auxiliary(
                self._module, self._aux_channel, on=False
            )
            await self.coordinator.async_request_refresh()
