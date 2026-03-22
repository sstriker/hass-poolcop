# PoolCop Integration for Home Assistant

Custom component for the [PoolCop](https://www.poolcop.com/) pool automation system, using the PoolCop Cloud API.

> **Status:** This branch (`aiopoolcop`) is a rewrite targeting the new Cloud API with OAuth2 authentication. It requires OAuth2 client credentials from PCFR, which are being arranged.

## Features

- **Sensors:**
  - Water and air temperature
  - pH and ORP (Oxidation-Reduction Potential) readings
  - Pressure readings
  - Water level status
  - Pump speed, valve position, and operation mode
  - Forced filtration status and remaining time
  - Free available chlorine
  - Daily filtration volume and turnovers (computed from pump runtime)
  - Planned remaining filter volume and turnovers
  - Cycle tracking: elapsed time, remaining time, predicted end
  - Diagnostic sensors for pool, pump, filter, pH, ORP settings (from config endpoints)
  - History sensors: last backwash, refill, pH measure dates
  - Pool nickname

- **Binary Sensors:**
  - Pump running state
  - Active alarms (with alarm details in attributes)
  - Mains power lost
  - Equipment installed flags (pH, ORP, water level, air temperature)

- **Controls:**
  - Pump on/off switch
  - Auxiliary output switches (pool lights, water features, etc.)
  - Valve position selector
  - Pump speed selector
  - Clear alarm button

- **Device Tracker:**
  - Pool location on the map (from GPS coordinates)
  - Pool nickname shown on map hover

- **Smart Polling:**
  - Configurable update interval with automatic backoff on rate limits
  - Configuration endpoints fetched less frequently (every 30 minutes)
  - Cycle duration learning for better end-time predictions

## Installation

### HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed
2. Add this repository as a custom repository in HACS
3. Install the "PoolCop" integration through HACS
4. Restart Home Assistant

### Manual

1. Download the latest release
2. Extract `custom_components/poolcop` to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Prerequisites

1. A PoolCop device linked to your [poolcopilot.com](https://poolcopilot.com) account
2. OAuth2 client credentials (Client ID and Client Secret) — contact PCFR to obtain these

## Setup

1. Go to **Settings** > **Devices & Services** > **Application Credentials**
2. Add credentials for "PoolCop" with the Client ID and Client Secret from PCFR
3. Go to **Settings** > **Devices & Services** > **+ Add Integration** and search for "PoolCop"
4. You will be redirected to poolcopilot.com to authorize access
5. Select your PoolCop device (if you have multiple)
6. Configure pump flow rates for each speed level (used for volume/turnover calculations)

## Services

- `poolcop.set_pump` — turn pump on/off
- `poolcop.set_pump_speed` — set speed (Speed1, Speed2, Speed3)
- `poolcop.set_auxiliary` — turn an auxiliary output on/off
- `poolcop.set_valve_position` — set valve position (Filter, Waste, Backwash, etc.)
- `poolcop.clear_alarm` — clear a specific alarm by code

## Architecture

This integration uses:

- **[aiopoolcop](https://github.com/sstriker/python-aiopoolcop)** — async Python client for the PoolCop Cloud API (`cloud.api.poolcop.net`)
- **OAuth2 Authorization Code flow** via `poolcopilot.com/oauth2/` for authentication
- Home Assistant's built-in `application_credentials` platform for token management and automatic refresh

## Troubleshooting

- If sensors show "unavailable," check that your OAuth2 credentials are valid and your PoolCop is online
- The integration automatically refreshes OAuth2 tokens — if auth fails, re-authenticate via the integration page
- Check Home Assistant logs for detailed error information
