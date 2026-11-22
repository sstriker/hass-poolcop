"""Test PoolCop select platform."""

from unittest.mock import patch

from aiopoolcop import Pool, PoolCopDevice
from homeassistant.core import HomeAssistant


async def _setup_integration(
    hass, mock_config_entry, mock_poolcop_api, device_data, pool_data
):
    """Set up the integration and return the coordinator."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(pool_data)]
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.helpers.PoolCopClientAPI",
        return_value=mock_poolcop_api,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry.runtime_data


async def test_valve_position_setup(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Valve position entity exists with correct options."""
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [
        s for s in hass.states.async_all("select") if "valve_position" in s.entity_id
    ]
    assert len(states) >= 1
    state = states[0]
    assert "filter" in state.attributes.get("options", [])
    assert "backwash" in state.attributes.get("options", [])


async def test_valve_position_current(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Valve position 'Filter' from mock data."""
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [
        s for s in hass.states.async_all("select") if "valve_position" in s.entity_id
    ]
    assert len(states) >= 1
    assert states[0].state == "filter"


async def test_valve_position_set(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Selecting 'Backwash' calls set_valve_position."""
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    valve_select = next(
        s for s in hass.states.async_all("select") if "valve_position" in s.entity_id
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": valve_select.entity_id, "option": "backwash"},
        blocking=True,
    )
    mock_poolcop_api.set_valve_position.assert_called_once_with(2478, "Backwash")


async def test_pump_speed_options_3_speed(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """numberOfSpeeds=Speed3 -> options ['none', 'speed_1', 'speed_2', 'speed_3']."""
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [s for s in hass.states.async_all("select") if "pump_speed" in s.entity_id]
    assert len(states) >= 1
    assert states[0].attributes.get("options") == [
        "none",
        "speed_1",
        "speed_2",
        "speed_3",
    ]


async def test_pump_speed_current(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Current speed = Speed1."""
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [s for s in hass.states.async_all("select") if "pump_speed" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "speed_1"


async def test_pump_speed_set(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Selecting 'Speed3' calls set_pump_speed."""
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    speed_select = next(
        s for s in hass.states.async_all("select") if "pump_speed" in s.entity_id
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": speed_select.entity_id, "option": "speed_3"},
        blocking=True,
    )
    mock_poolcop_api.set_pump_speed.assert_called_once_with(2478, "Speed3")


async def test_pump_speed_no_pumps(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """No pumps -> speed options fall back to ['none', 'speed_1']."""
    mock_device_data["state"]["pumpsInfo"] = []
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [s for s in hass.states.async_all("select") if "pump_speed" in s.entity_id]
    assert len(states) >= 1
    assert states[0].attributes.get("options") == ["none", "speed_1"]


async def test_pump_speed_pump_off_shows_none(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Pump off -> current option is 'none'."""
    mock_device_data["state"]["pumpsInfo"][0]["pumpState"] = False
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [s for s in hass.states.async_all("select") if "pump_speed" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "none"


async def test_valve_position_no_pumps(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """No pumps -> valve position returns None."""
    mock_device_data["state"]["pumpsInfo"] = []
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [
        s for s in hass.states.async_all("select") if "valve_position" in s.entity_id
    ]
    assert len(states) >= 1
    assert states[0].state == "unknown"


async def test_forced_filtration_exists(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Forced filtration select entity exists with correct options."""
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [
        s for s in hass.states.async_all("select") if "forced_filtration" in s.entity_id
    ]
    assert len(states) >= 1
    options = states[0].attributes.get("options", [])
    assert options == ["not_forced", "forced_24h", "forced_48h", "forced_72h"]


async def test_forced_filtration_not_forced(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Timer filtration mode -> NotForced."""
    # Default mock: filtrationMode = "Timer"
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [
        s for s in hass.states.async_all("select") if "forced_filtration" in s.entity_id
    ]
    assert len(states) >= 1
    assert states[0].state == "not_forced"


async def test_forced_filtration_forced_24h(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Force24H filtration mode -> Forced24H."""
    mock_device_data["state"]["pumpsInfo"][0]["filtrationMode"] = "Forced24H"
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [
        s for s in hass.states.async_all("select") if "forced_filtration" in s.entity_id
    ]
    assert len(states) >= 1
    assert states[0].state == "forced_24h"


async def test_forced_filtration_set(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Setting forced filtration calls set_pump_forced."""
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    entity = next(
        s for s in hass.states.async_all("select") if "forced_filtration" in s.entity_id
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity.entity_id, "option": "forced_48h"},
        blocking=True,
    )
    mock_poolcop_api.set_pump_forced.assert_called_once_with(2478, "Forced48H")


async def test_forced_filtration_no_pumps(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """No pumps -> forced filtration unknown."""
    mock_device_data["state"]["pumpsInfo"] = []
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [
        s for s in hass.states.async_all("select") if "forced_filtration" in s.entity_id
    ]
    assert len(states) >= 1
    assert states[0].state == "unknown"


def _filtration_mode_entity_id(hass: HomeAssistant) -> str:
    return next(
        s.entity_id
        for s in hass.states.async_all("select")
        if s.entity_id.endswith("_filtration_mode")
    )


async def test_filtration_mode_select(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Filtration mode select shows the mode and sets it via filtrationtimer."""
    mock_device_data["state"]["pumpsInfo"][0]["filtrationMode"] = "EcoPlus"
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )
    entity_id = _filtration_mode_entity_id(hass)
    state = hass.states.get(entity_id)
    assert state.state == "eco_plus"
    assert state.attributes["options"] == [
        "stop",
        "timer",
        "eco_plus",
        "volume",
        "continuous",
        "mode_24h",
    ]

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "mode_24h"},
        blocking=True,
    )
    mock_poolcop_api.set_filtration_timer.assert_called_once_with(2478, "Mode24H")
    # Shown as requested until the device reports it
    assert hass.states.get(entity_id).state == "mode_24h"


async def test_filtration_mode_select_forced_is_unknown(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """While forced filtration overrides the mode the select has no option."""
    mock_device_data["state"]["pumpsInfo"][0]["filtrationMode"] = "Forced48H"
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )
    assert hass.states.get(_filtration_mode_entity_id(hass)).state == "unknown"


async def test_filtration_mode_select_no_pumps(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """No pumps -> unknown filtration mode."""
    mock_device_data["state"]["pumpsInfo"] = []
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )
    assert hass.states.get(_filtration_mode_entity_id(hass)).state == "unknown"


def test_option_key():
    """API values map to snake_case translation keys."""
    from custom_components.poolcop.select import option_key

    assert option_key("EcoPlus") == "eco_plus"
    assert option_key("Speed3") == "speed_3"
    assert option_key("Forced24H") == "forced_24h"
    assert option_key("NotForced") == "not_forced"
    assert option_key("None") == "none"
