"""Test PoolCop switch platform."""

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


async def test_pump_switch_state_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """status.pump=1 → state 'on'."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("switch.poolcop_test_poolcop_id_pump")
    assert state is not None
    assert state.state == "on"


async def test_pump_switch_turn_off(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Calls toggle_pump(turn_on=False)."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.poolcop_test_poolcop_id_pump"}, blocking=True
    )
    mock_poolcop.toggle_pump.assert_called_once()


async def test_pump_switch_turn_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Calls toggle_pump(turn_on=True) — pump already on so idempotent."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.poolcop_test_poolcop_id_pump"}, blocking=True
    )
    # Pump is already on (status.pump==1), so toggle_pump should NOT be called
    mock_poolcop.toggle_pump.assert_not_called()


async def test_aux_switch_is_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """aux4 status=1 → is_on True."""
    # aux4 is switchable, add status=1
    for aux in mock_poolcop_data["PoolCop"]["aux"]:
        if aux["id"] == 4:
            aux["status"] = 1
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("switch.poolcop_test_poolcop_id_transfer_pump")
    assert state is not None
    assert state.state == "on"


async def test_aux_switch_turn_on_when_off(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Calls toggle_auxiliary(4) when aux is off."""
    for aux in mock_poolcop_data["PoolCop"]["aux"]:
        if aux["id"] == 4:
            aux["status"] = 0
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.poolcop_test_poolcop_id_transfer_pump"},
        blocking=True,
    )
    mock_poolcop.toggle_auxiliary.assert_called_once_with(4)


async def test_aux_switch_idempotent(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Already on → no toggle call."""
    for aux in mock_poolcop_data["PoolCop"]["aux"]:
        if aux["id"] == 4:
            aux["status"] = 1
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.poolcop_test_poolcop_id_transfer_pump"},
        blocking=True,
    )
    mock_poolcop.toggle_auxiliary.assert_not_called()


async def test_aux_switch_is_on_returns_none_when_not_found(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """is_on returns None when aux id not found in aux list."""
    for aux in mock_poolcop_data["PoolCop"]["aux"]:
        if aux["id"] == 4:
            aux["status"] = 1
    coordinator = await _setup_integration(
        hass, mock_config_entry, mock_poolcop, mock_poolcop_data
    )

    # Remove aux 4 from the data so is_on cannot find it
    from custom_components.poolcop.coordinator import PoolCopData

    modified_data = dict(mock_poolcop_data)
    modified_data["PoolCop"] = dict(modified_data["PoolCop"])
    modified_data["PoolCop"]["aux"] = [
        a for a in modified_data["PoolCop"]["aux"] if a["id"] != 4
    ]
    coordinator.data = PoolCopData(status=modified_data)
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("switch.poolcop_test_poolcop_id_transfer_pump")
    assert state is not None
    # When is_on returns None, HA shows state as unknown
    assert state.state == "unknown"


async def test_aux_switch_extra_state_attributes_not_found(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """extra_state_attributes returns {} when aux not found."""
    for aux in mock_poolcop_data["PoolCop"]["aux"]:
        if aux["id"] == 4:
            aux["status"] = 0
    coordinator = await _setup_integration(
        hass, mock_config_entry, mock_poolcop, mock_poolcop_data
    )

    # Remove aux 4 from data
    from custom_components.poolcop.coordinator import PoolCopData

    modified_data = dict(mock_poolcop_data)
    modified_data["PoolCop"] = dict(modified_data["PoolCop"])
    modified_data["PoolCop"]["aux"] = [
        a for a in modified_data["PoolCop"]["aux"] if a["id"] != 4
    ]
    coordinator.data = PoolCopData(status=modified_data)
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("switch.poolcop_test_poolcop_id_transfer_pump")
    assert state is not None
    # No label, slave, or days attributes when aux not found
    assert "label" not in state.attributes
    assert "slave" not in state.attributes


async def test_aux_switch_icon_no_label_match(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """icon returns None when label_id has no icon mapping."""
    # Change aux 4's label to one without an icon mapping (label_aux_15 = "Available")
    for aux in mock_poolcop_data["PoolCop"]["aux"]:
        if aux["id"] == 4:
            aux["label"] = "label_aux_15"
            aux["status"] = 0
            aux["switchable"] = True
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    state = hass.states.get("switch.poolcop_test_poolcop_id_available")
    assert state is not None
    # label_id 15 is not in AUX_LABEL_ICONS, so icon should not be set
    assert "icon" not in state.attributes


async def test_aux_switch_turn_off_when_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """turn_off when aux is on calls toggle_auxiliary."""
    for aux in mock_poolcop_data["PoolCop"]["aux"]:
        if aux["id"] == 4:
            aux["status"] = 1
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.poolcop_test_poolcop_id_transfer_pump"},
        blocking=True,
    )
    mock_poolcop.toggle_auxiliary.assert_called_once_with(4)


async def test_aux_switch_turn_off_when_already_off(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """turn_off when already off does not call toggle_auxiliary."""
    for aux in mock_poolcop_data["PoolCop"]["aux"]:
        if aux["id"] == 4:
            aux["status"] = 0
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.poolcop_test_poolcop_id_transfer_pump"},
        blocking=True,
    )
    mock_poolcop.toggle_auxiliary.assert_not_called()
