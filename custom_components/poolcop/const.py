"""Constants for the PoolCop integration."""

from __future__ import annotations

import logging
from datetime import timedelta
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
    8: "Eco+",  # Eco+ intelligent mode
    9: "Continuous",  # 24/24h continuous mode
}

# Timer-related constants
DEFAULT_TIMER_UPDATE_INTERVAL = 15 * 60  # 15 minutes
APPROACHING_TIMER_UPDATE_INTERVAL = 60  # 1 minute
TIMER_APPROACHING_THRESHOLD = 10 * 60  # 10 minutes

# Aux label display names (maps numeric label IDs to human-readable names)
# Without the X-PoolCopilot-Lang header, the API returns "label_aux_N" keys
# where N is the numeric label ID.
AUX_LABEL_NAMES: Final[dict[int, str]] = {
    0: "Pool Light",
    1: "Pool Cleaner",
    2: "Pool Heating",
    3: "Disinfection",
    4: "Electrolysis",
    5: "Remnant",
    6: "Transfer Pump",
    7: "UV",
    8: "Spa",
    9: "Fountain",
    10: "Borehole",
    11: "Pool House",
    12: "Garden 1",
    13: "Garden 2",
    14: "Garden 3",
    15: "Available",
    16: "Waste Valve",
    17: "Speed Control",
    18: "ORP Control",
    19: "Remnant",
    20: "Pool Cover",
    21: "Jet Stream",
    22: "External Warnings",
    23: "Cleaning Valve",
    24: "Rinsing Valve",
    25: "Dosing APF",
    26: "Dosing ACO",
    27: "Suction Valve",
}


# Fixed-function label IDs (16+) that have first-class entity counterparts
AUX_FIXED_FUNCTION_LABELS: Final[set[int]] = {16, 17, 18}

# Valve-type aux label IDs — OPENING device class (Open/Closed)
AUX_VALVE_LABELS: Final[set[int]] = {16, 23, 24, 27}

# Relay-type aux label IDs with first-class counterparts — POWER device class (On/Off)
AUX_RELAY_LABELS: Final[set[int]] = {17, 18}

# Aux label icon mapping — (on_icon, off_icon) per label ID
AUX_LABEL_ICONS: Final[dict[int, tuple[str, str]]] = {
    0: ("mdi:lightbulb-on", "mdi:lightbulb-off"),  # Pool Light
    1: ("mdi:robot-vacuum", "mdi:robot-vacuum-off"),  # Pool Cleaner
    2: ("mdi:heating-coil", "mdi:heating-coil"),  # Pool Heating
    3: ("mdi:bottle-tonic-skull", "mdi:bottle-tonic-skull-outline"),  # Disinfection
    4: ("mdi:flash", "mdi:flash-off"),  # Electrolysis
    6: ("mdi:pump", "mdi:pump-off"),  # Transfer Pump
    7: ("mdi:weather-sunny", "mdi:weather-sunny-off"),  # UV
    8: ("mdi:hot-tub", "mdi:hot-tub"),  # Spa
    9: ("mdi:fountain", "mdi:fountain"),  # Fountain
    10: ("mdi:water-well", "mdi:water-well-outline"),  # Borehole
    11: ("mdi:home", "mdi:home-outline"),  # Pool House
    20: ("mdi:window-shutter", "mdi:window-shutter-open"),  # Pool Cover
    21: ("mdi:waves-arrow-right", "mdi:waves-arrow-right"),  # Jet Stream
    22: ("mdi:alert", "mdi:alert-outline"),  # External Warnings
    25: ("mdi:beaker", "mdi:beaker-outline"),  # Dosing APF
    26: ("mdi:beaker", "mdi:beaker-outline"),  # Dosing ACO
}


def aux_label_id(api_label: str) -> int | None:
    """Extract the numeric label ID from an API label string like 'label_aux_17'."""
    if api_label and api_label.startswith("label_aux_"):
        try:
            return int(api_label.removeprefix("label_aux_"))
        except ValueError:
            pass
    return None


def aux_display_name(api_label: str, aux_id: int) -> str:
    """Resolve an API aux label to a clean display name.

    The API returns "label_aux_N" where N is the numeric label ID.
    Maps to a human-readable name via AUX_LABEL_NAMES.
    """
    label_id = aux_label_id(api_label)
    if label_id is not None:
        return AUX_LABEL_NAMES.get(label_id, f"Aux {aux_id}")
    return api_label or f"Aux {aux_id}"
