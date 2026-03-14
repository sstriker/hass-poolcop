"""Common fixtures for the PoolCop tests."""

import time
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_API_KEY
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.poolcop.const import (
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
    DOMAIN,
)

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in Home Assistant."""
    yield


MOCK_API_KEY = "test-api-key-12345"
MOCK_POOLCOP_ID = "test-poolcop-id"


@pytest.fixture
def mock_config_entry():
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: MOCK_API_KEY,
            "pump_speeds": 3,
        },
        options={
            CONF_FLOW_RATE_1: 10.0,
            CONF_FLOW_RATE_2: 15.0,
            CONF_FLOW_RATE_3: 20.0,
        },
        unique_id=MOCK_POOLCOP_ID,
        entry_id="test_entry_id",
        version=2,
    )


@pytest.fixture
def mock_v1_config_entry():
    """Return a v1 config entry (pre-migration, flow rates in data)."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: MOCK_API_KEY,
            "pump_speeds": 3,
            CONF_FLOW_RATE_1: 10.0,
            CONF_FLOW_RATE_2: 15.0,
            CONF_FLOW_RATE_3: 20.0,
        },
        unique_id=MOCK_POOLCOP_ID,
        entry_id="test_entry_id",
        version=1,
    )


@pytest.fixture
def mock_poolcop_data():
    """Return mocked PoolCop API response data."""
    return {
        "PoolCop": {
            "temperature": {
                "water": 26.5,
                "air": 28.2,
            },
            "pressure": 1500,
            "pH": 7.2,
            "orp": 650,
            "ioniser": 0,
            "voltage": 230,
            "waterlevel": "normal",
            "status": {
                "valveposition": 1,
                "pumpspeed": 2,
                "poolcop": 3,
                "pump": 1,
                "watervalve": 0,
                "ph_control": 0,
                "orp_control": 0,
            },
            "conf": {
                "orp": 1,
                "pH": 1,
                "waterlevel": 1,
                "ioniser": 0,
                "autochlor": 0,
                "air": 1,
            },
            "aux": [
                {
                    "id": 1,
                    "label": "label_aux_17",
                    "slave": 0,
                    "switchable": False,
                    "days": [],
                },
                {
                    "id": 2,
                    "label": "label_aux_17",
                    "slave": 0,
                    "switchable": False,
                    "days": [],
                },
                {
                    "id": 3,
                    "label": "label_aux_17",
                    "slave": 0,
                    "switchable": False,
                    "days": [],
                },
                {
                    "id": 4,
                    "label": "label_aux_6",
                    "slave": 0,
                    "switchable": True,
                    "days": [True, True, True, True, True, True, True],
                },
                {
                    "id": 5,
                    "label": "label_aux_16",
                    "slave": 0,
                    "switchable": False,
                    "days": [],
                },
                {
                    "id": 6,
                    "label": "label_aux_18",
                    "slave": 0,
                    "switchable": False,
                    "days": [],
                },
            ],
            "history": {
                "backwash": "2023-04-15T10:30:00+0200",
                "refill": "2023-04-15T10:32:00+0200",
                "ph_measure": "2023-04-22T09:45:00+0200",
            },
            "alarms": {
                "count": 0,
            },
            "network": {
                "version": "44.8.7",
                "connected": True,
            },
            "settings": {
                "pump": {
                    "nb_speed": 3,
                    "flowrate": 15.0,
                    "speed_cycle1": 2,
                    "speed_cycle2": 1,
                },
                "pool": {
                    "volume": 50,
                },
                "ph": {
                    "set_point": 7.2,
                },
                "orp": {
                    "set_point": 650,
                },
                "filter": {
                    "timer": 2,
                },
            },
            "timers": {
                "cycle1": {
                    "enabled": 1,
                    "start": "08:00:00",
                    "stop": "12:00:00",
                },
                "cycle2": {
                    "enabled": 0,
                    "start": "00:00:00",
                    "stop": "00:00:00",
                },
            },
        },
        "Pool": {
            "nickname": "Test Pool",
            "timezone": "Europe/Amsterdam",
            "latitude": 48.86,
            "longitude": 2.35,
        },
    }


@pytest.fixture
def mock_poolcop():
    """Return a mocked PoolCopilot instance."""
    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot", autospec=True
    ) as mock_poolcop_class:
        poolcop = mock_poolcop_class.return_value
        poolcop.poolcop_id = MOCK_POOLCOP_ID
        poolcop.status = AsyncMock()
        poolcop.set_pump_speed = AsyncMock(return_value={"result": "ok"})
        poolcop.toggle_pump = AsyncMock(return_value={"result": "ok"})
        poolcop.toggle_auxiliary = AsyncMock(return_value={"result": "ok"})
        poolcop.set_valve_position = AsyncMock(return_value={"result": "ok"})
        poolcop.clear_alarm = AsyncMock(return_value={"result": "ok"})
        poolcop.set_force_filtration = AsyncMock(return_value={"result": "ok"})
        poolcop.command_history = AsyncMock(return_value={"commands": []})
        poolcop.close = AsyncMock()
        poolcop.token_limit = 89
        poolcop.token_expire = time.time() + 900  # 15-min window
        yield poolcop
