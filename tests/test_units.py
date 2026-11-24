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


async def test_sensors_follow_account_units(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Values are metric; the account's units are suggested for display."""
    hass.config.units = METRIC_SYSTEM
    mock_poolcop_api.units = IMPERIAL
    mock_device_data["state"]["waterTemperature"] = 25.0
    mock_device_data["state"]["pumpsInfo"][0]["pumpPressure"] = 62.7
    mock_device_data["settings"]["pool"]["volume"] = 77
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
    assert water.attributes["unit_of_measurement"] == "°F"
    assert float(water.state) == pytest.approx(77.0)
    pressure = state("_pressure")
    assert pressure.attributes["unit_of_measurement"] == "psi"
    assert float(pressure.state) == pytest.approx(9.09, abs=0.01)
    volume = state("_pool_volume")
    assert volume.attributes["unit_of_measurement"] == "gal"
    assert float(volume.state) == pytest.approx(20341, rel=1e-3)

    coordinator = mock_config_entry.runtime_data
    assert coordinator._pool_volume_m3() == 77


async def test_sensors_without_units_header(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Without a units header HA's own unit system decides."""
    hass.config.units = METRIC_SYSTEM
    mock_device_data["state"]["pumpsInfo"][0]["pumpPressure"] = 62.7
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(mock_device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(mock_pool_data)]
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.poolcop.helpers.PoolCopClientAPI",
        return_value=mock_poolcop_api,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    pressure = next(
        s for s in hass.states.async_all("sensor") if s.entity_id.endswith("_pressure")
    )
    assert pressure.attributes["unit_of_measurement"] == "kPa"
    assert float(pressure.state) == pytest.approx(62.7)
