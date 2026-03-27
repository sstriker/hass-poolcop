"""Test PoolCop geo location platform."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import CONF_MAP_MODE, DOMAIN, MAP_MODE_ATTENTION
from custom_components.poolcop.coordinator import PoolCopData


async def _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data):
    """Set up the integration and return the coordinator."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return hass.data[DOMAIN][mock_config_entry.entry_id]


async def test_geo_location_with_coords(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """lat/lon → geo_location entity with source and distance."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    states = hass.states.async_all("geo_location")
    poolcop_states = [s for s in states if s.attributes.get("source") == "poolcop"]
    assert len(poolcop_states) == 1

    state = poolcop_states[0]
    assert state.attributes.get("latitude") == 48.86
    assert state.attributes.get("longitude") == 2.35
    # State is distance (float) — should be a number
    assert state.state is not None


async def test_geo_location_no_coords(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """No coords → no entity."""
    del mock_poolcop_data["Pool"]
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    states = hass.states.async_all("geo_location")
    poolcop_states = [s for s in states if s.attributes.get("source") == "poolcop"]
    assert len(poolcop_states) == 0


async def test_geo_location_extra_attrs(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Extra attributes include timezone, nickname, alarm_count."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    states = hass.states.async_all("geo_location")
    poolcop_states = [s for s in states if s.attributes.get("source") == "poolcop"]
    assert len(poolcop_states) == 1

    state = poolcop_states[0]
    assert state.attributes.get("timezone") == "Europe/Amsterdam"
    assert state.attributes.get("nickname") == "Test Pool"
    assert state.attributes.get("alarm_count") == 0
    assert state.attributes.get("icon") == "mdi:pool"


async def test_geo_location_non_dict_pool_data(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Non-dict Pool data skips entity creation."""
    mock_poolcop_data["Pool"] = "not a dict"
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    states = hass.states.async_all("geo_location")
    poolcop_states = [s for s in states if s.attributes.get("source") == "poolcop"]
    assert len(poolcop_states) == 0


async def test_geo_location_invalid_coords(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Non-numeric lat/lon skips entity creation."""
    mock_poolcop_data["Pool"]["latitude"] = "not-a-number"
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    states = hass.states.async_all("geo_location")
    poolcop_states = [s for s in states if s.attributes.get("source") == "poolcop"]
    assert len(poolcop_states) == 0


async def test_geo_location_with_image(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Pool image URL sets entity_picture attribute."""
    mock_poolcop_data["Pool"]["image"] = "https://example.com/pool.jpg"
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    states = hass.states.async_all("geo_location")
    poolcop_states = [s for s in states if s.attributes.get("source") == "poolcop"]
    assert len(poolcop_states) == 1
    assert (
        poolcop_states[0].attributes.get("entity_picture")
        == "https://example.com/pool.jpg"
    )


async def test_geo_location_attention_mode_no_alarms(
    hass: HomeAssistant, mock_poolcop, mock_poolcop_data
):
    """Attention mode with no alarms → entity has no coordinates (hidden from map)."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.poolcop.const import CONF_FLOW_RATE_1, CONF_FLOW_RATE_2, CONF_FLOW_RATE_3

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "test", "pump_speeds": 3},
        options={
            CONF_FLOW_RATE_1: 10.0,
            CONF_FLOW_RATE_2: 15.0,
            CONF_FLOW_RATE_3: 20.0,
            CONF_MAP_MODE: MAP_MODE_ATTENTION,
        },
        unique_id="test-poolcop-id",
        entry_id="test_attention_no_alarms",
        version=2,
    )
    await _setup_integration(hass, entry, mock_poolcop, mock_poolcop_data)

    states = hass.states.async_all("geo_location")
    poolcop_states = [s for s in states if s.attributes.get("source") == "poolcop"]
    assert len(poolcop_states) == 1
    state = poolcop_states[0]
    # No alarms → no coordinates → hidden from map
    assert state.attributes.get("latitude") is None
    assert state.attributes.get("longitude") is None
    assert state.state == "unknown"


async def test_geo_location_attention_mode_with_alarms(
    hass: HomeAssistant, mock_poolcop, mock_poolcop_data
):
    """Attention mode with active alarms → entity visible with coordinates."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.poolcop.const import CONF_FLOW_RATE_1, CONF_FLOW_RATE_2, CONF_FLOW_RATE_3

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "test", "pump_speeds": 3},
        options={
            CONF_FLOW_RATE_1: 10.0,
            CONF_FLOW_RATE_2: 15.0,
            CONF_FLOW_RATE_3: 20.0,
            CONF_MAP_MODE: MAP_MODE_ATTENTION,
        },
        unique_id="test-poolcop-id",
        entry_id="test_attention_with_alarms",
        version=2,
    )
    mock_poolcop_data["PoolCop"]["alarms"] = {"count": 2}
    await _setup_integration(hass, entry, mock_poolcop, mock_poolcop_data)

    states = hass.states.async_all("geo_location")
    poolcop_states = [s for s in states if s.attributes.get("source") == "poolcop"]
    assert len(poolcop_states) == 1
    state = poolcop_states[0]
    assert state.attributes.get("latitude") == 48.86
    assert state.attributes.get("longitude") == 2.35
    assert state.state is not None


async def test_geo_location_attrs_non_dict_at_runtime(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """extra_state_attributes returns {} when Pool data becomes non-dict at runtime."""
    coordinator = await _setup_integration(
        hass, mock_config_entry, mock_poolcop, mock_poolcop_data
    )

    states = hass.states.async_all("geo_location")
    poolcop_states = [s for s in states if s.attributes.get("source") == "poolcop"]
    assert len(poolcop_states) == 1

    # Change Pool data to non-dict and trigger update
    modified_data = dict(mock_poolcop_data)
    modified_data["Pool"] = "not a dict"
    coordinator.data = PoolCopData(status=modified_data)
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    states = hass.states.async_all("geo_location")
    poolcop_states = [s for s in states if s.attributes.get("source") == "poolcop"]
    assert len(poolcop_states) == 1
    state = poolcop_states[0]
    assert "timezone" not in state.attributes
    assert "nickname" not in state.attributes
