"""Test PoolCop binary sensor platform."""

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


async def test_binary_sensor_setup(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Core binary sensors exist: pump, active_alarm."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("binary_sensor")
    entity_ids = {s.entity_id for s in states}
    assert any("pump" in e for e in entity_ids)
    assert any("active_alarm" in e for e in entity_ids)


async def test_pump_binary_sensor_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Pump is on (pumpState=True) -> state 'on'."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if s.entity_id.endswith("_pump")]
    assert len(states) >= 1
    assert states[0].state == "on"


async def test_active_alarm_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Alarm present -> active_alarm is on."""
    # mock_device_data already has alarms: ["PressureLowPump1"]
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if "active_alarm" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "on"
    assert states[0].attributes.get("alarm_count", 0) >= 1


async def test_active_alarm_off(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """No alarms -> active_alarm is off."""
    mock_device_data["state"]["alarms"] = []
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if "active_alarm" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "off"


async def test_pump_icon(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Pump on -> mdi:pump icon."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if s.entity_id.endswith("_pump")]
    assert len(states) >= 1
    assert states[0].attributes.get("icon") == "mdi:pump"


async def test_aux_binary_sensor_reserved(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Reserved aux creates a binary sensor, not a switch."""
    from copy import deepcopy

    # Add a reserved aux (label_aux_16 = Waste Valve, is_reserved=True)
    mock_device_data["settings"]["auxs"]["None"]["Aux5"] = {
        "id": "Aux5",
        "auxChannel": 5,
        "module": "None",
        "moduleId": 0,
        "label": "label_aux_16",
        "friendlyName": "Waste",
        "status": False,
        "isSlave": False,
        "slavedTo": "NotSlave",
        "mode": "Manual",
        "isReserved": True,
        "isHeating": False,
        "daysOfWeek": ["Monday", "Wednesday"],
        "timers": [{"id": 1, "timeOn": "00:00:00", "timeOff": "00:00:00"}],
    }
    mock_device_data["state"]["auxiliaries"]["None"]["Aux5"] = True

    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("binary_sensor")
    aux_bs = [s for s in states if "aux_5" in s.entity_id]
    assert len(aux_bs) >= 1
    state = aux_bs[0]
    assert state.state == "on"
    # Reserved + label 16 (Waste Valve) → OPENING device class, diagnostic entity
    assert state.attributes.get("device_class") == "opening"
    # Valve icon
    assert state.attributes.get("icon") == "mdi:valve-open"
    # Extra attrs from reserved aux
    assert state.attributes.get("days") == ["Monday", "Wednesday"]
    assert state.attributes.get("label") == "label_aux_16"


async def test_aux_binary_sensor_slave(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Slaved aux creates a binary sensor with slave attribute."""
    mock_device_data["settings"]["auxs"]["None"]["Aux6"] = {
        "id": "Aux6",
        "auxChannel": 6,
        "module": "None",
        "moduleId": 0,
        "label": "label_aux_17",
        "friendlyName": "Speed",
        "status": False,
        "isSlave": True,
        "slavedTo": "Aux1",
        "mode": "Manual",
        "isReserved": False,
        "isHeating": False,
        "daysOfWeek": [],
        "timers": [],
    }
    mock_device_data["state"]["auxiliaries"]["None"]["Aux6"] = False

    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("binary_sensor")
    aux_bs = [s for s in states if "aux_6" in s.entity_id]
    assert len(aux_bs) >= 1
    state = aux_bs[0]
    assert state.state == "off"
    # Label 17 (Speed Control) → POWER device class, fixed-function → diagnostic
    assert state.attributes.get("device_class") == "power"
    # Slave attr
    assert state.attributes.get("slave") == "Aux1"
    # Label 17 (Speed Control) → uses AUX_LABEL_ICONS
    assert "icon" in state.attributes


async def test_aux_binary_sensor_no_module(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Aux binary sensor with unknown module returns None for is_on."""
    mock_device_data["settings"]["auxs"]["None"]["Aux3"] = {
        "id": "Aux3",
        "auxChannel": 3,
        "module": "Missing",
        "moduleId": 0,
        "label": "",
        "friendlyName": "",
        "status": False,
        "isSlave": False,
        "slavedTo": "NotSlave",
        "mode": "Manual",
        "isReserved": True,
        "isHeating": False,
        "daysOfWeek": [],
        "timers": [],
    }

    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("binary_sensor")
    aux_bs = [s for s in states if "aux_3" in s.entity_id]
    assert len(aux_bs) >= 1
    # Default fallback icon when no label_id and no special device class
    assert aux_bs[0].attributes.get("icon") in ("mdi:toggle-switch-off", "mdi:toggle-switch")


async def test_aux_binary_sensor_with_icon_label(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Reserved aux with known icon label shows correct on/off icons."""
    mock_device_data["settings"]["auxs"]["None"]["Aux2"] = {
        "id": "Aux2",
        "auxChannel": 2,
        "module": "None",
        "moduleId": 0,
        "label": "label_aux_0",
        "friendlyName": "My Pool Light",
        "status": False,
        "isSlave": False,
        "slavedTo": "NotSlave",
        "mode": "Manual",
        "isReserved": True,
        "isHeating": False,
        "daysOfWeek": [],
        "timers": [],
    }
    mock_device_data["state"]["auxiliaries"]["None"]["Aux2"] = True

    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("binary_sensor")
    aux_bs = [s for s in states if "pool_light" in s.entity_id]
    assert len(aux_bs) >= 1
    # label_aux_0 = Pool Light -> icon should be mdi:lightbulb-on (is_on=True)
    assert aux_bs[0].attributes.get("icon") == "mdi:lightbulb-on"
    assert aux_bs[0].attributes.get("friendly_name") is not None


async def test_aux_binary_sensor_attrs_no_match(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Aux binary sensor returns empty attrs when aux no longer in settings."""
    mock_device_data["settings"]["auxs"]["None"]["Aux1"] = {
        "id": "Aux1",
        "auxChannel": 1,
        "module": "None",
        "moduleId": 0,
        "label": "",
        "friendlyName": "",
        "status": False,
        "isSlave": False,
        "slavedTo": "NotSlave",
        "mode": "",
        "isReserved": True,
        "isHeating": False,
        "daysOfWeek": [],
        "timers": [],
    }
    mock_device_data["state"]["auxiliaries"]["None"]["Aux1"] = False

    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    # Clear the settings so extra_state_attributes can't find matching aux
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    coordinator.data.device.settings.auxs.clear()

    # Force the entity to re-write its state
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    states = hass.states.async_all("binary_sensor")
    aux_bs = [s for s in states if "aux_1" in s.entity_id]
    assert len(aux_bs) >= 1
    # Attrs should be empty
    assert "slave" not in aux_bs[0].attributes
    assert "label" not in aux_bs[0].attributes


async def test_alarm_attrs_with_alert_title(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Alarm with alert_title_ prefix resolves to display name."""
    mock_device_data["state"]["alarms"] = ["alert_title_1", "PressureLow"]
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if "active_alarm" in s.entity_id]
    assert len(states) >= 1
    attrs = states[0].attributes
    assert attrs["alarm_count"] == 2
    alarms = attrs["alarms"]
    assert alarms[0]["description"] == "Freezing Risk"
    assert alarms[1]["code"] == "PressureLow"


async def test_alarm_attrs_empty(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """No alarms returns empty attrs."""
    mock_device_data["state"]["alarms"] = []
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if "active_alarm" in s.entity_id]
    assert len(states) >= 1
    assert states[0].attributes["alarm_count"] == 0


async def test_extra_state_attributes_none_for_non_alarm(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Non-alarm binary sensors return None for extra_state_attributes."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if s.entity_id.endswith("_pump")]
    assert len(states) >= 1
    # Pump binary sensor has no extra_attrs_fn, so alarm_count should not be present
    assert "alarm_count" not in states[0].attributes


async def test_pool_cover_binary_sensor_off(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Pool cover closed (isOpen=False) -> off state."""
    # Default mock: hasPoolCover=True, isOpen=False
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if s.entity_id.endswith("_pool_cover")]
    assert len(states) >= 1
    assert states[0].state == "off"
    assert states[0].attributes.get("device_class") == "opening"
    assert states[0].attributes.get("icon") == "mdi:window-shutter"


async def test_pool_cover_binary_sensor_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Pool cover open (isOpen=True) -> on state with extra attrs."""
    mock_device_data["state"]["poolCover"]["isOpen"] = True
    mock_device_data["state"]["poolCover"]["isOpening"] = True
    mock_device_data["state"]["poolCover"]["isStopped"] = False
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if s.entity_id.endswith("_pool_cover")]
    assert len(states) >= 1
    assert states[0].state == "on"
    assert states[0].attributes.get("icon") == "mdi:window-shutter-open"
    assert states[0].attributes["is_opening"] is True
    assert states[0].attributes["is_stopped"] is False
    assert states[0].attributes["controllable"] is False


async def test_pool_cover_not_installed(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Pool cover not installed -> no state entity (equip flag still exists)."""
    mock_device_data["equipmentsInfo"]["hasPoolCover"] = False
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if s.entity_id.endswith("_pool_cover")]
    assert len(states) == 0


async def test_jet_stream_binary_sensor(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Jet stream running when installed."""
    mock_device_data["equipmentsInfo"]["hasJetStream"] = True
    mock_device_data["state"]["jetStream"]["isRunning"] = True
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if s.entity_id.endswith("_jet_stream")]
    assert len(states) >= 1
    assert states[0].state == "on"


async def test_jet_stream_not_installed(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Jet stream not installed -> no state entity (equip flag still exists)."""
    # Default mock: hasJetStream=False
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if s.entity_id.endswith("_jet_stream")]
    assert len(states) == 0


async def test_input_1_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Input 1 is True in mock -> on state."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if "input_1" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "on"
    assert states[0].attributes.get("icon") == "mdi:electric-switch-closed"


async def test_input_2_off(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Input 2 is False in mock -> off state."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if "input_2" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "off"
    assert states[0].attributes.get("icon") == "mdi:electric-switch"


async def test_ph_auto_adjust_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """pH auto-adjust enabled -> on state."""
    # Default mock: autoAdjust = True, hasPHSensor = True
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if "ph_auto_adjust" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "on"


async def test_ph_auto_adjust_off(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """pH auto-adjust disabled -> off state."""
    mock_device_data["settings"]["pH"]["autoAdjust"] = False
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if "ph_auto_adjust" in s.entity_id]
    assert len(states) >= 1
    assert states[0].state == "off"


async def test_ph_auto_adjust_not_installed(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """pH auto-adjust gated by hasPHSensor."""
    mock_device_data["equipmentsInfo"]["hasPHSensor"] = False
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = [s for s in hass.states.async_all("binary_sensor") if "ph_auto_adjust" in s.entity_id]
    assert len(states) == 0


async def test_equipment_flags_always_created(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Equipment inventory flags are always created regardless of equipment state."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("binary_sensor")
    entity_ids = {s.entity_id for s in states}

    assert any("fac_sensor_installed" in e for e in entity_ids)
    assert any("salt_sensor_installed" in e for e in entity_ids)
    assert any("flow_meter_installed" in e for e in entity_ids)
    assert any("energy_meter_installed" in e for e in entity_ids)
    assert any("pool_cover_installed" in e for e in entity_ids)
    assert any("jet_stream_installed" in e for e in entity_ids)


async def test_equipment_flags_values(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Equipment flags reflect actual equipment state."""
    # Default mock: hasPoolCover=True, hasJetStream=False, etc.
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    states = hass.states.async_all("binary_sensor")

    pool_cover = [s for s in states if "pool_cover_installed" in s.entity_id][0]
    assert pool_cover.state == "on"

    jet_stream = [s for s in states if "jet_stream_installed" in s.entity_id][0]
    assert jet_stream.state == "off"

    fac = [s for s in states if "fac_sensor_installed" in s.entity_id][0]
    assert fac.state == "off"
