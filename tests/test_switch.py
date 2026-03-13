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

    state = hass.states.get("switch.test_pool_pump")
    assert state is not None
    assert state.state == "on"


async def test_pump_switch_turn_off(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Calls toggle_pump(turn_on=False)."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.test_pool_pump"}, blocking=True
    )
    mock_poolcop.toggle_pump.assert_called_once()


async def test_pump_switch_turn_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Calls toggle_pump(turn_on=True) — pump already on so idempotent."""
    await _setup_integration(hass, mock_config_entry, mock_poolcop, mock_poolcop_data)

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.test_pool_pump"}, blocking=True
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

    state = hass.states.get("switch.test_pool_transfer_pump")
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
        {"entity_id": "switch.test_pool_transfer_pump"},
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
        {"entity_id": "switch.test_pool_transfer_pump"},
        blocking=True,
    )
    mock_poolcop.toggle_auxiliary.assert_not_called()
