"""Constants for the PoolCop integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Final

DOMAIN: Final = "poolcop"
LOGGER = logging.getLogger(__package__)

# Update intervals (in seconds)
NORMAL_UPDATE_INTERVAL = 45  # 45 seconds during normal operation
TRANSITION_UPDATE_INTERVAL = 30  # 30 seconds when transitions are imminent
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
QUOTA_TRANSITION_THRESHOLD = 20  # Min remaining calls to allow transition speed-up
QUOTA_CONSTRAINED_INTERVAL = 300  # 5 min fallback when quota is low

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
    0: "STOP - Disabled",
    1: "TIMER - Manual Schedule",
    2: "ECO+ - Intelligent",
    3: "VOLUME - Pool Volume",
    4: "CONTINUOUS - 23h/day",
    5: "FORCE 24H",
    6: "FORCE 48H",
    7: "FORCE 72H",
    8: "24/24 - Always On",
}

# Descriptions for filter timer modes (from PoolCop Evolution manual §4.4.4.6)
FILTER_TIMER_MODE_DESCRIPTIONS: Final[dict[int, str]] = {
    0: "Completely disables filtration. Both cycles set to 00:00-00:00.",
    1: "User-defined ON/OFF times for Cycle 1 and Cycle 2.",
    2: "Cycle 1 user-set, Cycle 2 duration adjusted based on water temperature.",
    3: "Cycle 1 user-set, Cycle 2 duration calculated from pool volume and turnovers.",
    4: "Runs 23h/day in two 11h30 cycles. Only start time configurable.",
    5: "Overrides normal cycles. Pump runs for 24h then reverts to previous settings.",
    6: "Overrides normal cycles. Pump runs for 48h then reverts to previous settings.",
    7: "Overrides normal cycles. Pump runs for 72h then reverts to previous settings.",
    8: "True continuous mode. Pump runs 24/7. No cycles.",
}

PH_TYPES = {
    0: "Acid (pH-)",
    1: "Base (pH+)",
}

# Descriptions for pH types
PH_TYPE_DESCRIPTIONS: Final[dict[int, str]] = {
    0: "Acid dosing (pH-). Lowers pH when above setpoint.",
    1: "Base dosing (pH+). Raises pH when below setpoint.",
}

# Disinfectant types (from PoolCop Evolution manual §5.4.3 ORP Control)
DISINFECTANT_TYPES: Final[dict[int, str]] = {
    0: "Read",
    1: "Chlorine",
    2: "Salt",
    3: "Bromine",
    4: "Other",
}

# Descriptions for disinfectant types
DISINFECTANT_TYPE_DESCRIPTIONS: Final[dict[int, str]] = {
    0: "Read and display ORP only. No dosing control.",
    1: "Liquid chlorine injection. Controlled by ORP sensor via Aux 6.",
    2: "Salt water chlorinator. External system controlled via Aux 6.",
    3: "Bromine dosing. Controlled by ORP sensor via Aux 6.",
    4: "Other disinfection method. Algorithm not optimized for specific type.",
}

OPERATION_MODES = {
    0: "Stop",
    1: "Freeze",
    2: "Forced",
    3: "Auto",
    4: "Timer",
    5: "Manual",
    6: "Paused",
    7: "External",
    8: "Eco+",
    9: "Continuous",
}

# Descriptions for operating modes (from PoolCop Evolution manual §4.4.4.4)
OPERATION_MODE_DESCRIPTIONS: Final[dict[int, str]] = {
    0: "Filtration stopped. No cycles defined.",
    1: "Freeze protection active. Pump runs to prevent freezing.",
    2: "Forced filtration. Overrides normal cycles for 24/48/72h.",
    3: "Automatic mode. PoolCop adjusts Cycle 2 duration based on water temperature.",
    4: "Timer mode. Filtration runs on user-programmed Cycle 1 and Cycle 2 schedules.",
    5: "Manual mode. Pump started by user, runs outside programmed timer periods.",
    6: "Paused. All automatic actions suspended.",
    7: "External mode. Pump controlled by external system.",
    8: "Eco+ intelligent mode. Runtime adjusted based on water temperature.",
    9: "Continuous mode. Runs 23h/day in two 11h30 cycles.",
}

# Operating modes where filtration cycles are active and cycle sensors are relevant
CYCLE_ACTIVE_MODES: Final[set[int]] = {2, 3, 4, 8, 9}

# Descriptions for valve positions (from PoolCop Evolution manual §4.4.4)
VALVE_POSITION_DESCRIPTIONS: Final[dict[int, str]] = {
    0: "Normal operation. Water flows through filter media to pool.",
    1: "Water bypasses filter and goes to drain. Used to lower water level.",
    2: "No water flow. Valve sealed.",
    3: "Reverse flow through filter to clean media. Water sent to drain.",
    4: "Water recirculates bypassing filter entirely. No filtration.",
    5: "Brief forward flow to drain after backwash to settle filter media.",
    6: "Valve position could not be determined.",
    7: "No multiway valve installed.",
}

# Descriptions for water level states
WATERLEVEL_STATE_DESCRIPTIONS: Final[dict[int, str]] = {
    0: "Water level sensor not installed.",
    1: "Water level low. Auto refill will start if enabled.",
    2: "Water level normal. No action required.",
    3: "Water level high. Reduction may occur if auto reduce is enabled.",
    4: "Water level sensor error. Check sensor wiring and condition.",
}

# Descriptions for forced filtration modes (from PoolCop Evolution manual §4.4.4.5.7)
FORCED_FILTRATION_DESCRIPTIONS: Final[dict[int, str]] = {
    0: "No forced filtration active. Normal timer cycles in effect.",
    1: "Pump forced on for 24h. Overrides Cycle 1 times, max 23h/day. Reverts when done.",
    2: "Pump forced on for 48h. Overrides Cycle 1 times, max 23h/day. Reverts when done.",
    3: "Pump forced on for 72h. Overrides Cycle 1 times, max 23h/day. Reverts when done.",
}

# Descriptions for pump types (from PoolCop Evolution manual §5.5)
PUMP_TYPE_DESCRIPTIONS: Final[dict[int, str]] = {
    0: "Pump type not configured.",
    1: "Single fixed speed. On/off control only.",
    2: "Two speed motor. Aux 1 controls high/low speed.",
    3: "Three speed motor. Aux 1-3 control speed selection.",
    4: "Variable speed drive. Continuous speed adjustment.",
    5: "Variable speed with 3-step control via aux relays.",
    6: "Pump controlled by external system. PoolCop does not control start/stop.",
}

# Descriptions for pool types
POOL_TYPE_DESCRIPTIONS: Final[dict[int, str]] = {
    0: "Standard skimmer pool. Surface water drawn through skimmers.",
    1: "Infinity edge pool, type A. Overflow to balance tank.",
    2: "Infinity edge pool, type B. Overflow to balance tank.",
    3: "Spa or hot tub. Typically smaller volume with higher turnover.",
}

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


# Alarm names (from cloud API enum PCFR.PoolCopilot.Xml.Alarm)
# The legacy API returns "alert_title_N" where N is the 0-based index.
ALARM_NAMES: Final[dict[int, str]] = {
    0: "None",
    1: "Freezing Risk",
    2: "Consumables Level Low (Disinfection)",
    3: "Pressure Low",
    4: "Pressure Zero",
    5: "pH Low",
    6: "pH High",
    7: "AutoChlor Acid Depleted",
    8: "Ioniser Copper Electrodes",
    9: "Cleaning Limit Reached",
    10: "Electrolyser Production Limited",
    11: "Ioniser Conductivity Error",
    12: "Water Level Sensor Cable Failure",
    13: "Valve Scan Error",
    14: "pH Out of Bounds",
    15: "Comm Bus Failure",
    16: "Comm Bus Timeout",
    17: "Pool Cover Open",
    18: "Valve Disk Failure",
    19: "Water Refill Timeout",
    20: "Battery Low",
    21: "Consumables Level Low (pH)",
    22: "Cleaning Cycle Aborted",
    23: "Valve Rotation Inhibited (High Pressure)",
    24: "Salt System Needs Attention",
    25: "Pressure Out of Bounds",
    26: "Cleaning Required",
    27: "Reduction Limit Reached",
    28: "Consumables Level Low",
    29: "Water Level Not Optimum",
    30: "Valve Rotation Inhibited (Water Ingress)",
    31: "Valve Position Not Reached",
    32: "Water Temperature Faulty",
    33: "ORP Out of Bounds",
    34: "Disinfection Stopped (Low Temperature)",
    35: "Disinfection Control Inefficient",
    36: "pH Control Inefficient",
    37: "Clock Not Running",
    38: "Free Available Chlorine Low",
    39: "Free Available Chlorine High",
    40: "Free Available Chlorine Error",
    41: "Manual Alarm",
    42: "Water No Flow Detected",
    43: "Free Available Chlorine Needs Maintenance",
    44: "Flow Rate Low",
    45: "Flow Rate High",
    46: "FAC Negative",
    47: "Free Available Chlorine Initial Calibration Required",
    48: "Free Available Chlorine Periodic Calibration Required",
    49: "Pressure Inhibited",
    50: "Freezing Risk (External)",
    51: "Consumables Level Low (Disinfection)",
    52: "Consumables Level Low (pH)",
    53: "Consumables Level Low",
    54: "Pool Cover Open",
    55: "Salt System Needs Attention",
    56: "Pump Start Request",
    57: "Pump Stop Request",
    58: "Jet Stream Button Activated",
    59: "Water Flow Switch Activated",
    60: "Flooding",
    61: "Flooding (Stop Filtration)",
    62: "Free Chlorine Sensor Low Flow",
    63: "Consumables Level Low (ACO)",
    64: "Consumables Level Low (Flocculant)",
    65: "Overflow Requested",
    66: "Open Cover Button Activated",
    67: "Close Cover Button Activated",
    68: "Water Flow Switch for Electrolyser Activated",
    69: "Aux Activated by Input",
}

# Alarm severity levels (from cloud API enum PCFR.PoolCopilot.Xml.AlarmSeverity)
ALARM_SEVERITIES: Final[dict[str, str]] = {
    "Remind": "Reminder",
    "Warning": "Warning",
    "Error": "Error",
    "Failure": "Failure",
}


def alert_title_id(api_name: str) -> int | None:
    """Extract the numeric alarm ID from an API alert string like 'alert_title_5'."""
    if api_name and api_name.startswith("alert_title_"):
        try:
            return int(api_name.removeprefix("alert_title_"))
        except ValueError:
            pass
    return None


def alert_display_name(api_name: str) -> str:
    """Resolve an API alert name to a human-readable name.

    The API returns "alert_title_N" where N is the numeric alarm code.
    Maps to a human-readable name via ALARM_NAMES.
    """
    alarm_id = alert_title_id(api_name)
    if alarm_id is not None:
        return ALARM_NAMES.get(alarm_id, f"Alarm {alarm_id}")
    return api_name or "Unknown Alarm"


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
