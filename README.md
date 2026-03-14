# PoolCop Integration for Home Assistant

This custom component adds support for the PoolCop pool automation system to Home Assistant.

## Overview

PoolCop is an advanced pool automation system that monitors and controls essential pool equipment and water parameters. This integration allows you to monitor and control your PoolCop system directly from Home Assistant.

## Features

- **Sensors:**
  - Water and air temperature
  - pH and ORP (Oxidation-Reduction Potential) readings
  - Pressure readings
  - Water level status
  - Pump speed and flow rate (computed from speed + configured rates)
  - Valve position and operation mode
  - Forced filtration status and remaining time
  - Daily filtration volume and turnovers (accumulated from pump runtime)
  - Planned remaining filter volume and turnovers (projected from cycle timers)
  - Cycle tracking: elapsed time, remaining time, predicted end
  - Timer sensors for filtration cycles and auxiliary schedules
  - Diagnostic sensors for pool, pump, filter, pH, ORP, and ioniser settings

- **Binary Sensors:**
  - Pump running state
  - Active alarms
  - pH and ORP control status
  - Water valve state
  - Auxiliary output states (with automatic labelling)
  - Network connectivity

- **Controls:**
  - Pump on/off switch
  - Auxiliary output switches (pool lights, water features, etc.)
  - Forced filtration mode selector (off, 24h, 48h, 72h)
  - Clear alarm button

- **Services:**
  - `poolcop.toggle_pump` — toggle the pump on/off
  - `poolcop.set_pump_speed` — set speed (1-3)
  - `poolcop.toggle_aux` — toggle an auxiliary output (1-6)
  - `poolcop.set_valve_position` — set valve position (1-6)
  - `poolcop.clear_alarm` — clear active alarms
  - `poolcop.set_force_filtration` — set forced filtration mode

- **Device Tracker:**
  - Pool location on the map (from PoolCopilot GPS coordinates)
  - Pool image from PoolCopilot

- **Smart Polling:**
  - Dynamic interval: `time_to_key_renewal / remaining_quota` — evenly distributes API calls across the quota window (10s–120s range)
  - Automatic exponential backoff on rate limit errors
  - Learns cycle durations for better end-time predictions

## Installation

### HACS Installation (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed
2. Add this repository as a custom repository in HACS
3. Install the "PoolCop" integration through HACS
4. Restart Home Assistant

### Manual Installation

1. Download the latest release
2. Extract the `custom_components/poolcop` directory to your Home Assistant's `custom_components` directory
3. Restart Home Assistant

## Setup

1. Go to **Settings** > **Devices & Services**
2. Click **+ Add Integration** and search for "PoolCop"
3. Enter your PoolCopilot API key (available from [poolcopilot.com/api](https://poolcopilot.com/api))
4. Configure pump flow rates for each speed level (used for volume/turnover calculations)
5. Click **Submit**

## API Key

An API key is required to authenticate with the PoolCopilot API. You can obtain an API key by:

1. Creating an account at [poolcopilot.com](https://poolcopilot.com)
2. Linking your PoolCop device
3. Requesting an API key from the API section
