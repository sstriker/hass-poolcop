# PoolCop Integration for Home Assistant

This custom component adds support for the PoolCop pool automation system to Home Assistant.

## Overview

PoolCop is an advanced pool automation system that monitors and controls essential pool equipment and water parameters. This integration allows you to monitor and control your PoolCop system directly from Home Assistant.

## Features

- **Comprehensive Sensor Data:**
  - Water and air temperature
  - pH and ORP (Oxidation-Reduction Potential) readings with setpoints
  - Pressure readings
  - Water level status
  - Pump status and speed
  - Valve positions
  - Filtration times and statistics
  - System operation mode
  - Running status
  - Forced filtration status and remaining time

- **Control Capabilities:**
  - Toggle pump on/off
  - Set pump speed (for variable speed pumps)
  - Toggle auxiliary outputs (pool lights, water features, etc.)
  - Set valve position
  - Clear alarms
  - Set forced filtration mode (24h, 48h, or 72h)

- **Configuration Support:**
  - Custom auxiliary names from PoolCop configuration are automatically used
  - Installed equipment detection (pH control, ORP control, ionizer, etc.)

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
4. Click **Submit**

## API Key

An API key is required to authenticate with the PoolCopilot API. You can obtain an API key by:

1. Creating an account at [poolcopilot.com](https://poolcopilot.com)
2. Linking your PoolCop device
3. Requesting an API key from the API section

## Services

The integration provides several services to control your PoolCop system:

- `poolcop.toggle_pump`: Toggle the pump on/off
- `poolcop.set_pump_speed`: Set the pump speed (1-3)
- `poolcop.toggle_aux`: Toggle an auxiliary output (1-6)
- `poolcop.set_valve_position`: Set the valve position (1-6)
- `poolcop.clear_alarm`: Clear active alarms
- `poolcop.set_force_filtration`: Set forced filtration mode (24, 48, or 72 hours)

## Troubleshooting

- If sensors show "unavailable," ensure your API key is correct and your PoolCop system is online
- The integration refreshes data approximately every 12 seconds to respect API rate limits
- Check Home Assistant logs for detailed error information