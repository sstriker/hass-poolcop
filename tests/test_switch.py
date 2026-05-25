"""Test PoolCop switch platform."""

from unittest.mock import patch

from aiopoolcop import Pool, PoolCopDevice
from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import DOMAIN


async def _setup_integration(hass, mock_config_entry, mock_poolcop_api, device_data, pool_data):
    """Set up the integration and return the coordinator."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(pool_data)]
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.poolcop.PoolCopClientAPI", return_value=mock_poolcop_api):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return hass.data[DOMAIN][mock_config_entry.entry_id]


async def test_pump_switch_state_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Pump is on -> switch state 'on'."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("switch") if "pump" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "on"


async def test_pump_switch_turn_off(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Turning off calls set_pump(on=False)."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    pump_switch = [s for s in hass.states.async_all("switch") if "pump" in s.entity_id and "aux" not in s.entity_id][0]
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": pump_switch.entity_id}, blocking=True
    )
    mock_poolcop_api.set_pump.assert_called_once_with(2478, on=False)


async def test_pump_switch_turn_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Turning on calls set_pump(on=True)."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    pump_switch = [s for s in hass.states.async_all("switch") if "pump" in s.entity_id and "aux" not in s.entity_id][0]
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": pump_switch.entity_id}, blocking=True
    )
    mock_poolcop_api.set_pump.assert_called_once_with(2478, on=True)


async def test_aux_switch_exists(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Aux4 (not reserved, not slave) should create a switch."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("switch") if "transferpump" in s.entity_id]
    assert len(states) >= 1


async def test_aux_switch_turn_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Aux turn on calls set_auxiliary."""
    # Set aux state to off so turn_on will fire
    mock_device_data["state"]["auxiliaries"]["None"]["Aux4"] = False
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    aux_switch = [s for s in hass.states.async_all("switch") if "transferpump" in s.entity_id][0]
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": aux_switch.entity_id}, blocking=True
    )
    mock_poolcop_api.set_auxiliary.assert_called_once_with(2478, "None", 4, on=True)


async def test_aux_switch_turn_off(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Aux turn off calls set_auxiliary when currently on."""
    # Set aux state to on so turn_off will fire
    mock_device_data["state"]["auxiliaries"]["None"]["Aux4"] = True
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    aux_switch = [s for s in hass.states.async_all("switch") if "transferpump" in s.entity_id][0]
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": aux_switch.entity_id}, blocking=True
    )
    mock_poolcop_api.set_auxiliary.assert_called_once_with(2478, "None", 4, on=False)


async def test_aux_switch_idempotent_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Already on -> turn_on does not call API."""
    mock_device_data["state"]["auxiliaries"]["None"]["Aux4"] = True
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    aux_switch = [s for s in hass.states.async_all("switch") if "transferpump" in s.entity_id][0]
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": aux_switch.entity_id}, blocking=True
    )
    mock_poolcop_api.set_auxiliary.assert_not_called()


async def test_pump_switch_no_pumps(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Pump switch with no pumps info -> state None."""
    mock_device_data["state"]["pumpsInfo"] = []
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("switch") if "pump" in s.entity_id and "aux" not in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "unknown"


async def test_aux_switch_no_module_returns_none(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Aux switch with missing module in state returns None."""
    mock_device_data["state"]["auxiliaries"] = {}
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("switch") if "transferpump" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "unknown"


async def test_aux_switch_extra_attrs_days(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Aux switch with days_of_week shows days attr."""
    mock_device_data["settings"]["auxs"]["None"]["Aux4"]["daysOfWeek"] = ["Monday", "Friday"]
    mock_device_data["state"]["auxiliaries"]["None"]["Aux4"] = True
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("switch") if "transferpump" in s.entity_id]
    assert len(states) >= 1
    assert states[0].attributes.get("days") == ["Monday", "Friday"]
    assert states[0].attributes.get("label") == "TransferPump"
    assert states[0].attributes.get("friendly_name") is not None
    assert states[0].attributes.get("mode") == "Manual"


async def test_aux_switch_icon_with_known_label(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Aux switch with known label_aux_0 (Pool Light) shows light icon."""
    mock_device_data["settings"]["auxs"]["None"]["Aux4"]["label"] = "label_aux_0"
    mock_device_data["state"]["auxiliaries"]["None"]["Aux4"] = True
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("switch") if "pool_light" in s.entity_id]
    assert len(states) >= 1
    assert states[0].attributes.get("icon") == "mdi:lightbulb-on"


async def test_aux_switch_icon_off_state(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Aux switch off with known label shows off icon."""
    mock_device_data["settings"]["auxs"]["None"]["Aux4"]["label"] = "label_aux_0"
    mock_device_data["state"]["auxiliaries"]["None"]["Aux4"] = False
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("switch") if "pool_light" in s.entity_id]
    assert len(states) >= 1
    assert states[0].attributes.get("icon") == "mdi:lightbulb-off"


async def test_aux_switch_empty_attrs_fallback(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Aux switch whose settings no longer match returns empty attrs."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    # Remove the aux from settings after setup so extra_state_attributes misses
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    coordinator.data.device.settings.auxs.clear()

    # Force the entity to re-write its state
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    states = [s for s in hass.states.async_all("switch") if "transferpump" in s.entity_id]
    assert len(states) >= 1
    # Extra attrs should not have days/label/mode from the aux
    attrs = states[0].attributes
    assert "days" not in attrs
    assert "label" not in attrs
