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

    # Dynamic aux switches from aux[] array where switchable and not slaved
    aux_list = coordinator.data.status_value("aux") or []
    for aux in aux_list:
        if aux.get("switchable") and not aux.get("slave"):
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
        return bool(self.coordinator.data.status_value("status.pump"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the pump on."""
        await self.coordinator.toggle_pump(turn_on=True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the pump off."""
        await self.coordinator.toggle_pump(turn_on=False)
        self.async_write_ha_state()


class PoolCopAuxSwitch(PoolCopEntity, SwitchEntity):  # type: ignore[misc]
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
        api_label = aux_data.get("label", "")
        label = aux_display_name(api_label, self._aux_id)
        self._label_id = aux_label_id(api_label)

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
            await self.coordinator.toggle_auxiliary(self._aux_id)
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the aux output off."""
        if self.is_on:
            await self.coordinator.toggle_auxiliary(self._aux_id)
            self.async_write_ha_state()
