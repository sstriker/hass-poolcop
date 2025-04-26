"""Common fixtures for the PoolCop tests."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from custom_components.poolcop.const import DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"

@pytest.fixture
def mock_config_entry():
    """Return a mocked config entry."""
    return MagicMock(
        data={CONF_API_KEY: "test-api-key"},
        unique_id="test-poolcop-id",
        entry_id="test",
    )

@pytest.fixture
def mock_poolcop_data():
    """Return mocked PoolCop data."""
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
                "pumpspeed": 50,
                "poolcop": 3,
                "pump": 1,
                "watervalve": 0,
                "ph_control": 0,
                "orp_control": 0,
                "aux1": 0,
                "aux2": 0,
                "aux3": 0,
                "aux4": 0,
                "aux5": 0,
                "aux6": 0,
            },
            "conf": {
                "orp": 1,
                "pH": 1,
                "waterlevel": 1,
                "ioniser": 0,
                "autochlor": 0,
                "air": 1,
            },
            "history": {
                "backwash": "2023-04-15T10:30:00+0200",
                "refill": "2023-04-15T10:32:00+0200",
                "ph_measure": "2023-04-22T09:45:00+0200"
            },
            "network": {
                "version": "1.0.0"
            }
        }
    }

@pytest.fixture
def mock_poolcop():
    """Return a mocked PoolCopilot instance."""
    with patch(
        "custom_components.poolcop.coordinator.PoolCopilot", autospec=True
    ) as mock_poolcop_class:
        poolcop = mock_poolcop_class.return_value
        poolcop.poolcop_id = "test-poolcop-id"
        poolcop.status = AsyncMock()
        poolcop.set_pump_speed = AsyncMock()
        poolcop.set_pump = AsyncMock()
        poolcop.close = AsyncMock()
        yield poolcop