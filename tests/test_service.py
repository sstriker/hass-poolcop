"""Test PoolCop service functionality."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import (
    DOMAIN,
    SERVICE_CLEAR_ALARM,
    SERVICE_SET_PUMP_SPEED,
    SERVICE_SET_VALVE_POSITION,
    SERVICE_TOGGLE_AUX,
    SERVICE_TOGGLE_PUMP,
)


async def test_service_toggle_pump(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Test the toggle_pump service."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TOGGLE_PUMP,
        {},
        blocking=True,
    )
    mock_poolcop.toggle_pump.assert_called_once()


async def test_service_set_pump_speed(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Test the set_pump_speed service."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PUMP_SPEED,
        {"speed": 2},
        blocking=True,
    )
    mock_poolcop.set_pump_speed.assert_called_once_with(2)


async def test_service_toggle_aux(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Test the toggle_aux service."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TOGGLE_AUX,
        {"aux_id": 4},
        blocking=True,
    )
    mock_poolcop.toggle_auxiliary.assert_called_once_with(4)


async def test_service_set_valve_position(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Test the set_valve_position service."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        {"position": "filter"},
        blocking=True,
    )
    mock_poolcop.set_valve_position.assert_called_once_with(0)


async def test_service_clear_alarm(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Test the clear_alarm service."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_ALARM,
        {},
        blocking=True,
    )
    mock_poolcop.clear_alarm.assert_called_once()


async def test_service_error_handling(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """ConnectionError logged, not raised."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Make set_pump_speed raise ConnectionError
    mock_poolcop.set_pump_speed.side_effect = ConnectionError("offline")

    # Should not raise — service catches and logs
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PUMP_SPEED,
        {"speed": 2},
        blocking=True,
    )


async def test_service_registration_idempotent(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """Double register → no crash."""
    from custom_components.poolcop.service import async_setup_services

    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Call setup_services again — should not crash
    await async_setup_services(hass)
    assert hass.services.has_service(DOMAIN, SERVICE_SET_PUMP_SPEED)


async def test_service_unload_not_registered(hass: HomeAssistant):
    """Unload when not registered → no crash."""
    from custom_components.poolcop.service import async_unload_services

    # Services not registered yet — should not crash
    await async_unload_services(hass)
    assert not hass.services.has_service(DOMAIN, SERVICE_SET_PUMP_SPEED)


async def test_service_toggle_pump_error(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """ConnectionError in toggle_pump is logged, not raised."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_poolcop.toggle_pump.side_effect = ConnectionError("offline")

    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE_PUMP, {}, blocking=True
    )


async def test_service_toggle_aux_error(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """ConnectionError in toggle_aux is logged, not raised."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_poolcop.toggle_auxiliary.side_effect = ConnectionError("offline")

    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE_AUX, {"aux_id": 4}, blocking=True
    )


async def test_service_set_valve_position_error(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """ConnectionError in set_valve_position is logged, not raised."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_poolcop.set_valve_position.side_effect = ConnectionError("offline")

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_VALVE_POSITION, {"position": "filter"}, blocking=True
    )


async def test_service_clear_alarm_error(
    hass: HomeAssistant, mock_config_entry, mock_poolcop, mock_poolcop_data
):
    """ConnectionError in clear_alarm is logged, not raised."""
    mock_poolcop.status.return_value = mock_poolcop_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot",
        return_value=mock_poolcop,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_poolcop.clear_alarm.side_effect = ConnectionError("offline")

    await hass.services.async_call(
        DOMAIN, SERVICE_CLEAR_ALARM, {}, blocking=True
    )
