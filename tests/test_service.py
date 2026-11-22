"""Test PoolCop actions (services)."""

from unittest.mock import patch

import pytest
from aiopoolcop import (
    FiltrationTimer,
    Pool,
    PoolCopClientAccessExpiredError,
    PoolCopClientAuthError,
    PoolCopClientConnectionError,
    PoolCopClientRateLimitError,
    PoolCopDevice,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.poolcop.const import DOMAIN

CLIENT = "custom_components.poolcop.helpers.PoolCopClientAPI"


@pytest.fixture
async def coordinator(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
):
    """Set up the integration and return the coordinator."""
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(mock_device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(mock_pool_data)]
    mock_config_entry.add_to_hass(hass)
    with patch(CLIENT, return_value=mock_poolcop_api):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    return mock_config_entry.runtime_data


async def _call(hass: HomeAssistant, service: str, data: dict | None = None) -> None:
    await hass.services.async_call(DOMAIN, service, data or {}, blocking=True)


@pytest.mark.parametrize(
    ("speed", "expected"),
    [
        (0, "None"),
        (2, "Speed2"),
        ("3", "Speed3"),
        ("speed1", "Speed1"),
        ("None", "None"),
    ],
)
async def test_set_pump_speed(
    hass: HomeAssistant, coordinator, mock_poolcop_api, speed, expected
):
    """Speeds are accepted as numbers or names."""
    await _call(hass, "set_pump_speed", {"speed": speed})
    mock_poolcop_api.set_pump_speed.assert_called_once_with(2478, expected)


@pytest.mark.parametrize("speed", [9, -1, "fast"])
async def test_set_pump_speed_invalid(hass: HomeAssistant, coordinator, speed):
    """Invalid speeds are rejected."""
    with pytest.raises(Exception, match="speed"):
        await _call(hass, "set_pump_speed", {"speed": speed})


async def test_toggle_pump(
    hass: HomeAssistant, coordinator, mock_poolcop_api, mock_device_data
):
    """Toggle turns a running pump off, then (pending) back on."""
    assert mock_device_data["state"]["pumpsInfo"][0]["pumpState"] is True
    await _call(hass, "toggle_pump")
    mock_poolcop_api.set_pump.assert_called_once_with(2478, on=False)

    # The pending 'off' is used for the next toggle
    await _call(hass, "toggle_pump")
    assert mock_poolcop_api.set_pump.call_args.kwargs == {"on": True}


async def test_toggle_pump_no_pumps(hass: HomeAssistant, coordinator, mock_poolcop_api):
    """Without pump info the pump is assumed off."""
    coordinator.data.device.state.pumps.clear()
    await _call(hass, "toggle_pump")
    mock_poolcop_api.set_pump.assert_called_once_with(2478, on=True)


async def test_toggle_aux(
    hass: HomeAssistant, coordinator, mock_poolcop_api, mock_device_data
):
    """Toggle an auxiliary output."""
    assert mock_device_data["state"]["auxiliaries"]["None"]["Aux1"] is True
    await _call(hass, "toggle_aux", {"aux_id": 1})
    mock_poolcop_api.set_auxiliary.assert_called_once_with(2478, "None", 1, on=False)


async def test_toggle_aux_unknown_module(
    hass: HomeAssistant, coordinator, mock_poolcop_api
):
    """An unknown module counts as off."""
    await _call(hass, "toggle_aux", {"aux_id": 2, "module": "XM8"})
    mock_poolcop_api.set_auxiliary.assert_called_once_with(2478, "XM8", 2, on=True)


@pytest.mark.parametrize("position", ["backwash", "Backwash", "BACKWASH"])
async def test_set_valve_position(
    hass: HomeAssistant, coordinator, mock_poolcop_api, position
):
    """Valve positions are case-insensitive."""
    await _call(hass, "set_valve_position", {"position": position})
    mock_poolcop_api.set_valve_position.assert_called_once_with(2478, "Backwash")


async def test_set_valve_position_invalid(hass: HomeAssistant, coordinator):
    """Unknown positions are rejected."""
    with pytest.raises(Exception, match="must be one of"):
        await _call(hass, "set_valve_position", {"position": "sideways"})


async def test_clear_alarm(hass: HomeAssistant, coordinator, mock_poolcop_api):
    """Clear one alarm or all alarms."""
    await _call(hass, "clear_alarm", {"alarm_code": "PressureLowPump1"})
    mock_poolcop_api.clear_alarm.assert_called_once_with(2478, "PressureLowPump1")
    await _call(hass, "clear_alarm")
    mock_poolcop_api.clear_all_alarms.assert_called_once_with(2478)


async def test_stop_backwash(hass: HomeAssistant, coordinator, mock_poolcop_api):
    """Stop a backwash."""
    await _call(hass, "stop_backwash")
    mock_poolcop_api.stop_backwash.assert_called_once_with(2478)


async def test_set_filtration_mode(hass: HomeAssistant, coordinator, mock_poolcop_api):
    """Set the filtration mode (snake_case from the UI)."""
    await _call(hass, "set_filtration_mode", {"mode": "eco_plus"})
    mock_poolcop_api.set_filtration_timer.assert_called_once_with(2478, "EcoPlus")


async def test_set_filtration_timers(
    hass: HomeAssistant, coordinator, mock_poolcop_api
):
    """Changed cycle settings are merged into the current timers."""
    current = coordinator.data.device.settings.filtrations[0]
    await _call(
        hass,
        "set_filtration_timers",
        {"cycle_1_start": "08:30", "cycle_1_end": "12:00:00", "cycle_2_enabled": False},
    )
    args = mock_poolcop_api.set_filtration_timer.call_args
    mode = current.filtration_mode if current.filtration_mode != "NoPump" else "Timer"
    assert args.args == (2478, mode)
    timers = args.kwargs["timers"]
    assert timers[0] == FiltrationTimer(
        id=current.timers[0].id,
        enabled=current.timers[0].enabled,
        time_on="08:30:00",
        time_off="12:00:00",
    )
    assert timers[1].enabled is False
    assert timers[1].time_on == current.timers[1].time_on


async def test_set_filtration_timers_mode_and_new_timer(
    hass: HomeAssistant, coordinator, mock_poolcop_api
):
    """A mode can be given, and missing timers are created."""
    filtration = coordinator.data.device.settings.filtrations[0]
    filtration.timers.clear()
    await _call(
        hass,
        "set_filtration_timers",
        {"mode": "timer", "cycle_2_start": "16:00", "cycle_2_enabled": True},
    )
    args = mock_poolcop_api.set_filtration_timer.call_args
    assert args.args == (2478, "Timer")
    assert args.kwargs["timers"] == [
        FiltrationTimer(id=1),
        FiltrationTimer(id=2, enabled=True, time_on="16:00:00"),
    ]


async def test_set_filtration_timers_forced_mode_defaults_to_timer(
    hass: HomeAssistant, coordinator, mock_poolcop_api
):
    """While forced, changing timers keeps the timer mode."""
    filtration = coordinator.data.device.settings.filtrations[0]
    object.__setattr__(filtration, "filtration_mode", "Forced24H")
    await _call(hass, "set_filtration_timers", {"cycle_1_enabled": True})
    assert mock_poolcop_api.set_filtration_timer.call_args.args == (2478, "Timer")


async def test_set_filtration_timers_without_filtrations(
    hass: HomeAssistant, coordinator, mock_poolcop_api
):
    """Without filtration settings the timer mode is used."""
    coordinator.data.device.settings.filtrations.clear()
    await _call(hass, "set_filtration_timers", {"cycle_1_enabled": True})
    args = mock_poolcop_api.set_filtration_timer.call_args
    assert args.args == (2478, "Timer")
    assert args.kwargs["timers"] == [FiltrationTimer(id=1, enabled=True)]


async def test_set_filtration_timers_nothing_to_change(
    hass: HomeAssistant, coordinator
):
    """At least one setting is required."""
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "set_filtration_timers")
    assert err.value.translation_key == "nothing_to_change"


