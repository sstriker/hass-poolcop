"""Common fixtures for the PoolCop tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry


from aiopoolcop import (
    Pool,
    PoolCopAlarm,
    PoolCopAuxiliary,
    PoolCopDevice,
    PoolCopState,
    PumpInfo,
    WaterLevelInfo,
)

from custom_components.poolcop.const import (
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
    CONF_POOLCOP_ID,
    DOMAIN,
)

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


MOCK_POOLCOP_ID = 12345
MOCK_TOKEN = {
    "access_token": "mock-access-token",
    "refresh_token": "mock-refresh-token",
    "token_type": "Bearer",
    "expires_in": 3600,
    "expires_at": 9999999999.0,
}


def make_pump_info(**kwargs) -> PumpInfo:
    """Create a PumpInfo with sensible defaults."""
    defaults = {
        "id": 1,
        "current_speed": "Speed1",
        "forced_remaining": "00:00:00",
        "running_status": "Auto",
        "pump_state": True,
        "pump_primed": True,
        "valve_position": "Filter",
        "pressure": 1.2,
    }
    defaults.update(kwargs)
    return PumpInfo(**defaults)


def make_state(**kwargs) -> PoolCopState:
    """Create a PoolCopState with sensible defaults."""
    defaults = {
        "status": "Auto",
        "pumps": [make_pump_info()],
        "ph": 7.2,
        "orp": 650,
        "water_temperature": 26.5,
        "daily_average_water_temperature": 25.0,
        "air_temperature": 28.2,
        "battery_voltage": 12.6,
        "mains_voltage": 230.0,
        "mains_power_lost": False,
        "free_available_chlorine": 0.0,
        "free_chlorine": 0.0,
        "total_chlorine": 0.0,
        "water_level": WaterLevelInfo(installed=True, state="Normal"),
        "auxiliaries": {
            "AuxModule1": {"Aux1": True, "Aux2": False},
        },
        "inputs": {},
        "date_time": "2026-03-16T12:00:00",
    }
    defaults.update(kwargs)
    return PoolCopState(**defaults)


def make_device(**kwargs) -> PoolCopDevice:
    """Create a PoolCopDevice with sensible defaults."""
    defaults = {
        "id": MOCK_POOLCOP_ID,
        "nickname": "My PoolCop",
        "uuid": "test-uuid-1234",
        "mac": "AA:BB:CC:DD:EE:FF",
        "pool_id": 1,
        "user_id": 1,
        "is_connected": True,
        "is_fully_connected": True,
    }
    defaults.update(kwargs)
    return PoolCopDevice(**defaults)


def make_pool(**kwargs) -> Pool:
    """Create a Pool with sensible defaults."""
    defaults = {
        "id": 1,
        "nickname": "My Pool",
        "latitude": -33.8688,
        "longitude": 151.2093,
        "timezone": "Australia/Sydney",
        "city": "Sydney",
        "country": "AU",
    }
    defaults.update(kwargs)
    return Pool(**defaults)


def make_alarm(
    active: bool = True,
    code: str = "AL01",
    severity: str = "Warning",
    label: str = "Test Alarm",
    **kwargs,
) -> PoolCopAlarm:
    """Create a PoolCopAlarm."""
    defaults = {
        "id": 1,
        "pool_cop_id": MOCK_POOLCOP_ID,
        "code": code,
        "severity": severity,
        "label": label,
        "start_date": "2026-03-16T10:00:00",
        "end_date": None if active else "2026-03-16T11:00:00",
    }
    defaults.update(kwargs)
    return PoolCopAlarm(**defaults)


def make_auxiliary(
    module_id: int = 1,
    aux_channel: int = 1,
    label: str = "Pool Light",
    mode: str = "Auto",
    **kwargs,
) -> PoolCopAuxiliary:
    """Create a PoolCopAuxiliary."""
    defaults = {
        "aux_channel": aux_channel,
        "module_id": module_id,
        "mode": mode,
        "label": label,
        "friendly_name": label,
        "is_reserved": False,
        "status": False,
        "has_timer": False,
        "is_heating": False,
    }
    defaults.update(kwargs)
    return PoolCopAuxiliary(**defaults)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": "poolcop",
            "token": MOCK_TOKEN,
            CONF_POOLCOP_ID: MOCK_POOLCOP_ID,
            "pump_speeds": 3,
        },
        options={
            CONF_FLOW_RATE_1: 10.0,
            CONF_FLOW_RATE_2: 15.0,
            CONF_FLOW_RATE_3: 20.0,
        },
        unique_id=str(MOCK_POOLCOP_ID),
        entry_id="test_entry_id",
        version=3,
    )


@pytest.fixture
def mock_poolcop_state() -> PoolCopState:
    """Return a mocked PoolCop state."""
    return make_state()


@pytest.fixture
def mock_poolcop_device() -> PoolCopDevice:
    """Return a mocked PoolCop device."""
    return make_device()


@pytest.fixture
def mock_pool() -> Pool:
    """Return a mocked Pool."""
    return make_pool()


@pytest.fixture
def mock_alarms() -> list[PoolCopAlarm]:
    """Return mocked alarms."""
    return [make_alarm()]


@pytest.fixture
def mock_auxiliaries() -> list[PoolCopAuxiliary]:
    """Return mocked auxiliaries."""
    return [
        make_auxiliary(module_id=1, aux_channel=1, label="Pool Light"),
        make_auxiliary(module_id=1, aux_channel=2, label="Pool Cleaner", mode="Auto"),
    ]


@pytest.fixture
def mock_cloud_api(
    mock_poolcop_state,
    mock_poolcop_device,
    mock_pool,
    mock_alarms,
    mock_auxiliaries,
):
    """Return a mocked PoolCopCloudAPI."""
    with patch(
        "custom_components.poolcop.PoolCopCloudAPI", autospec=True
    ) as mock_api_class:
        api = mock_api_class.return_value
        api.get_state = AsyncMock(return_value=mock_poolcop_state)
        api.get_poolcop = AsyncMock(return_value=mock_poolcop_device)
        api.get_poolcops = AsyncMock(return_value=[mock_poolcop_device])
        api.get_pool = AsyncMock(return_value=mock_pool)
        api.get_alarms = AsyncMock(return_value=mock_alarms)
        api.get_auxiliaries = AsyncMock(return_value=mock_auxiliaries)
        api.get_pump_config = AsyncMock(
            return_value={"type": "Variable", "nbSpeed": 3, "flowrate": 15.0}
        )
        api.get_filter_config = AsyncMock(
            return_value={
                "timerMode": "Auto",
                "backwashDuration": 120,
                "rinseDuration": 30,
            }
        )
        api.get_pool_config = AsyncMock(return_value={"volume": 50.0, "turnover": 2.0})
        api.get_ph_config = AsyncMock(return_value={"setPoint": 7.2})
        api.get_orp_config = AsyncMock(
            return_value={"setPoint": 650, "disinfectantType": "Chlorine"}
        )
        api.get_waterlevel_config = AsyncMock(return_value={})
        api.get_history = AsyncMock(
            return_value={
                "backwashesCount": 42,
                "lastBackwashDate": "2026-03-15T14:30:00",
                "refillsCount": 10,
                "lastRefillDate": "2026-03-10T09:00:00",
                "lastpHMeasureDate": "2026-03-16T08:00:00",
            }
        )
        api.get_equipments = AsyncMock(
            return_value={
                "pH": True,
                "orp": True,
                "air": True,
                "ioniser": False,
                "autochlor": False,
            }
        )
        api.set_pump = AsyncMock()
        api.set_pump_speed = AsyncMock()
        api.set_valve_position = AsyncMock()
        api.set_auxiliary = AsyncMock()
        api.set_forced_filtration = AsyncMock()
        api.clear_alarm = AsyncMock()
        api.close = AsyncMock()
        yield api


@pytest.fixture
def mock_oauth2_session():
    """Mock the OAuth2 session setup."""
    with (
        patch(
            "custom_components.poolcop.config_entry_oauth2_flow.async_get_config_entry_implementation",
        ) as mock_impl,
        patch(
            "custom_components.poolcop.config_entry_oauth2_flow.OAuth2Session",
        ) as mock_session_class,
    ):
        mock_session = MagicMock()
        mock_session.async_ensure_token_valid = AsyncMock()
        mock_session.token = MOCK_TOKEN
        mock_session_class.return_value = mock_session
        mock_impl.return_value = MagicMock()
        yield mock_session


@pytest.fixture
def mock_storage():
    """Mock the storage for learned data."""
    with patch(
        "custom_components.poolcop.coordinator.Store",
    ) as mock_store_class:
        store = mock_store_class.return_value
        store.async_save = AsyncMock()
        store.async_load = AsyncMock(return_value=None)
        yield store
