"""Test PoolCop geo location platform."""

from unittest.mock import patch

from aiopoolcop import Pool, PoolCopDevice
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.poolcop.const import (
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
    CONF_MAP_MODE,
    DOMAIN,
    MAP_MODE_ATTENTION,
)

MOCK_API_KEY = "test-api-key-12345"


async def _setup_integration(hass, config_entry, mock_poolcop_api, device_data, pool_data):
    """Set up the integration and return the coordinator."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(pool_data)]
    config_entry.add_to_hass(hass)

    with patch("custom_components.poolcop.PoolCopClientAPI", return_value=mock_poolcop_api):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return hass.data[DOMAIN][config_entry.entry_id]


async def test_geo_location_with_coords(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Pool with coords creates geo_location entity."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("geo_location")
    poolcop_states = [s for s in states if s.attributes.get("source") == "poolcop"]
    assert len(poolcop_states) == 1

    state = poolcop_states[0]
    assert state.attributes.get("latitude") == 52.165958
    assert state.attributes.get("longitude") == 6.038603
    assert state.state is not None


async def test_geo_location_no_pool(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """No matching pool -> no geo_location entity."""
    # Return a pool with no matching device ID
    mock_pool_data["devices"] = [{"id": 9999, "nickname": "Other"}]
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("geo_location")
    poolcop_states = [s for s in states if s.attributes.get("source") == "poolcop"]
    assert len(poolcop_states) == 0


async def test_geo_location_extra_attrs(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Extra attributes include timezone, nickname, alarm_count."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("geo_location")
    poolcop_states = [s for s in states if s.attributes.get("source") == "poolcop"]
    assert len(poolcop_states) == 1

    state = poolcop_states[0]
    assert state.attributes.get("timezone") == "Europe/Amsterdam"
    assert state.attributes.get("nickname") == "Striker"
    assert state.attributes.get("alarm_count") == 1  # PressureLowPump1
    assert state.attributes.get("icon") == "mdi:pool"


async def test_geo_location_attention_mode_no_alarms(
    hass: HomeAssistant, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Attention mode with no alarms -> entity hidden from map."""
    mock_device_data["state"]["alarms"] = []
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": MOCK_API_KEY, "pump_speeds": 3},
        options={
            CONF_FLOW_RATE_1: 10.0,
            CONF_FLOW_RATE_2: 15.0,
            CONF_FLOW_RATE_3: 20.0,
            CONF_MAP_MODE: MAP_MODE_ATTENTION,
        },
        unique_id="2478",
        entry_id="test_attention_no_alarms",
        version=2,
    )
    await _setup_integration(hass, entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("geo_location")
    poolcop_states = [s for s in states if s.attributes.get("source") == "poolcop"]
    assert len(poolcop_states) == 1
    state = poolcop_states[0]
    assert state.attributes.get("latitude") is None
    assert state.attributes.get("longitude") is None


async def test_geo_location_attention_mode_with_alarms(
    hass: HomeAssistant, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Attention mode with alarms -> entity visible."""
    # mock_device_data already has alarms
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": MOCK_API_KEY, "pump_speeds": 3},
        options={
            CONF_FLOW_RATE_1: 10.0,
            CONF_FLOW_RATE_2: 15.0,
            CONF_FLOW_RATE_3: 20.0,
            CONF_MAP_MODE: MAP_MODE_ATTENTION,
        },
        unique_id="2478",
        entry_id="test_attention_with_alarms",
        version=2,
    )
    await _setup_integration(hass, entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("geo_location")
    poolcop_states = [s for s in states if s.attributes.get("source") == "poolcop"]
    assert len(poolcop_states) == 1
    state = poolcop_states[0]
    assert state.attributes.get("latitude") == 52.165958
    assert state.attributes.get("longitude") == 6.038603
