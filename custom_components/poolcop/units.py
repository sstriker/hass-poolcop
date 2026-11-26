"""Map the Client API's UCUM unit codes to Home Assistant units.

The API names the units chosen in the account's PoolCop app preferences in a
``units`` response header such as
``temperature=Cel,pressure=kPa,volume=m3,flowRate=m3/h`` (UCUM codes). The
values themselves are always metric (°C, kPa, m³, m³/h): an account set to bar
still gets a filter pressure of 62.7. The header is only used to suggest the
display unit.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from homeassistant.const import (
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)

from .const import LOGGER

TEMPERATURE: Final = "temperature"
PRESSURE: Final = "pressure"
VOLUME: Final = "volume"
FLOW_RATE: Final = "flowRate"

UCUM_UNITS: Final[dict[str, dict[str, str]]] = {
    TEMPERATURE: {
        "Cel": UnitOfTemperature.CELSIUS,
        "[degF]": UnitOfTemperature.FAHRENHEIT,
        "K": UnitOfTemperature.KELVIN,
    },
    PRESSURE: {
        "Pa": UnitOfPressure.PA,
        "hPa": UnitOfPressure.HPA,
        "kPa": UnitOfPressure.KPA,
        "bar": UnitOfPressure.BAR,
        "mbar": UnitOfPressure.MBAR,
        "[psi]": UnitOfPressure.PSI,
    },
    VOLUME: {
        "m3": UnitOfVolume.CUBIC_METERS,
        "L": UnitOfVolume.LITERS,
        "l": UnitOfVolume.LITERS,
        "[gal_us]": UnitOfVolume.GALLONS,
        "[ft_i]3": UnitOfVolume.CUBIC_FEET,
    },
    FLOW_RATE: {
        "m3/h": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "m3/min": UnitOfVolumeFlowRate.CUBIC_METERS_PER_MINUTE,
        "L/h": UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        "l/h": UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        "L/min": UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        "l/min": UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        "L/s": UnitOfVolumeFlowRate.LITERS_PER_SECOND,
        "l/s": UnitOfVolumeFlowRate.LITERS_PER_SECOND,
        "[gal_us]/h": UnitOfVolumeFlowRate.GALLONS_PER_HOUR,
        "[gal_us]/min": UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        "[ft_i]3/min": UnitOfVolumeFlowRate.CUBIC_FEET_PER_MINUTE,
    },
}

# The units the API's values are in.
METRIC_UNITS: Final[dict[str, str]] = {
    TEMPERATURE: UnitOfTemperature.CELSIUS,
    PRESSURE: UnitOfPressure.KPA,
    VOLUME: UnitOfVolume.CUBIC_METERS,
    FLOW_RATE: UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
}

_warned: set[tuple[str, str]] = set()


def ha_unit(units: Mapping[str, str], kind: str) -> str:
    """Return the Home Assistant unit for a measurement kind."""
    code = units.get(kind)
    if code is None:
        return METRIC_UNITS[kind]
    if (unit := UCUM_UNITS[kind].get(code)) is None:
        if (kind, code) not in _warned:
            _warned.add((kind, code))
            LOGGER.warning(
                "Unknown PoolCop %s unit %r, assuming %s",
                kind,
                code,
                METRIC_UNITS[kind],
            )
        return METRIC_UNITS[kind]
    return unit
