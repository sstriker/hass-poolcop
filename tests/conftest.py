"""Common fixtures for the PoolCop tests."""

from copy import deepcopy
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
MOCK_DEVICE_ID = "2478"

# Raw API response dict matching the client-api.poolcop.net shape.
# Copied from python-aiopoolcop/tests/conftest.py DEVICE_RESPONSE.
MOCK_DEVICE_RESPONSE = {
    "id": 2478,
    "nickname": "Striker",
    "uuid": "09600011-2620-7caf-f22a-835fc72000f5",
    "mac": "02:09:60:00:11:26",
    "installationDate": "2022-07-05T00:00:04+02:00",
    "connectionDate": "2026-04-04T16:00:59+02:00",
    "lastPing": "00:00:10.5820637",
    "isFullyConnected": True,
    "cloudAccessState": "Unlimited",
    "state": {
        "pH": 7.5,
        "orp": 810,
        "airTemperature": 27,
        "waterTemperature": 27.2,
        "freeAvailableChlorine": 0,
        "totalChlorine": 0,
        "freeChlorine": 0,
        "batteryVoltage": 14.4,
        "mainsVoltage": 187,
        "salt": 0,
        "serviceMode": False,
        "pHDosing": False,
        "disinfectionDosing": False,
        "dateTime": "2026-04-04T16:00:55",
        "alarms": ["PressureLowPump1"],
        "pumpsInfo": [
            {
                "id": 0,
                "pumpCurrentSpeed": "Speed1",
                "pumpPressure": 76.5,
                "pumpState": True,
                "valvePosition": "Filter",
                "runningStatus": "TimerMode",
                "numberOfSpeeds": "Speed3",
                "filtrationMode": "Timer",
                "pumpForcedRemaining": "00:00:00",
            }
        ],
        "waterLevel": {
            "installed": True,
            "state": "Normal",
            "setPoint": "High",
            "isOnTarget": True,
            "isOnError": False,
            "isRefilling": False,
            "isMeasuring": False,
        },
        "jetStream": {"installed": False, "isRunning": False},
        "poolCover": {
            "installed": True,
            "controllable": False,
            "isClosing": False,
            "isOpening": False,
            "isOpen": False,
            "isStopped": True,
        },
        "flowVis": [],
        "inputs": {"Input1": True, "Input2": False},
        "auxiliaries": {"None": {"Aux1": True, "Aux2": False}},
    },
    "settings": {
        "pool": {
            "type": "RimflowTypeB",
            "volume": 77,
            "estimatedFlowrate": 9,
            "freezeProtection": False,
            "turnoverPerDay": 1,
        },
        "pH": {
            "installed": True,
            "setPoint": 7.5,
            "lowValue": 6.8,
            "highValue": 8.2,
            "autoAdjust": True,
            "mode": "phMinus",
            "maxDosingDuration": "00:10:00",
            "orpProtection": True,
        },
        "disinfection": {
            "lowShutdownTemperature": 7,
            "disinfectantType": "Chlorine",
            "mode": "ORP",
            "electrolyser": {
                "polarityInversionDuration": 4,
                "productionPercent": 80,
            },
            "orp": {
                "installed": True,
                "setPoint": 770,
                "lowValue": 500,
                "highValue": 900,
                "hyperchlorationSetPoint": 850,
                "hyperchlorationWeekday": "Monday",
            },
            "fac": {
                "installed": False,
                "setPoint": 0,
                "lowValue": 0,
                "highValue": 0,
                "protection": False,
            },
            "fc": {
                "installed": False,
                "setPoint": 0,
                "lowValue": 0,
                "highValue": 0,
            },
            "tc": {
                "installed": False,
                "lowValue": 0,
                "highValue": 0,
            },
        },
        "waterLevel": {
            "installed": True,
            "setPoint": "High",
            "canRefill": True,
            "canReduce": False,
            "maxFillDuration": "01:20:00",
            "drainingDuration": "00:10:00",
            "continuousFill": False,
            "reductionThreshold": 30,
        },
        "filtrations": [
            {
                "id": 1,
                "pumpType": "BaduEcoTouch",
                "filtrationMode": "Timer",
                "nbSpeeds": "Speed3",
                "speedCycle1": "Speed1",
                "speedCycle2": "Speed2",
                "speedCycle3": "Speed3",
                "speedCycle4": "Speed3",
                "speedBackwash": "Speed3",
                "speed24": "Speed1",
                "coverFiltrationSpeed": "Speed1",
                "coverFiltrationReduction": 5,
                "backwashFlowRate": 15.0,
                "flowRateMonitoringSpeed": "Speed1",
                "backwashTrigger": "Pressure",
                "filtrationValveType": "MultiPort",
                "rinseValveType": "None",
                "wasteLineValve": "None",
                "currentCycleElapsedTime": "01:30:00",
                "currentCycleRemainingTime": "02:30:00",
                "backwashPressure": 144,
                "backwashDuration": "00:02:30",
                "backwashTime": "11:00:00",
                "backwashMode": "Automatic",
                "maxIntervalBetweenBackwash": "14.00:00:00",
                "rinseDuration": "00:00:20",
                "alarmPressure": 51,
                "lowPressure": 52,
                "pumpProtection": True,
                "filterType": "Pressure",
                "timers": [
                    {
                        "id": 1,
                        "enabled": True,
                        "timeOn": "23:59:00",
                        "timeOff": "04:00:00",
                    },
                    {
                        "id": 2,
                        "enabled": True,
                        "timeOn": "08:00:00",
                        "timeOff": "21:59:00",
                    },
                ],
            }
        ],
        "auxs": {
            "None": {
                "Aux4": {
                    "id": "Aux4",
                    "auxChannel": 4,
                    "module": "None",
                    "moduleId": 0,
                    "label": "TransferPump",
                    "friendlyName": "Apf",
                    "status": False,
                    "isSlave": False,
                    "slavedTo": "NotSlave",
                    "mode": "Manual",
                    "isReserved": False,
                    "isHeatingControlled": False,
                    "heatingSetPoint": 0,
                    "pulseDuration": "00:00:00",
                    "moduleChannel": 0,
                    "daysOfWeek": [],
                    "timers": [
                        {"id": 1, "timeOn": "00:00:00", "timeOff": "00:00:00"}
                    ],
                }
            }
        },
        "aco": {
            "installed": False,
            "flowRate": 0,
            "module": "None",
            "aux": "Aux1",
        },
        "remnant": {
            "installed": False,
            "flowRate": 0,
            "module": "None",
            "aux": "Aux1",
            "temperatureCompensation": False,
            "mode": "Manual",
        },
        "suctionValve": {
            "type": "None",
            "source": "None",
        },
    },
    "equipmentsInfo": {
        "hasPHSensor": True,
        "hasORPSensor": True,
        "hasAirTemperatureSensor": True,
        "hasFACSensor": False,
        "hasConductivitySensor": False,
        "hasSaltSensor": False,
        "hasWaterLevelSensor": True,
        "hasFCSensor": False,
        "hasTCSensor": False,
        "hasFlowMeter": False,
        "hasEnergyMeter": False,
        "hasPoolCover": True,
        "hasJetStream": False,
    },
    "history": {
        "pHLastInjectionDuration": None,
        "disinfectionLastInjectionDuration": None,
        "acoLastInjectionDuration": None,
        "remnantLastInjectionDuration": None,
        "lastpHMeasureDate": "2026-05-23T04:15:00",
        "lastRefillDate": "2026-05-16T22:28:00",
        "lastBackwashDate": "2026-05-16T11:03:00",
    },
    "versionInfo": {
        "poolCopVersion": "44.9.0",
        "model": "Evolution",
        "osVersion": "1.2.3",
    },
}

