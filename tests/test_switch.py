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

    states = [s for s in hass.states.async_all("switch") if "aux" in s.entity_id]
    assert len(states) >= 1


async def test_aux_switch_turn_on(
    hass: HomeAssistant, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data
):
    """Aux turn on calls set_auxiliary."""
    # Set aux state to off so turn_on will fire
    mock_device_data["state"]["auxiliaries"]["None"]["Aux4"] = False
    await _setup_integration(hass, mock_config_entry, mock_poolcop_api, mock_device_data, mock_pool_data)

    aux_switch = [s for s in hass.states.async_all("switch") if "aux" in s.entity_id][0]
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

    aux_switch = [s for s in hass.states.async_all("switch") if "aux" in s.entity_id][0]
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

    aux_switch = [s for s in hass.states.async_all("switch") if "aux" in s.entity_id][0]
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": aux_switch.entity_id}, blocking=True
    )
    mock_poolcop_api.set_auxiliary.assert_not_called()
