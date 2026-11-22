"""Test unit handling from the API's units header."""

from unittest.mock import patch

import pytest
from aiopoolcop import Pool, PoolCopDevice
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import METRIC_SYSTEM

from custom_components.poolcop.units import (
    FLOW_RATE,
    PRESSURE,
    TEMPERATURE,
    VOLUME,
    ha_unit,
    to_cubic_meters,
    to_cubic_meters_per_hour,
)

IMPERIAL = {
    TEMPERATURE: "[degF]",
    PRESSURE: "[psi]",
    VOLUME: "[gal_us]",
    FLOW_RATE: "[gal_us]/min",
}


@pytest.mark.parametrize(
    ("kind", "code", "expected"),
    [
        (TEMPERATURE, "Cel", "°C"),
        (TEMPERATURE, "[degF]", "°F"),
        (PRESSURE, "bar", "bar"),
        (PRESSURE, "[psi]", "psi"),
        (VOLUME, "L", "L"),
        (FLOW_RATE, "L/min", "L/min"),
    ],
)
def test_ha_unit(kind, code, expected):
    """UCUM codes map to Home Assistant units."""
    assert ha_unit({kind: code}, kind) == expected


def test_ha_unit_defaults_to_metric(caplog):
    """Missing or unknown codes fall back to metric, warning once."""
    assert ha_unit({}, PRESSURE) == "kPa"
    assert ha_unit({PRESSURE: "[atm]"}, PRESSURE) == "kPa"
    assert ha_unit({PRESSURE: "[atm]"}, PRESSURE) == "kPa"
    assert caplog.text.count("Unknown PoolCop pressure unit") == 1


def test_conversions():
    """Volumes and flow rates convert to metric for calculations."""
    assert to_cubic_meters(77, {}) == 77
    assert to_cubic_meters(1000, {VOLUME: "L"}) == pytest.approx(1)
    assert to_cubic_meters_per_hour(60, {FLOW_RATE: "L/min"}) == pytest.approx(3.6)


async def test_sensors_follow_account_units(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Sensors use the account's units; HA converts them for display."""
    hass.config.units = METRIC_SYSTEM
    mock_poolcop_api.units = IMPERIAL
    mock_device_data["state"]["waterTemperature"] = 77.0
    mock_device_data["settings"]["pool"]["volume"] = 1000
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(mock_device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(mock_pool_data)]
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.poolcop.helpers.PoolCopClientAPI",
        return_value=mock_poolcop_api,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    def state(suffix: str):
        return next(
            s for s in hass.states.async_all("sensor") if s.entity_id.endswith(suffix)
        )

    water = state("_water_temperature")
    assert water.attributes["unit_of_measurement"] == "°C"
    assert float(water.state) == pytest.approx(25.0)
    assert state("_pool_volume").attributes["unit_of_measurement"] == "gal"

    coordinator = mock_config_entry.runtime_data
    assert coordinator._pool_volume_m3() == pytest.approx(3.785, rel=1e-3)
