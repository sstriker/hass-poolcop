# PoolCop Integration for Home Assistant

Monitor and control a [PoolCop](https://www.poolcop.com) pool controller from
Home Assistant: water quality, filtration, valve, pump, auxiliary outputs and
alarms.

The integration uses the official PoolCop Client API
(`client-api.poolcop.net`) through the
[aiopoolcop](https://pypi.org/project/aiopoolcop/) library.

> **Upgrading from 2.x?** Version 3.0 replaces the PoolCopilot API, which shuts
> down at the end of November 2026. You need a **new API key**; see
> [Upgrading from 2.x](#upgrading-from-2x).

## Requirements

- Home Assistant 2026.9 or newer
- A PoolCop connected to the PoolCop cloud, with active cloud access
- A PoolCop Client API key (see below)

## Getting an API key

1. Log in to [MyPoolCop](https://my.poolcop.com) with your PoolCop account.
2. Open **Profile → API key**
   ([my.poolcop.com/profile/apikey](https://my.poolcop.com/profile/apikey)).
3. Click **Generate a key** and copy it.

One key gives access to every PoolCop on your account. Generating a new key
invalidates the old one, so update Home Assistant afterwards (see
[Changing the API key](#changing-the-api-key)). Keep the key private: it can
control your pool.

Keys for the old PoolCopilot API (poolcopilot.com) do **not** work.

## Installation

### HACS (recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed.
2. Add `https://github.com/sstriker/hass-poolcop` as a custom repository
   (category: Integration).
3. Install **PoolCop** and restart Home Assistant.

### Manual

1. Download the latest release.
2. Copy `custom_components/poolcop` into your Home Assistant
   `custom_components` directory.
3. Restart Home Assistant.

## Setup

1. Go to **Settings → Devices & services → Add integration** and search for
   **PoolCop**.
2. Enter your API key.
3. If your account has more than one PoolCop, choose the one to add. Add the
   others the same way; PoolCops that are already set up are not offered again.
4. Enter your pump's flow rate at each speed (m³/h). It is used to calculate the
   filtered volume and turnovers; the PoolCop's own estimate is pre-filled.

### Options

**Settings → Devices & services → PoolCop → Configure**:

| Option | Description |
| --- | --- |
| Pool on the map | Always show the pool on the map, or only when it needs attention (alarm or problem). |
| Flow rate at speed 1–3 | Pump flow rate per speed, in m³/h. |

### Changing the API key

Use **Reconfigure** on the PoolCop entry. If PoolCop rejects the key,
Home Assistant asks for a new one by itself (re-authentication). Either way the
key must belong to the account that owns the PoolCop.

## What you get

Each PoolCop becomes a device with:

- **Sensors:** water and air temperature, pH, ORP, pressure, water level,
  salt and chlorine (when installed), pump speed, valve position, running
  status, filtration mode, forced filtration time left, filtration cycle times,
  backwash and refill history, alarms and firmware details.
- **Calculated sensors:** current flow rate, filtered volume and turnovers
  today, planned remaining volume and turnovers, cycle elapsed and remaining
  time and predicted end.
- **Binary sensors:** pump running, active alarm, auxiliary outputs that can't
  be switched, inputs, water level flags, pool cover, installed equipment.
- **Switches:** pump, jet stream (when installed), switchable auxiliary outputs
  (named after their PoolCop label, such as Pool Light).
- **Selects:** pump speed, valve position, filtration mode, forced filtration
  (24, 48 or 72 hours).
- **Buttons:** clear alarms, stop backwash.
- **Map:** the pool location (optional, see Options).
- **Diagnostics:** download from the device page; the API key and location
  are redacted.

Entities only appear for equipment the PoolCop reports as installed. Entity
names and states are translated (English and Dutch).

## Actions

All actions take an optional `config_entry_id` to choose the PoolCop. It is
only required when more than one PoolCop is set up.

| Action | Fields | What it does |
| --- | --- | --- |
| `poolcop.set_pump_speed` | `speed` (0–8, 0 = off) | Set the pump speed. |
| `poolcop.toggle_pump` | | Turn the pump on if off, off if on. |
| `poolcop.toggle_aux` | `aux_id`, `module` (default `None`) | Toggle an auxiliary output. |
| `poolcop.set_valve_position` | `position` (filter, waste, closed, backwash, bypass, rinse) | Turn the multiport valve. |
| `poolcop.clear_alarm` | `alarm_code` (optional) | Clear one alarm, or all alarms. |
| `poolcop.stop_backwash` | | Stop a backwash in progress. |
| `poolcop.set_filtration_mode` | `mode` (stop, timer, eco_plus, volume, continuous, mode_24h) | Set the filtration mode, keeping the cycle times. |
| `poolcop.set_filtration_timers` | `mode`, `cycle_1_enabled`, `cycle_1_start`, `cycle_1_end`, `cycle_2_…` | Change the filtration cycles; anything left out keeps its value. |

Example: run cycle 1 from 08:00 to 12:00 in timer mode.

```yaml
action: poolcop.set_filtration_timers
data:
  mode: timer
  cycle_1_enabled: true
  cycle_1_start: "08:00:00"
  cycle_1_end: "12:00:00"
```

Example automation: start a 24-hour forced filtration after a heavy rain
warning.

```yaml
automation:
  - alias: Forced filtration after storm
    triggers:
      - trigger: state
        entity_id: binary_sensor.storm_warning
        to: "on"
    actions:
      - action: select.select_option
        target:
          entity_id: select.my_pool_forced_filtration
        data:
          option: forced_24h
```

## How data is updated

- The PoolCop is polled every 15 seconds; pool details (location, time zone)
  every 30 minutes.
- PoolCop applies commands with a delay of **30 seconds to 2 minutes**.
  Switches and selects show the requested state straight away and keep it
  until the PoolCop reports it (or 2.5 minutes pass).
- The Client API allows one request per second per key and 10 seconds between
  requests for the same PoolCop (pump, valve and auxiliary commands are
  exempt). The integration spaces its requests to stay within these limits,
  so a command can take up to 10 seconds to be sent.
- Values use the units chosen in your PoolCop app preferences (for example
  °F, psi or gallons); Home Assistant converts them to your unit system.

## Known limitations

- Commands are not instant (see above), and PoolCop can reject a command that
  doesn't fit the current state, for example a valve change during a
  backwash.
- The flow rate per speed is entered by you; filtered volume and turnovers are
  only as accurate as those numbers (a PoolCop flow meter is used when
  installed).
- Ioniser and AutoChlor data are not available through the Client API.
- Only the first pump and filtration system of a PoolCop are supported.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| "Invalid API key" | Generate a new key in MyPoolCop (Profile → API key). PoolCopilot keys don't work. |
| "This API key cannot access this PoolCop" | Use a key from the account that owns the PoolCop. |
| Repair: "PoolCop cloud access expired" | Renew the cloud access in MyPoolCop or with your dealer. |
| Entities unavailable | Check that the PoolCop is online in MyPoolCop. Rate-limit errors in the log usually clear by themselves. |
| A command "doesn't work" | Wait up to 2 minutes; check the PoolCop's command history in MyPoolCop. |

When reporting a problem, attach the diagnostics file (device page → Download
diagnostics) and enable debug logging:

```yaml
logger:
  logs:
    custom_components.poolcop: debug
    aiopoolcop: debug
```

## Upgrading from 2.x

1. Generate a Client API key (see [Getting an API key](#getting-an-api-key)).
2. Update the integration to 3.0 and restart Home Assistant.
3. Home Assistant shows a repair notice and asks you to re-authenticate the
   PoolCop: enter the new key.

Your PoolCop keeps its device and entity IDs and history. What changes:

- Entities that the Client API no longer provides are removed: ioniser,
  AutoChlor, ORP hyper-chlorination and next-injection times, water valve,
  refill status, water level cable status, filter mode and the old forced
  filtration mode and remaining sensors.
- The old **Operation Mode** sensor becomes **Running Status**, with new state
  values (for example `timer_mode`, `eco_plus_mode`).
- Select options are now lower-case keys: `filter`, `speed_2`, `forced_24h`,
  `not_forced`. Update automations that set or compare them.
- Actions take an optional `config_entry_id`; `set_pump_speed` takes 0–8.
- Home Assistant 2026.9 or newer is required.

## Removing the integration

Go to **Settings → Devices & services → PoolCop**, open the menu (⋮) of the
entry and choose **Delete**. To revoke Home Assistant's access, generate a new
API key in MyPoolCop; this invalidates the old one.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) and [DEVELOPMENT.md](DEVELOPMENT.md).
