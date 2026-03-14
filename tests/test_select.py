"""Test PoolCop select platform."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import DOMAIN


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


async def test_valve_position_setup(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Entity exists with correct options."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("select.test_pool_valve_position")
    assert state is not None
    assert "Filter" in state.attributes.get("options", [])
    assert "Backwash" in state.attributes.get("options", [])


async def test_valve_position_current(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """valve=1 → 'Waste'."""
    # mock_poolcop_data has valveposition=1
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("select.test_pool_valve_position")
    assert state is not None
    assert state.state == "Waste"


async def test_valve_position_set(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """select 'Backwash' → set_valve_position(3)."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test_pool_valve_position", "option": "Backwash"},
        blocking=True,
    )
    mock_poolcop.set_valve_position.assert_called_once_with(3)


async def test_pump_speed_options_3_speed(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """nb_speed=3 → ['0','1','2','3']."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("select.test_pool_pump_speed")
    assert state is not None
    assert state.attributes.get("options") == ["0", "1", "2", "3"]


async def test_pump_speed_current(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """speed=2 → '2'."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("select.test_pool_pump_speed")
    assert state is not None
    assert state.state == "2"


async def test_pump_speed_set(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """select '3' → set_pump_speed(3)."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test_pool_pump_speed", "option": "3"},
        blocking=True,
    )
    mock_poolcop.set_pump_speed.assert_called_once_with(3)


async def test_pump_speed_invalid_value(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Non-numeric pump speed → ValueError logged, no crash (lines 44-45)."""
    from custom_components.poolcop.select import _async_set_pump_speed

    coordinator = await _setup_integration(
        hass, mock_config_entry, mock_poolcop, mock_poolcop_data
    )
    # Should not raise — logs error
    await _async_set_pump_speed(coordinator, "not_a_number")
    mock_poolcop.set_pump_speed.assert_not_called()


async def test_pump_speed_non_int_pumpspeed(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """pumpspeed is not an int → current_option=None (line 57)."""
    mock_poolcop_data["PoolCop"]["status"]["pumpspeed"] = "bad"
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("select.test_pool_pump_speed")
    assert state is not None
    assert state.state == "unknown"


async def test_pump_speed_fallback_pump_type_3(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """nb_speed missing, pump_type=3 → 4 options (line 72)."""
    del mock_poolcop_data["PoolCop"]["settings"]["pump"]["nb_speed"]
    mock_poolcop_data["PoolCop"]["conf"]["pump_type"] = 3
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("select.test_pool_pump_speed")
    assert state is not None
    assert state.attributes.get("options") == ["0", "1", "2", "3"]


async def test_pump_speed_fallback_pump_type_2(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """nb_speed missing, pump_type=2 → 3 options (line 74)."""
    del mock_poolcop_data["PoolCop"]["settings"]["pump"]["nb_speed"]
    mock_poolcop_data["PoolCop"]["conf"]["pump_type"] = 2
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("select.test_pool_pump_speed")
    assert state is not None
    assert state.attributes.get("options") == ["0", "1", "2"]


async def test_pump_speed_fallback_pump_type_1(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """nb_speed missing, pump_type=1 → 2 options (line 76)."""
    del mock_poolcop_data["PoolCop"]["settings"]["pump"]["nb_speed"]
    mock_poolcop_data["PoolCop"]["conf"]["pump_type"] = 1
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("select.test_pool_pump_speed")
    assert state is not None
    assert state.attributes.get("options") == ["0", "1"]


async def test_valve_position_unknown_value(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Unknown valve position value → None (line 106)."""
    mock_poolcop_data["PoolCop"]["status"]["valveposition"] = 99
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("select.test_pool_valve_position")
    assert state is not None
    assert state.state == "unknown"
