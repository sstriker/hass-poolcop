"""Constants for the PoolCop integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "poolcop"
LOGGER = logging.getLogger(__package__)

# Update intervals (in seconds)
NORMAL_UPDATE_INTERVAL = 120  # 2 minutes during normal operation
TRANSITION_UPDATE_INTERVAL = 15  # 15 seconds when transitions are imminent
CYCLE_END_PREDICTION_WINDOW = 300  # 5 minutes before predicted cycle end

# Alarm fetching interval (in seconds)
ALARM_FETCH_INTERVAL = 14400  # 4 hours

# Storage constants
STORAGE_KEY = "poolcop_learned_data"
STORAGE_VERSION = 1

# Configuration constants for flow rates based on pump speed levels (1, 2, 3)
CONF_FLOW_RATE_1 = "flow_rate_1"  # Low speed
CONF_FLOW_RATE_2 = "flow_rate_2"  # Medium speed
CONF_FLOW_RATE_3 = "flow_rate_3"  # High speed

# The PoolCopilot API provides 90 requests per 900s (15 minutes) token.
# With variable update frequency, we ensure staying within rate limits
# while providing more timely updates during important transitions.
SCAN_INTERVAL = timedelta(seconds=NORMAL_UPDATE_INTERVAL)

# Services
SERVICE_SET_PUMP_SPEED = "set_pump_speed"
SERVICE_TOGGLE_PUMP = "toggle_pump"
SERVICE_TOGGLE_AUX = "toggle_aux"
SERVICE_SET_VALVE_POSITION = "set_valve_position"
SERVICE_CLEAR_ALARM = "clear_alarm"

VALVE_POSITIONS = {
    "filter": 0,
    "waste": 1,
    "closed": 2,
    "backwash": 3,
    "bypass": 4,
    "rinse": 5,
}

VALVE_POSITION_NAMES = {
    0: "Filter",
    1: "Waste",
    2: "Closed",
    3: "Backwash",
    4: "Bypass",
    5: "Rinse",
    6: "Unknown",
    7: "None",
}

WATERLEVEL_STATES = {
    0: "Not Installed",
    1: "Low",
    2: "Normal",
    3: "High",
    4: "Error",
}

WATER_VALVE_POSITIONS = {
    0: "Standby",
    1: "Refill",
    2: "Measure",
}

# Add a mapping for 'Watervalve' (valve used for water level control)
WATERVALVE_STATES = {0: "Standby", 1: "Open", 2: "Closed", 3: "Measure"}

FORCED_FILTRATION_MODES = {
    0: "None",
    1: "24 Hours",
    2: "48 Hours",
    3: "72 Hours",
}

POOL_TYPES = {
    0: "Skimmer",
    1: "Infinity A",
    2: "Infinity B",
    3: "Spa",
}

PUMP_TYPES = {
    0: "Unknown",
    1: "Single Speed",
    2: "Two Speed",
    3: "Three Speed",
    4: "Variable Speed",
    5: "Variable Speed (3-step)",
    6: "External",
}

FILTER_MODES = {
    0: "Basic",
    1: "Smart",
    2: "Economy",
    3: "Custom",
}

FILTER_TIMER_MODES = {
    0: "STOP - Disabled",  # Completely disables filtration
    1: "TIMER - Manual Schedule",  # User-defined ON/OFF times for two cycles
    2: "ECO+ - Intelligent",  # Adjusts runtime based on water temperature
    3: "VOLUME - Pool Volume",  # Based on pool volume, pump flow, desired turnovers
    4: "CONTINUOUS - 23h/day",  # Runs 23 hours/day in two cycles
    5: "FORCE 24H",  # Overrides normal logic to run for 24h
    6: "FORCE 48H",  # Overrides normal logic to run for 48h
    7: "FORCE 72H",  # Overrides normal logic to run for 72h
    8: "24/24 - Always On",  # True continuous mode, pump runs 24/7
}

PH_TYPES = {
    0: "Acid (pH-)",
    1: "Base (pH+)",
}

OPERATION_MODES = {
    0: "Stop",  # PoolCop stopped
    1: "Freeze",  # PoolCop freeze protection
    2: "Forced",  # PoolCop in forced mode
    3: "Auto",  # Auto mode
    4: "Timer",  # Timers mode
    5: "Manual",  # Manual mode
    6: "Paused",  # PoolCop paused
    7: "External",  # External mode
    8: "Unknown",
    9: "Unknown",
}

# Timer-related constants
DEFAULT_TIMER_UPDATE_INTERVAL = 15 * 60  # 15 minutes
APPROACHING_TIMER_UPDATE_INTERVAL = 60  # 1 minute
TIMER_APPROACHING_THRESHOLD = 10 * 60  # 10 minutes
