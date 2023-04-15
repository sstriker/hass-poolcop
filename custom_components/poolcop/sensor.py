"""Support for PoolCop sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PoolCopData, PoolCopDataUpdateCoordinator
from .entity import PoolCopEntity


@dataclass
class PoolCopSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[PoolCopData], str | int | float | datetime | None]


@dataclass
class PoolCopSensorEntityDescription(
    SensorEntityDescription, PoolCopSensorEntityDescriptionMixin
):
    """Describes PoolCop sensor entity."""


def _value_fn(
    path: str,
) -> Callable[[PoolCopData], str | int | float | datetime | None]:
    """Return a value function for data at path."""

    def value_fn(data: PoolCopData) -> str | int | float | datetime | None:
        return data.status_value(path)

    return value_fn


def _datetime_value_fn(
    path: str,
) -> Callable[[PoolCopData], datetime | None]:
    """Return a value function for timestamp at path."""

    def value_fn(data: PoolCopData) -> datetime | None:
        value = data.status_value(path)
        if value is None:
            return None
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")

    return value_fn


SENSORS: tuple[PoolCopSensorEntityDescription, ...] = (
    PoolCopSensorEntityDescription(
        key="temperature_water",
        name="Water temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=_value_fn("temperature.water"),
    ),
    PoolCopSensorEntityDescription(
        key="temperature_air",
        name="Air temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=_value_fn("temperature.air"),
    ),
    PoolCopSensorEntityDescription(
        key="pressure",
        name="Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.PA,
        value_fn=_value_fn("pressure"),
    ),
    PoolCopSensorEntityDescription(
        key="pH",
        name="pH",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="pH",
        value_fn=_value_fn("pH"),
    ),
    PoolCopSensorEntityDescription(
        key="orp",
        name="Oxidation-Reduction Potential",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value_fn("orp"),
    ),
    PoolCopSensorEntityDescription(
        key="ioniser",
        name="ioniser",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value_fn("ioniser"),
    ),
    PoolCopSensorEntityDescription(
        key="voltage",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=_value_fn("voltage"),
    ),
    PoolCopSensorEntityDescription(
        key="waterlevel",
        name="Waterlevel",
        value_fn=_value_fn("waterlevel"),
    ),
    PoolCopSensorEntityDescription(
        key="valve_position",
        name="Valve position",
        value_fn=_value_fn("status.valveposition"),
    ),
    PoolCopSensorEntityDescription(
        key="pump_speed",
        name="Pump speed",
        value_fn=_value_fn("status.pumpspeed"),
    ),
    PoolCopSensorEntityDescription(
        key="poolcop",
        name="Poolcop ?",
        value_fn=_value_fn("status.poolcop"),
    ),
    # poolcop mode?
    # 7 = external filter
    # 6 = pause
    # 3 = cycle 2?
    PoolCopSensorEntityDescription(
        key="last_backwash",
        name="Last backwash",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_datetime_value_fn("history.backwash"),
    ),
    PoolCopSensorEntityDescription(
        key="last_refill",
        name="Last refill",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_datetime_value_fn("history.refill"),
    ),
    PoolCopSensorEntityDescription(
        key="last_ph_measure",
        name="Last pH measure",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_datetime_value_fn("history.ph_measure"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PoolCop sensors based on a config entry."""
    coordinator: PoolCopDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PoolCopSensorEntity(coordinator=coordinator, description=description)
        for description in SENSORS
    )


class PoolCopSensorEntity(PoolCopEntity, SensorEntity):
    """Defines a PoolCop sensor."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by PoolCop"
    entity_description: PoolCopSensorEntityDescription

    def __init__(
        self,
        *,
        coordinator: PoolCopDataUpdateCoordinator,
        description: PoolCopSensorEntityDescription,
    ) -> None:
        """Initialize PoolCop sensor."""
        super().__init__(coordinator=coordinator, description=description)
        self.entity_id = f"{SENSOR_DOMAIN}.{self._attr_unique_id}"

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
