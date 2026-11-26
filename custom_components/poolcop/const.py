"""Constants for the PoolCop integration."""

from __future__ import annotations

import logging
import re
from typing import Final

DOMAIN: Final = "poolcop"
LOGGER = logging.getLogger(__package__)

# Update interval (in seconds)
# Initial interval used before the first API response provides quota data.
# After each call, interval is dynamically adjusted: time_to_renewal / remaining_quota.
UPDATE_INTERVAL = 15

# Dynamic interval bounds (in seconds)
MIN_UPDATE_INTERVAL = 10  # Floor: never poll faster than every 10s
MAX_UPDATE_INTERVAL = 120  # Ceiling: never wait longer than 2 minutes

# User-configurable polling interval (options flow)
CONF_POLL_INTERVAL = "poll_interval"

# Storage constants
STORAGE_KEY = "poolcop_learned_data"
STORAGE_VERSION = 1

# Configuration constants for flow rates based on pump speed levels (1, 2, 3)
CONF_FLOW_RATE_1 = "flow_rate_1"  # Low speed
CONF_FLOW_RATE_2 = "flow_rate_2"  # Medium speed
CONF_FLOW_RATE_3 = "flow_rate_3"  # High speed

# Map mode
CONF_MAP_MODE = "map_mode"
MAP_MODE_ALWAYS = "always"
MAP_MODE_ATTENTION = "attention"

# Services
SERVICE_SET_PUMP_SPEED = "set_pump_speed"
SERVICE_TOGGLE_PUMP = "toggle_pump"
SERVICE_TOGGLE_AUX = "toggle_aux"
SERVICE_SET_VALVE_POSITION = "set_valve_position"
SERVICE_CLEAR_ALARM = "clear_alarm"
SERVICE_STOP_BACKWASH = "stop_backwash"
SERVICE_SET_FILTRATION_MODE = "set_filtration_mode"
SERVICE_SET_FILTRATION_TIMERS = "set_filtration_timers"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"

# Client API rate limits (seconds). Requests on the same device must be
# 10 s apart, except the pump state, valve position and auxiliary state
# commands, which only need the 1 s per-key spacing the client applies.
# The API measures the 10 s itself and refused a read sent exactly 10 s after
# a command, so leave a margin.
ENTITY_RATE_LIMIT = 12.0

# A 429 whose Retry-After is at most this many seconds is waited out and the
# request sent once more, instead of failing.
RATE_LIMIT_RETRY_MAX = 5.0

# The first request after a quiet period can take more than 15 s to answer.
REQUEST_TIMEOUT = 45.0

# Commands are accepted with HTTP 202 and take 30 s to 2 min to show up in
# the device state. Entities show the requested state until then.
PENDING_COMMAND_TIMEOUT = 150.0

# Filtration modes accepted by the filtrationtimer command. Forced24H/48H/72H
# are set through the forced filtration select instead.
FILTRATION_MODES: Final = [
    "Stop",
    "Timer",
    "EcoPlus",
    "Volume",
    "Continuous",
    "Mode24H",
]

# Where users generate a Client API key
API_KEY_URL: Final = "https://my.poolcop.com/profile/apikey"

# Repair issue raised when a 2.x (PoolCopilot API) entry is migrated
ISSUE_NEW_API_KEY = "new_api_key"

# Entities from 2.x (PoolCopilot API) that the Client API no longer provides,
# as (platform, key). Removed from the entity registry by the v2 -> v3 migration.
REMOVED_ENTITY_KEYS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("binary_sensor", "autochlor_acid"),
        ("binary_sensor", "autochlor_auto"),
        ("binary_sensor", "autochlor_control"),
        ("binary_sensor", "autochlor_installed"),
        ("binary_sensor", "ioniser_control"),
        ("binary_sensor", "ioniser_installed"),
        ("binary_sensor", "ioniser_mode"),
        ("binary_sensor", "orp_control_enabled"),
        ("binary_sensor", "watervalve"),
        ("sensor", "autochlor_duration"),
        ("sensor", "autochlor_next_injection"),
        ("sensor", "filter_mode"),
        ("sensor", "forced_filtration_mode"),
        ("sensor", "forced_filtration_remaining"),
        ("sensor", "ioniser"),
        ("sensor", "ioniser_current"),
        ("sensor", "ioniser_duration"),
        ("sensor", "ioniser_next_injection"),
        ("sensor", "orp_hyper_day"),
        ("sensor", "orp_hyper_set_point"),
        ("sensor", "orp_next_injection"),
        ("sensor", "ph_next_injection"),
        ("sensor", "refill_status"),
        ("sensor", "waterlevel_cable_status"),
    }
)

