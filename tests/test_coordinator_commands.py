"""Test coordinator rate limiting, pending commands and error handling."""

import time
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiopoolcop import (
    Pool,
    PoolCopClientAccessExpiredError,
    PoolCopClientConnectionError,
    PoolCopClientRateLimitError,
    PoolCopDevice,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.poolcop.const import DOMAIN, PENDING_COMMAND_TIMEOUT
from custom_components.poolcop.coordinator import PoolCopDataUpdateCoordinator

COORDINATOR = "custom_components.poolcop.coordinator"


@pytest.fixture
def coordinator(
    hass: HomeAssistant,
    mock_config_entry,
    mock_poolcop_api,
    mock_device_data,
    mock_pool_data,
) -> PoolCopDataUpdateCoordinator:
    """Return a coordinator with a mocked API."""
    mock_config_entry.add_to_hass(hass)
    mock_poolcop_api.get_device.return_value = PoolCopDevice.from_dict(mock_device_data)
    mock_poolcop_api.get_pools.return_value = [Pool.from_dict(mock_pool_data)]
    coord = PoolCopDataUpdateCoordinator(
        hass, mock_poolcop_api, 2478, mock_config_entry
    )
    coord._store = MagicMock(async_save=AsyncMock(), async_load=AsyncMock())
    return coord


async def test_device_calls_are_spaced(coordinator, mock_poolcop_api):
    """Non-exempt calls wait for the per-device limit; exempt ones don't."""
    clock = [1000.0]
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        clock[0] += delay

    fake_time = MagicMock(wraps=time)
    fake_time.monotonic.side_effect = lambda: clock[0]
    with (
        patch(f"{COORDINATOR}.ENTITY_RATE_LIMIT", 10.0),
        patch(f"{COORDINATOR}.time", fake_time),
        patch(f"{COORDINATOR}.asyncio.sleep", fake_sleep),
    ):
        await coordinator._async_update_data()
        coordinator.data = await coordinator._async_update_data()
        assert sleeps == [10.0]

        clock[0] += 3
        await coordinator.set_pump(on=False)  # exempt: no wait
        assert sleeps == [10.0]

        clock[0] += 4
        await coordinator.set_pump_speed("Speed2")  # 6 s left since last call
        assert sleeps == [10.0, 6.0]


async def test_rate_limit_backs_off_then_restores_interval(
    coordinator, mock_poolcop_api
):
    """A 429 slows polling down until the next successful update."""
    normal = coordinator.update_interval
    mock_poolcop_api.get_device.side_effect = PoolCopClientRateLimitError(
        "429", retry_after=60
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(seconds=60)

    mock_poolcop_api.get_device.side_effect = None
    await coordinator._async_update_data()
    assert coordinator.update_interval == normal


async def test_rate_limit_without_retry_after(coordinator, mock_poolcop_api):
    """Without Retry-After the normal interval is kept."""
    normal = coordinator.update_interval
    mock_poolcop_api.get_device.side_effect = PoolCopClientRateLimitError("429")
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.update_interval == normal


async def test_connection_error_fails_update(coordinator, mock_poolcop_api):
    """Connection errors fail the update."""
    mock_poolcop_api.get_device.side_effect = PoolCopClientConnectionError("down")
    with pytest.raises(UpdateFailed) as err:
        await coordinator._async_update_data()
    assert err.value.translation_key == "update_failed"


async def test_access_expired_raises_issue(
    hass: HomeAssistant, coordinator, mock_poolcop_api, mock_config_entry
):
    """Expired cloud access creates a repair issue until the device is back."""
    issue_id = f"cloud_access_expired_{mock_config_entry.entry_id}"
    mock_poolcop_api.get_device.side_effect = PoolCopClientAccessExpiredError("402")
    with pytest.raises(UpdateFailed) as err:
        await coordinator._async_update_data()
    assert err.value.translation_key == "access_expired"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None

    mock_poolcop_api.get_device.side_effect = None
    await coordinator._async_update_data()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_pending_expires(coordinator):
    """A pending state is dropped after the timeout."""
    clock = [500.0]
    fake_time = MagicMock(wraps=time)
    fake_time.monotonic.side_effect = lambda: clock[0]
    with patch(f"{COORDINATOR}.time", fake_time):
        coordinator.set_pending("pump", False)
        assert coordinator.resolve_pending("pump", True) is False
        clock[0] += PENDING_COMMAND_TIMEOUT
        assert coordinator.resolve_pending("pump", True) is True
        assert coordinator._pending == {}


async def test_learned_data_saved_periodically(coordinator, mock_config_entry):
    """Learned data is saved on the first update and then hourly."""
    clock = [100.0]
    fake_time = MagicMock(wraps=time)
    fake_time.monotonic.side_effect = lambda: clock[0]
    with (
        patch(f"{COORDINATOR}.time", fake_time),
        patch.object(mock_config_entry, "async_create_background_task") as task,
    ):
        await coordinator._async_update_data()
        clock[0] += 60
        await coordinator._async_update_data()
        assert task.call_count == 1
        clock[0] += 3600
        await coordinator._async_update_data()
        assert task.call_count == 2
    for call in task.call_args_list:
        call.args[1].close()
