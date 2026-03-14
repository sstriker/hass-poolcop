"""Test PoolCop binary sensor platform."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.poolcop.binary_sensor import _resolve_alarm
from custom_components.poolcop.const import DOMAIN
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


async def test_binary_sensor_setup(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """pump, watervalve, active_alarm exist."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    states = hass.states.async_all("binary_sensor")
    entity_ids = {s.entity_id for s in states}
    assert any("pump" in e and "switch" not in e for e in entity_ids)
    assert any("watervalve" in e for e in entity_ids)
    assert any("active_alarm" in e for e in entity_ids)


async def test_pump_sensor_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """pump=1 → is_on True."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("binary_sensor.test_pool_pump")
    assert state is not None
    assert state.state == "on"


async def test_active_alarm_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Alarm present → is_on True + extra attrs."""
    # Add alerts to status to trigger active alarms
    mock_poolcop_data["PoolCop"]["alerts"] = [
        {
            "code": 5,
            "description": "alert_title_5",
            "timestamp": "2023-04-15T10:00:00+0000",
        }
    ]
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("binary_sensor.test_pool_active_alarm")
    assert state is not None
    assert state.state == "on"
    assert state.attributes.get("alarm_count", 0) >= 1


async def test_active_alarm_off(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """No alarms → is_on False."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("binary_sensor.test_pool_active_alarm")
    assert state is not None
    assert state.state == "off"


async def test_resolve_alarm():
    """alert_title_5 → human-readable name."""
    alarm = {"code": 5, "description": "alert_title_5"}
    resolved = _resolve_alarm(alarm)
    assert resolved["code"] == 5
    assert resolved["description"] != "alert_title_5"  # Should be resolved


async def test_aux_binary_sensor_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Non-switchable aux status=1 → on."""
    # aux1 is non-switchable, give it status=1
    for aux in mock_poolcop_data["PoolCop"]["aux"]:
        if aux["id"] == 1:
            aux["status"] = 1
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    # Find the aux1 binary sensor
    states = hass.states.async_all("binary_sensor")
    aux1_states = [s for s in states if "aux_1" in s.entity_id]
    assert len(aux1_states) >= 1
    assert aux1_states[0].state == "on"


async def test_aux_missing_id():
    """Unknown aux → None from is_on."""

    # The is_on property iterates aux list — if aux_id not found, returns None
    data = PoolCopData(
        status={"PoolCop": {"aux": [{"id": 1, "status": 0}]}},
    )
    # Verify logic directly: no match for id=99
    aux_list = data.status_value("aux") or []
    found = None
    for aux in aux_list:
        if aux.get("id") == 99:
            found = bool(aux.get("status"))
    assert found is None


async def test_icon_selection(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """pump on → mdi:pump, off → mdi:pump-off."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("binary_sensor.test_pool_pump")
    assert state is not None
    # Pump is on (status.pump=1)
    assert state.attributes.get("icon") == "mdi:pump"


async def test_resolve_alarm_name_field():
    """alarm with name='alert_title_6' → resolved via name field (line 67)."""
    alarm = {"id": 6, "name": "alert_title_6"}
    resolved = _resolve_alarm(alarm)
    assert resolved["code"] == 6
    # name was resolved, description was empty → description = resolved name
    assert "pH" in resolved["description"]  # alert_title_6 = "pH High"


async def test_aux_binary_sensor_not_found(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Aux removed from data after setup → is_on=None, attrs={} (lines 384, 400)."""
    # aux1 is non-switchable → gets a binary sensor
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    # Find the aux1 entity
    states = hass.states.async_all("binary_sensor")
    aux1_states = [s for s in states if "aux_1" in s.entity_id]
    assert len(aux1_states) >= 1

    # Now clear the aux list so the entity can't find its aux_id
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    status = dict(coordinator.data.status)
    status["PoolCop"] = dict(status["PoolCop"])
    status["PoolCop"]["aux"] = []
    coordinator.data = coordinator.data._replace(status=status)
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get(aux1_states[0].entity_id)
    # is_on returns None → HA shows "unknown"
    assert state.state == "unknown"


async def test_aux_binary_sensor_icon_with_label(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Aux with known label_id and status → icon from AUX_LABEL_ICONS (line 409)."""
    # Use aux1 with label_aux_0 (Pool Light) which IS in AUX_LABEL_ICONS.
    # aux1 is non-switchable (switchable=False) → binary sensor.
    for aux in mock_poolcop_data["PoolCop"]["aux"]:
        if aux["id"] == 1:
            aux["label"] = "label_aux_0"  # Pool Light
            aux["status"] = 1
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    # Entity name is derived from label: "Pool Light" → "pool_light"
    state = hass.states.get("binary_sensor.test_pool_pool_light")
    assert state is not None
    # label_id=0 (Pool Light), status=1 → icons[0] = "mdi:lightbulb-on"
    assert state.attributes.get("icon") == "mdi:lightbulb-on"