# Entities whose 3.0 counterpart has a different key, as
# (platform, old key) -> new key. They keep their entity ID and history.
RENAMED_ENTITY_KEYS: Final[dict[tuple[str, str], str]] = {
    ("sensor", "poolcop"): "running_status",
}

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
    6: "Error (Position)",
    7: "Error (Rotation)",
    8: "Error (No Disk)",
    9: "Rotating",
}

WATERLEVEL_STATES = {
    0: "Faulty",
    1: "Low",
    2: "Normal",
    3: "High",
    4: "Very High",
}

WATER_VALVE_POSITIONS = {
    0: "Closed",
    1: "Open",
    2: "Measuring",
}

# Water level valve states (from cloud API enum WaterLevelValve)
WATERVALVE_STATES = {0: "Closed", 1: "Open", 2: "Measuring"}

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

# Pump types (from PoolCop Evolution manual §5.6.2 Pump Data)
PUMP_TYPES = {
    0: "Single Speed",
    1: "Pentair IntelliComm",
    2: "Pentair SuperFlo VS",
    3: "Hayward Eco Star",
    4: "Hayward Range VSTD",
    5: "Badu Eco Touch-Pro",
    6: "Badu 90 Eco Motion",
    7: "Zodiac FloPro VS",
    8: "Invertek OptiDrive",
    9: "Binary Combination",
    10: "Davey ProMaster VSD400",
    11: "ACIS VIPool MKB",
    12: "DAB E.Swim / E.Pro",
    13: "Aquagem / Pahlen",
    14: "SACI Epool Ejoy",
    15: "Schneider ATV212",
    16: "No Pump",
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
    9: "No Pump",
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
    9: "No pump installed. Filtration not controlled by PoolCop.",
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
    0: "Read Only",
    1: "Chlorine",
    2: "Salt",
    3: "Bromine",
    4: "PoolCop Ocean",
    5: "DA Space",
    6: "DA Gen",
    7: "Aquark",
}

# Descriptions for disinfectant types
DISINFECTANT_TYPE_DESCRIPTIONS: Final[dict[int, str]] = {
    0: "Read and display ORP only. No dosing control.",
    1: "Liquid chlorine injection. Controlled by ORP sensor.",
    2: "Salt water chlorinator. External system controlled.",
    3: "Bromine dosing. Controlled by ORP sensor.",
    4: "PoolCop Ocean integrated disinfection system.",
    5: "Dryden Aqua DA Space disinfection system.",
    6: "Dryden Aqua DA Gen disinfection system.",
    7: "Aquark disinfection system.",
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
    8: "Water Level Management",
    9: "24/24",
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
    8: "Water level management in progress. Refill or reduction active.",
    9: "24/24 continuous mode. Pump runs non-stop.",
}

# Running status modes where filtration cycles are active and cycle sensors are relevant
CYCLE_ACTIVE_MODES: Final[set[int]] = {2, 3, 4, 9}

