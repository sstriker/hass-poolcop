"""Test PoolCop switch platform."""

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


async def test_pump_switch_state_on(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Pump is on -> switch state 'on'."""
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [s for s in hass.states.async_all("switch") if "pump" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "on"


async def test_pump_switch_turn_off(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Turning off calls set_pump(on=False)."""
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    pump_switch = next(
        s
        for s in hass.states.async_all("switch")
        if "pump" in s.entity_id and "aux" not in s.entity_id
    )
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": pump_switch.entity_id}, blocking=True
    )
    mock_poolcop_api.set_pump.assert_called_once_with(2478, on=False)


async def test_pump_switch_turn_on(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Turning on calls set_pump(on=True)."""
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    pump_switch = next(
        s
        for s in hass.states.async_all("switch")
        if "pump" in s.entity_id and "aux" not in s.entity_id
    )
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": pump_switch.entity_id}, blocking=True
    )
    mock_poolcop_api.set_pump.assert_called_once_with(2478, on=True)


async def test_aux_switch_exists(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Aux4 (not reserved, not slave) should create a switch."""
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [
        s for s in hass.states.async_all("switch") if "transfer_pump" in s.entity_id
    ]
    assert len(states) >= 1


async def test_aux_switch_turn_on(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Aux turn on calls set_auxiliary."""
    # Set aux state to off so turn_on will fire
    mock_device_data["state"]["auxiliaries"]["None"]["Aux4"] = False
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    aux_switch = next(
        s for s in hass.states.async_all("switch") if "transfer_pump" in s.entity_id
    )
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": aux_switch.entity_id}, blocking=True
    )
    mock_poolcop_api.set_auxiliary.assert_called_once_with(2478, "None", 4, on=True)


async def test_aux_switch_turn_off(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Aux turn off calls set_auxiliary when currently on."""
    # Set aux state to on so turn_off will fire
    mock_device_data["state"]["auxiliaries"]["None"]["Aux4"] = True
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    aux_switch = next(
        s for s in hass.states.async_all("switch") if "transfer_pump" in s.entity_id
    )
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": aux_switch.entity_id}, blocking=True
    )
    mock_poolcop_api.set_auxiliary.assert_called_once_with(2478, "None", 4, on=False)


async def test_aux_switch_command_shows_pending_state(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """The requested state shows until the device reports it (HTTP 202 delay)."""
    mock_device_data["state"]["auxiliaries"]["None"]["Aux4"] = False
    coordinator = await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    aux_switch = next(
        s for s in hass.states.async_all("switch") if "transfer_pump" in s.entity_id
    )
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": aux_switch.entity_id}, blocking=True
    )
    mock_poolcop_api.set_auxiliary.assert_called_once_with(2478, "None", 4, on=True)
    assert hass.states.get(aux_switch.entity_id).state == "on"

    # A refresh that still reports the old state keeps the requested state
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(aux_switch.entity_id).state == "on"

    # Once the device reports it, the pending state is cleared
    mock_device_data["state"]["auxiliaries"]["None"]["Aux4"] = True
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(mock_device_data)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator._pending == {}
    assert hass.states.get(aux_switch.entity_id).state == "on"


async def test_pump_switch_no_pumps(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Pump switch with no pumps info -> state None."""
    mock_device_data["state"]["pumpsInfo"] = []
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [
        s
        for s in hass.states.async_all("switch")
        if "pump" in s.entity_id and "aux" not in s.entity_id
    ]
    assert len(states) >= 1
    assert states[0].state == "unknown"


async def test_aux_switch_no_module_returns_none(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Aux switch with missing module in state returns None."""
    mock_device_data["state"]["auxiliaries"] = {}
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [
        s for s in hass.states.async_all("switch") if "transfer_pump" in s.entity_id
    ]
    assert len(states) >= 1
    assert states[0].state == "unknown"


async def test_aux_switch_extra_attrs_days(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Aux switch with days_of_week shows days attr."""
    mock_device_data["settings"]["auxs"]["None"]["Aux4"]["daysOfWeek"] = [
        "Monday",
        "Friday",
    ]
    mock_device_data["state"]["auxiliaries"]["None"]["Aux4"] = True
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [
        s for s in hass.states.async_all("switch") if "transfer_pump" in s.entity_id
    ]
    assert len(states) >= 1
    assert states[0].attributes.get("days") == ["Monday", "Friday"]
    assert states[0].attributes.get("label") == "TransferPump"
    assert states[0].attributes.get("mode") == "Manual"


async def test_aux_switch_uses_friendly_name(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """A friendly name set on the PoolCop names the switch."""
    mock_device_data["settings"]["auxs"]["None"]["Aux4"]["friendlyName"] = "Fountain"
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    state = hass.states.get("switch.poolcop_2478_fountain")
    assert state is not None
    assert state.attributes["label"] == "TransferPump"


async def test_aux_switch_icon_with_known_label(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Aux switch with known PoolLight (Pool Light) shows light icon."""
    mock_device_data["settings"]["auxs"]["None"]["Aux4"]["label"] = "PoolLight"
    mock_device_data["state"]["auxiliaries"]["None"]["Aux4"] = True
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [s for s in hass.states.async_all("switch") if "pool_light" in s.entity_id]
    assert len(states) >= 1
    assert states[0].attributes.get("icon") == "mdi:lightbulb-on"


async def test_aux_switch_icon_off_state(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Aux switch off with known label shows off icon."""
    mock_device_data["settings"]["auxs"]["None"]["Aux4"]["label"] = "PoolLight"
    mock_device_data["state"]["auxiliaries"]["None"]["Aux4"] = False
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [s for s in hass.states.async_all("switch") if "pool_light" in s.entity_id]
    assert len(states) >= 1
    assert states[0].attributes.get("icon") == "mdi:lightbulb-off"


async def test_jet_stream_switch_hidden_when_not_installed(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Jet stream switch should not be created when not installed."""
    mock_device_data["equipmentsInfo"]["hasJetStream"] = False
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [s for s in hass.states.async_all("switch") if "jet_stream" in s.entity_id]
    assert len(states) == 0


async def test_jet_stream_switch_on(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Jet stream switch on when installed and running."""
    mock_device_data["equipmentsInfo"]["hasJetStream"] = True
    mock_device_data["state"]["jetStream"]["installed"] = True
    mock_device_data["state"]["jetStream"]["isRunning"] = True
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    states = [s for s in hass.states.async_all("switch") if "jet_stream" in s.entity_id]
    assert len(states) == 1
    assert states[0].state == "on"


async def test_jet_stream_switch_turn_on(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Turning jet stream on calls set_jet_stream."""
    mock_device_data["equipmentsInfo"]["hasJetStream"] = True
    mock_device_data["state"]["jetStream"]["installed"] = True
    mock_device_data["state"]["jetStream"]["isRunning"] = False
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    js_switch = next(
        s for s in hass.states.async_all("switch") if "jet_stream" in s.entity_id
    )
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": js_switch.entity_id}, blocking=True
    )
    mock_poolcop_api.set_jet_stream.assert_called_once_with(2478, on=True)


async def test_jet_stream_switch_turn_off(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Turning jet stream off calls set_jet_stream."""
    mock_device_data["equipmentsInfo"]["hasJetStream"] = True
    mock_device_data["state"]["jetStream"]["installed"] = True
    mock_device_data["state"]["jetStream"]["isRunning"] = True
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    js_switch = next(
        s for s in hass.states.async_all("switch") if "jet_stream" in s.entity_id
    )
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": js_switch.entity_id}, blocking=True
    )
    mock_poolcop_api.set_jet_stream.assert_called_once_with(2478, on=False)


async def test_aux_switch_empty_attrs_fallback(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Aux switch whose settings no longer match returns empty attrs."""
    await _setup_integration(
        hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
    )

    # Remove the aux from settings after setup so extra_state_attributes misses
    coordinator = mock_config_entry.runtime_data
    coordinator.data.device.settings.auxs.clear()

    # Force the entity to re-write its state
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    states = [
        s for s in hass.states.async_all("switch") if "transfer_pump" in s.entity_id
    ]
    assert len(states) >= 1
    # Extra attrs should not have days/label/mode from the aux
    attrs = states[0].attributes
    assert "days" not in attrs
    assert "label" not in attrs