@pytest.mark.parametrize(
    ("error", "translation_key"),
    [
        (PoolCopClientConnectionError("down"), "command_failed"),
        (PoolCopClientRateLimitError("slow down"), "rate_limited"),
        (PoolCopClientAccessExpiredError("expired"), "access_expired"),
    ],
)
async def test_command_errors(
    hass: HomeAssistant, coordinator, mock_poolcop_api, error, translation_key
):
    """API errors become translated Home Assistant errors."""
    mock_poolcop_api.stop_backwash.side_effect = error
    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, "stop_backwash")
    assert err.value.translation_key == translation_key


async def test_command_auth_error_starts_reauth(
    hass: HomeAssistant, coordinator, mock_poolcop_api
):
    """A rejected key during a command starts reauth."""
    mock_poolcop_api.clear_all_alarms.side_effect = PoolCopClientAuthError("403")
    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, "clear_alarm")
    assert err.value.translation_key == "auth_failed"
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_target_by_config_entry_id(
    hass: HomeAssistant, coordinator, mock_config_entry, mock_poolcop_api
):
    """The PoolCop can be chosen explicitly."""
    await _call(hass, "stop_backwash", {"config_entry_id": mock_config_entry.entry_id})
    mock_poolcop_api.stop_backwash.assert_called_once_with(2478)


async def test_target_unknown_entry(hass: HomeAssistant, coordinator):
    """An unknown entry ID is rejected."""
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "stop_backwash", {"config_entry_id": "nope"})
    assert err.value.translation_key == "entry_not_found"


async def test_target_not_loaded_entry(hass: HomeAssistant, coordinator):
    """An entry that isn't loaded is rejected."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "k"}, unique_id="3001", version=3
    )
    entry.add_to_hass(hass)
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "stop_backwash", {"config_entry_id": entry.entry_id})
    assert err.value.translation_key == "entry_not_loaded"


async def test_target_required_with_several_entries(
    hass: HomeAssistant, coordinator, mock_config_entry, mock_poolcop_api
):
    """With several PoolCops loaded the target is required."""
    second = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: mock_config_entry.data[CONF_API_KEY], "pump_speeds": 3},
        unique_id="3001",
        version=3,
    )
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "stop_backwash")
    assert err.value.translation_key == "entry_required"


async def test_no_loaded_entries(hass: HomeAssistant, coordinator, mock_config_entry):
    """Without a loaded PoolCop the action fails clearly."""
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "toggle_pump")
    assert err.value.translation_key == "no_loaded_entries"


async def test_entry_of_other_domain(hass: HomeAssistant, coordinator):
    """Entries of other integrations are rejected."""
    other = MockConfigEntry(domain="other")
    other.add_to_hass(hass)
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "stop_backwash", {"config_entry_id": other.entry_id})
    assert err.value.translation_key == "entry_not_found"