# Descriptions for valve positions (from PoolCop Evolution manual §4.4.4)
VALVE_POSITION_DESCRIPTIONS: Final[dict[int, str]] = {
    0: "Normal operation. Water flows through filter media to pool.",
    1: "Water bypasses filter and goes to drain. Used to lower water level.",
    2: "No water flow. Valve sealed.",
    3: "Reverse flow through filter to clean media. Water sent to drain.",
    4: "Water recirculates bypassing filter entirely. No filtration.",
    5: "Brief forward flow to drain after backwash to settle filter media.",
    6: "Valve position error. Position could not be determined.",
    7: "Valve rotation error. Rotation failed.",
    8: "Valve error. No disk detected.",
    9: "Valve is currently rotating to target position.",
}

# Descriptions for water level states
WATERLEVEL_STATE_DESCRIPTIONS: Final[dict[int, str]] = {
    0: "Water level sensor faulty. Check sensor wiring and condition.",
    1: "Water level low. Auto refill will start if enabled.",
    2: "Water level normal. No action required.",
    3: "Water level high. Reduction may occur if auto reduce is enabled.",
    4: "Water level very high. Draining may occur if auto reduce is enabled.",
}

# Descriptions for forced filtration modes (from PoolCop Evolution manual §4.4.4.5.7)
FORCED_FILTRATION_DESCRIPTIONS: Final[dict[int, str]] = {
    0: "No forced filtration active. Normal timer cycles in effect.",
    1: "Pump forced on for 24h. Overrides Cycle 1 times, max 23h/day. Reverts when done.",
    2: "Pump forced on for 48h. Overrides Cycle 1 times, max 23h/day. Reverts when done.",
    3: "Pump forced on for 72h. Overrides Cycle 1 times, max 23h/day. Reverts when done.",
}

# Descriptions for pump types (from PoolCop Evolution manual §5.6.2 Pump Data)
PUMP_TYPE_DESCRIPTIONS: Final[dict[int, str]] = {
    0: "Single fixed speed. On/off control only.",
    1: "Pentair IntelliComm variable speed pump.",
    2: "Pentair SuperFlo VS variable speed pump.",
    3: "Hayward Eco Star variable speed pump.",
    4: "Hayward Range VSTD variable speed pump.",
    5: "Speck Badu Eco Touch-Pro variable speed pump.",
    6: "Speck Badu 90 Eco Motion variable speed pump.",
    7: "Zodiac FloPro VS variable speed pump.",
    8: "Invertek OptiDrive variable frequency drive.",
    9: "Binary combination speed control via aux relays.",
    10: "Davey ProMaster VSD400 variable speed pump.",
    11: "ACIS VIPool MKB variable speed pump.",
    12: "DAB E.Swim / E.Pro variable speed pump.",
    13: "Aquagem / Pahlen variable speed pump.",
    14: "SACI Epool Ejoy variable speed pump.",
    15: "Schneider ATV212 variable frequency drive.",
    16: "No pump installed. PoolCop does not control filtration.",
}

# Descriptions for pool types
POOL_TYPE_DESCRIPTIONS: Final[dict[int, str]] = {
    0: "Standard skimmer pool. Surface water drawn through skimmers.",
    1: "Infinity edge pool, type A. Overflow to balance tank.",
    2: "Infinity edge pool, type B. Overflow to balance tank.",
    3: "Spa or hot tub. Typically smaller volume with higher turnover.",
}

# Auxiliary output labels: the Client API's Auxiliary.label values and the
# names shown for them. A friendly name set on the PoolCop takes precedence.
AUX_LABEL_NAMES: Final[dict[str, str]] = {
    "PoolLight": "Pool Light",
    "PoolCleaner": "Pool Cleaner",
    "Heating": "Pool Heating",
    "Disinfection": "Disinfection",
    "Electrolyser": "Electrolyser",
    "Remnant": "Remnant",
    "TransferPump": "Transfer Pump",
    "UV": "UV",
    "Spa": "Spa",
    "Fountain": "Fountain",
    "Borehole": "Borehole",
    "PoolHouse": "Pool House",
    "Garden": "Garden",
    "Garden1": "Garden 1",
    "Garden2": "Garden 2",
    "Garden3": "Garden 3",
    "Available": "Available",
    "NotUsed": "Not Used",
    "ReservedACO": "ACO Dosing",
    "ReservedAuxAlarm": "External Warnings",
    "ReservedCleaningValve": "Cleaning Valve",
    "ReservedCover": "Pool Cover",
    "ReservedFloculant": "Flocculant Dosing",
    "ReservedJetStream": "Jet Stream",
    "ReservedORP": "ORP Control",
    "ReservedPumpControl": "Pump Control",
    "ReservedPumpSpeedControl": "Pump Speed Control",
    "ReservedRemnant": "Remnant",
    "ReservedRince": "Rinsing Valve",
    "ReservedSpeedControl": "Speed Control",
    "ReservedSuction": "Suction Valve",
    "ReservedValveCleaning": "Cleaning Valve",
    "ReservedWasteValve": "Waste Valve",
}

