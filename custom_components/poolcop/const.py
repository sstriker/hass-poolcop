"""Constants for the PoolCop integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Final

DOMAIN: Final = "poolcop"
LOGGER = logging.getLogger(__package__)

# Configuration
CONF_POOLCOP_ID: Final = "poolcop_id"

# Update interval (in seconds)
UPDATE_INTERVAL: Final = 60
CONFIG_UPDATE_INTERVAL: Final = 1800  # 30 minutes for config endpoints

# Storage constants
STORAGE_KEY: Final = "poolcop_learned_data"
STORAGE_VERSION: Final = 1

# Configuration constants for flow rates based on pump speed levels
CONF_FLOW_RATE_1: Final = "flow_rate_1"
CONF_FLOW_RATE_2: Final = "flow_rate_2"
CONF_FLOW_RATE_3: Final = "flow_rate_3"

SCAN_INTERVAL = timedelta(seconds=UPDATE_INTERVAL)

# OAuth2 URLs
OAUTH2_AUTHORIZE: Final = "https://poolcopilot.com/oauth2/authorize"
OAUTH2_TOKEN: Final = "https://poolcopilot.com/oauth2/token"

# Services
SERVICE_SET_PUMP_SPEED: Final = "set_pump_speed"
SERVICE_SET_PUMP: Final = "set_pump"
SERVICE_SET_AUX: Final = "set_aux"
SERVICE_SET_VALVE_POSITION: Final = "set_valve_position"
SERVICE_CLEAR_ALARM: Final = "clear_alarm"

# Valve positions — cloud API uses string values directly
VALVE_POSITIONS: Final[list[str]] = [
    "Filter",
    "Waste",
    "Closed",
    "Backwash",
    "Bypass",
    "Rinse",
]

# Forced filtration modes
FORCED_FILTRATION_MODES: Final[dict[str, str]] = {
    "None": "None",
    "Force24": "24 Hours",
    "Force48": "48 Hours",
    "Force72": "72 Hours",
}

# Aux label icon mapping — (on_icon, off_icon) keyed by label string
AUX_LABEL_ICONS: Final[dict[str, tuple[str, str]]] = {
    "Pool Light": ("mdi:lightbulb-on", "mdi:lightbulb-off"),
    "Pool Cleaner": ("mdi:robot-vacuum", "mdi:robot-vacuum-off"),
    "Pool Heating": ("mdi:heating-coil", "mdi:heating-coil"),
    "Disinfection": ("mdi:bottle-tonic-skull", "mdi:bottle-tonic-skull-outline"),
    "Electrolysis": ("mdi:flash", "mdi:flash-off"),
    "Transfer Pump": ("mdi:pump", "mdi:pump-off"),
    "UV": ("mdi:weather-sunny", "mdi:weather-sunny-off"),
    "Spa": ("mdi:hot-tub", "mdi:hot-tub"),
    "Fountain": ("mdi:fountain", "mdi:fountain"),
    "Borehole": ("mdi:water-well", "mdi:water-well-outline"),
    "Pool House": ("mdi:home", "mdi:home-outline"),
    "Pool Cover": ("mdi:window-shutter", "mdi:window-shutter-open"),
    "Jet Stream": ("mdi:waves-arrow-right", "mdi:waves-arrow-right"),
    "External Warnings": ("mdi:alert", "mdi:alert-outline"),
    "Dosing APF": ("mdi:beaker", "mdi:beaker-outline"),
    "Dosing ACO": ("mdi:beaker", "mdi:beaker-outline"),
}

# Alarm severity levels
ALARM_SEVERITIES: Final[dict[str, str]] = {
    "Remind": "Reminder",
    "Warning": "Warning",
    "Error": "Error",
    "Failure": "Failure",
}

# Running status modes where filtration cycles are active
CYCLE_ACTIVE_MODES: Final[set[str]] = {"Forced", "Auto", "Timer", "24/24"}