MOCK_POOL_RESPONSE = {
    "id": 97138,
    "nickname": "Striker",
    "address1": "Test St 1",
    "zipCode": "1234 AB",
    "city": "TestCity",
    "country": "Netherlands",
    "latitude": 52.165958,
    "longitude": 6.038603,
    "timezone": "Europe/Amsterdam",
    "creationDate": "2022-07-06T08:22:37+02:00",
    "devices": [{"id": 2478, "nickname": "Striker"}],
}


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
        unique_id=MOCK_DEVICE_ID,
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
        unique_id=MOCK_DEVICE_ID,
        entry_id="test_entry_id",
        version=1,
    )


@pytest.fixture
def mock_device_data():
    """Return a deep copy of the mock device API response dict."""
    return deepcopy(MOCK_DEVICE_RESPONSE)


@pytest.fixture
def mock_pool_data():
    """Return a deep copy of the mock pool API response dict."""
    return deepcopy(MOCK_POOL_RESPONSE)


@pytest.fixture
def mock_poolcop_api():
    """Return a mocked PoolCopClientAPI instance."""
    api = AsyncMock()
    api.get_device = AsyncMock()
    api.get_pools = AsyncMock()
    api.set_pump = AsyncMock()
    api.set_pump_speed = AsyncMock()
    api.set_valve_position = AsyncMock()
    api.clear_alarm = AsyncMock()
    api.clear_all_alarms = AsyncMock()
    api.set_auxiliary = AsyncMock()
    api.set_pump_forced = AsyncMock()
    api.set_heating_setpoint = AsyncMock()
    api.set_jet_stream = AsyncMock()
    api.close = AsyncMock()
    return api