# Outputs the firmware drives for a function that has its own entities
# (pump speed, ORP dosing, waste valve).
AUX_FIXED_FUNCTION_LABELS: Final[frozenset[str]] = frozenset(
    {
        "ReservedORP",
        "ReservedPumpSpeedControl",
        "ReservedSpeedControl",
        "ReservedWasteValve",
    }
)

# Valve outputs: OPENING device class (open/closed)
AUX_VALVE_LABELS: Final[frozenset[str]] = frozenset(
    {
        "ReservedCleaningValve",
        "ReservedRince",
        "ReservedSuction",
        "ReservedValveCleaning",
        "ReservedWasteValve",
    }
)

# Relay outputs with their own entities: POWER device class (on/off)
AUX_RELAY_LABELS: Final[frozenset[str]] = frozenset(
    {"ReservedORP", "ReservedPumpSpeedControl", "ReservedSpeedControl"}
)

# (on icon, off icon) per label
AUX_LABEL_ICONS: Final[dict[str, tuple[str, str]]] = {
    "PoolLight": ("mdi:lightbulb-on", "mdi:lightbulb-off"),
    "PoolCleaner": ("mdi:robot-vacuum", "mdi:robot-vacuum-off"),
    "Heating": ("mdi:heating-coil", "mdi:heating-coil"),
    "Disinfection": ("mdi:bottle-tonic-skull", "mdi:bottle-tonic-skull-outline"),
    "Electrolyser": ("mdi:flash", "mdi:flash-off"),
    "TransferPump": ("mdi:pump", "mdi:pump-off"),
    "UV": ("mdi:weather-sunny", "mdi:weather-sunny-off"),
    "Spa": ("mdi:hot-tub", "mdi:hot-tub"),
    "Fountain": ("mdi:fountain", "mdi:fountain"),
    "Borehole": ("mdi:water-well", "mdi:water-well-outline"),
    "PoolHouse": ("mdi:home", "mdi:home-outline"),
    "Garden": ("mdi:sprinkler", "mdi:sprinkler-variant"),
    "Garden1": ("mdi:sprinkler", "mdi:sprinkler-variant"),
    "Garden2": ("mdi:sprinkler", "mdi:sprinkler-variant"),
    "Garden3": ("mdi:sprinkler", "mdi:sprinkler-variant"),
    "ReservedCover": ("mdi:window-shutter", "mdi:window-shutter-open"),
    "ReservedJetStream": ("mdi:waves-arrow-right", "mdi:waves-arrow-right"),
    "ReservedAuxAlarm": ("mdi:alert", "mdi:alert-outline"),
    "ReservedACO": ("mdi:beaker", "mdi:beaker-outline"),
    "ReservedFloculant": ("mdi:beaker", "mdi:beaker-outline"),
}


def aux_display_name(label: str, friendly_name: str, channel: int) -> str:
    """Return the name to show for an auxiliary output."""
    return friendly_name or AUX_LABEL_NAMES.get(label) or label or f"Aux {channel}"


def alarm_display_name(code: str) -> str:
    """Return a readable alarm name: PressureLowPump1 -> Pressure Low Pump 1."""
    return re.sub(
        r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[a-zA-Z])(?=[0-9])",
        " ",
        code,
    )
