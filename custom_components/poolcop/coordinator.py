"""The Coordinator for PoolCop."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from aiopoolcop import (
    Pool,
    PoolCopClientAPI,
    PoolCopClientAuthError,
    PoolCopClientConnectionError,
    PoolCopClientRateLimitError,
    PoolCopDevice,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    ConfigEntryAuthFailed,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
    CONF_POLL_INTERVAL,
    DOMAIN,
    LOGGER,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    STORAGE_KEY,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
)

# Mode name -> numeric ID mapping for cycle tracking.
# The client API returns string running_status values; we map them to the
# same numeric codes that the legacy API used so all the cycle-duration
# prediction logic continues to work unchanged.
MODE_NAME_TO_ID: dict[str, int] = {
    "Stopped": 0,
    "FreezeProtection": 1,
    "ForcedMode": 2,
    "EcoPlusMode": 3,
    "TimerMode": 4,
    "Manual": 5,
    "Paused": 6,
    "ExternalRequest": 7,
    "WaterLevelManagement": 8,
    "Mode24H": 9,
}

# Valve position name -> numeric ID mapping.
VALVE_NAME_TO_ID: dict[str, int] = {
    "Filter": 0,
    "Waste": 1,
    "Closed": 2,
    "Backwash": 3,
    "Bypass": 4,
    "Rinse": 5,
}

# Speed name -> numeric level mapping.
SPEED_NAME_TO_LEVEL: dict[str, int] = {
    "None": 0,
    "Speed1": 1,
    "Speed2": 2,
    "Speed3": 3,
    "Speed4": 4,
    "Speed5": 5,
    "Speed6": 6,
    "Speed7": 7,
    "Speed8": 8,
}

# Default cycle durations (in seconds)
DEFAULT_CYCLE_DURATIONS: dict[int, int] = {
    0: 0,  # Idle - no duration
    1: 7200,  # Cycle 1 - start with 2 hours as default
    2: 600,  # Backwash - start with 10 minutes as default
    3: 3600,  # Cycle 2 - start with 1 hour as default
    4: 900,  # Waste - start with 15 minutes as default
    5: 300,  # Rinse - start with 5 minutes as default
    6: 0,  # Pause - no predictable duration
    7: 0,  # External Filter - no predictable duration
}

# Interval for refreshing pool info (lat/lon/timezone) — 30 minutes.
_POOL_REFRESH_INTERVAL = 1800


@dataclass
class PoolCopData:
    """Container for data returned by the coordinator."""

    device: PoolCopDevice
    pool: Pool | None = None
    cycle_status: dict[str, Any] | None = None


class PoolCopDataUpdateCoordinator(DataUpdateCoordinator[PoolCopData]):
    """Class to manage fetching PoolCop data from the Client API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: PoolCopClientAPI,
        device_id: int,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize global PoolCop data updater."""
        # Determine polling interval: honour user option, fall back to default.
        poll_seconds = config_entry.options.get(CONF_POLL_INTERVAL, UPDATE_INTERVAL)
        poll_seconds = max(MIN_UPDATE_INTERVAL, min(MAX_UPDATE_INTERVAL, poll_seconds))

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_seconds),
        )
        self.api = api
        self.device_id = device_id

        # Initialize pump flow rates from options (preferred) or data (pre-migration)
        self.flow_rates: dict[int, float] = {}
        for speed, key in (
            (1, CONF_FLOW_RATE_1),
            (2, CONF_FLOW_RATE_2),
            (3, CONF_FLOW_RATE_3),
        ):
            value = config_entry.options.get(key, config_entry.data.get(key))
            if value is not None:
                self.flow_rates[speed] = value

        # Setup storage for persisting learned data
        self._store: Store = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY}_{device_id}"
        )

        # Daily filtration volume tracking
        self._daily_volume: float = 0.0  # m3 filtered today
        self._daily_volume_date: str | None = None  # YYYY-MM-DD of current accumulation
        self._last_flow_update: float | None = (
            None  # monotonic timestamp of last update
        )

        # Cycle tracking
        self._last_operation_mode: int | None = None
        self._current_cycle_start: float | None = None
        self._cycle_durations: dict[int, int] = dict(DEFAULT_CYCLE_DURATIONS)
        self._cycle_transitions: list[dict[str, Any]] = []

        # Pool info cache
        self._pool: Pool | None = None
        self._pool_last_fetch: float = 0.0

    # ------------------------------------------------------------------
    # Helpers to extract numeric values from typed models
    # ------------------------------------------------------------------

    def _pump(self, device: PoolCopDevice) -> Any:
        """Return the first pump info, or None."""
        if device.state.pumps:
            return device.state.pumps[0]
        return None

    def _mode_id(self, device: PoolCopDevice) -> int | None:
        """Return numeric operation-mode ID from the device running_status."""
        pump = self._pump(device)
        if pump is None:
            return None
        return MODE_NAME_TO_ID.get(pump.running_status)

    def _speed_level(self, device: PoolCopDevice) -> int | None:
        """Return numeric speed level (0-8) from pump current_speed."""
        pump = self._pump(device)
        if pump is None:
            return None
        return SPEED_NAME_TO_LEVEL.get(pump.current_speed)

    def _valve_id(self, device: PoolCopDevice) -> int | None:
        """Return numeric valve position ID."""
        pump = self._pump(device)
        if pump is None:
            return None
        return VALVE_NAME_TO_ID.get(pump.valve_position)

    def _pool_timezone(self) -> Any:
        """Return a zoneinfo timezone from pool data, or None."""
        if self._pool and self._pool.timezone:
            try:
                import zoneinfo

                return zoneinfo.ZoneInfo(self._pool.timezone)
            except (ImportError, KeyError):
                pass
        return None

    # ------------------------------------------------------------------
    # Flow rate / volume
    # ------------------------------------------------------------------

    def _flow_meter_rate(self, device: PoolCopDevice) -> float | None:
        """Return flow meter reading if a physical meter is installed and reporting."""
        if not device.equipments_info.has_flow_meter:
            return None
        if device.state.flow_vis:
            rate = device.state.flow_vis[0].flow_rate
            if rate is not None and rate > 0:
                return rate
        return None

    def get_current_flow_rate(self) -> float:
        """Return the current effective flow rate in m3/h.

        Prefers physical flow meter reading when available; falls back to
        configured speed-based rates.  Returns 0.0 if pump is off or valve
        is not in a flowing position.
        """
        if not hasattr(self, "data") or self.data is None:
            return 0.0

        device = self.data.device
        pump = self._pump(device)
        if pump is None:
            return 0.0

        # Pump must be on
        if not pump.pump_state:
            return 0.0

        # Valve must be in a position that moves water through the filter
        # 0=Filter, 4=Bypass (still flowing), 5=Rinse (flowing)
        valve_id = self._valve_id(device)
        if valve_id is not None and valve_id not in (0, 4, 5):
            return 0.0

        # Prefer physical flow meter when installed
        meter_rate = self._flow_meter_rate(device)
        if meter_rate is not None:
            return meter_rate

        # Fall back to configured speed-based rates
        speed_level = self._speed_level(device)
        if speed_level is None or speed_level == 0:
            return 0.0

        return self.flow_rates.get(speed_level, 0.0)

    def _update_daily_volume(self) -> None:
        """Accumulate filtered volume based on current flow rate and elapsed time."""
        now = time.monotonic()

        # Reset at midnight (check date string)
        try:
            today = datetime.now().strftime("%Y-%m-%d")
        except Exception:
            today = None

        if today and today != self._daily_volume_date:
            self._daily_volume = 0.0
            self._daily_volume_date = today

        if self._last_flow_update is not None:
            elapsed_seconds = now - self._last_flow_update
            # Sanity cap: skip if gap > 10 minutes (probably a restart)
            if 0 < elapsed_seconds <= 600:
                flow_rate = self.get_current_flow_rate()
                self._daily_volume += flow_rate * (elapsed_seconds / 3600.0)

        self._last_flow_update = now

    def _get_remaining_cycle_seconds(self, timer_index: int) -> float:
        """Return remaining filtration seconds for a cycle timer today.

        Uses the FiltrationTimer from device settings.  timer_index 0 = cycle 1,
        1 = cycle 2.
        """
        if not self.data or not self.data.device:
            return 0.0

        device = self.data.device
        # Get filtration settings for the first filtration group
        if not device.settings.filtrations:
            return 0.0
        filtration = device.settings.filtrations[0]

        if timer_index >= len(filtration.timers):
            return 0.0

        timer = filtration.timers[timer_index]
        if not timer.enabled:
            return 0.0

        start_str = timer.time_on
        stop_str = timer.time_off
        if (
            not start_str
            or not stop_str
            or start_str == "00:00:00"
            or stop_str == "00:00:00"
        ):
            return 0.0

        try:
            tz = self._pool_timezone()
            now = datetime.now(tz=tz)

            sh, sm, ss = map(int, start_str.split(":"))
            eh, em, es = map(int, stop_str.split(":"))

            start_dt = now.replace(hour=sh, minute=sm, second=ss, microsecond=0)
            stop_dt = now.replace(hour=eh, minute=em, second=es, microsecond=0)
        except (ValueError, TypeError):
            return 0.0

        # Ensure stop is after start (same-day cycle)
        if stop_dt <= start_dt:
            return 0.0

        if now >= stop_dt:
            return 0.0
        if now <= start_dt:
            return (stop_dt - start_dt).total_seconds()
        return (stop_dt - now).total_seconds()

    def _get_flow_rate_for_speed(self, speed: int | None) -> float:
        """Return flow rate for a given pump speed, with fallback.

        Prefers physical flow meter when installed.
        """
        if self.data:
            meter_rate = self._flow_meter_rate(self.data.device)
            if meter_rate is not None:
                return meter_rate
        if speed is not None:
            rate = self.flow_rates.get(speed, 0.0)
            if rate > 0:
                return rate
        # Fallback to current pump speed
        if self.data:
            current_speed = self._speed_level(self.data.device)
            if current_speed is not None:
                return self.flow_rates.get(current_speed, 0.0)
        # Last fallback: speed 1
        return self.flow_rates.get(1, 0.0)

    @property
    def planned_remaining_volume(self) -> float:
        """Return the planned remaining filtration volume in m3 for today."""
        if not self.data:
            return 0.0

        device = self.data.device
        op_mode = self._mode_id(device)
        if op_mode is None:
            return 0.0

        # Modes with no predictable planned filtration
        # 0=Stop, 1=Freeze, 5=Manual, 6=Paused, 7=External, 8=Water Level Mgmt
        if op_mode in (0, 1, 5, 6, 7, 8):
            return 0.0

        # Check the configured filter timer mode for modes that the
        # operating mode alone cannot distinguish.
        filtration = (
            device.settings.filtrations[0]
            if device.settings.filtrations
            else None
        )
        filter_timer_name = filtration.filtration_mode if filtration else None

        # Map filtration mode names to the legacy numeric filter-timer IDs
        # used below.  Only the two we need to distinguish here:
        is_always_on = filter_timer_name == "Continuous24"
        is_continuous = filter_timer_name == "Continuous" or op_mode == 9

        if is_always_on:
            return self._remaining_hours_volume()

        if is_continuous:
            return self._remaining_hours_volume()

        # Mode 2: Forced - use forced_remaining x flow rate
        if op_mode == 2:
            pump = self._pump(device)
            if pump is not None and pump.forced_remaining != "00:00:00":
                try:
                    parts = pump.forced_remaining.split(":")
                    remaining_hours = (
                        int(parts[0]) + int(parts[1]) / 60.0 + int(parts[2]) / 3600.0
                    )
                except (ValueError, IndexError):
                    remaining_hours = 0.0
                if remaining_hours > 0:
                    speed = self._speed_level(device)
                    flow = self._get_flow_rate_for_speed(speed)
                    return round(flow * remaining_hours, 3)
            return 0.0

        # Modes 3 (Auto), 4 (Timer) - use cycle timers
        if op_mode in (3, 4):
            total = 0.0
            for timer_idx, speed_attr in (
                (0, "speed_cycle1"),
                (1, "speed_cycle2"),
            ):
                remaining_secs = self._get_remaining_cycle_seconds(timer_idx)
                if remaining_secs > 0:
                    speed_name = (
                        getattr(filtration, speed_attr, "Speed1")
                        if filtration
                        else "Speed1"
                    )
                    speed = SPEED_NAME_TO_LEVEL.get(speed_name)
                    flow = self._get_flow_rate_for_speed(speed)
                    total += flow * (remaining_secs / 3600.0)
            return round(total, 3)

        return 0.0

    def _remaining_hours_volume(self) -> float:
        """Calculate volume from remaining hours today x current flow rate."""
        try:
            tz = self._pool_timezone()
            now = datetime.now(tz=tz) if tz else datetime.now()
            midnight = now.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)
            remaining_hours = (midnight - now).total_seconds() / 3600.0
            # Cap at 23 hours
            remaining_hours = min(remaining_hours, 23.0)
        except Exception:
            return 0.0

        speed = self._speed_level(self.data.device) if self.data else None
        flow = self._get_flow_rate_for_speed(speed)
        return round(flow * remaining_hours, 3)

    @property
    def planned_remaining_turnovers(self) -> float | None:
        """Return planned remaining turnovers (volume / pool_volume)."""
        if not self.data:
            return None
        pool_volume = self.data.device.settings.pool.volume
        if not pool_volume or pool_volume <= 0:
            return None
        return round(self.planned_remaining_volume / pool_volume, 2)

    @property
    def daily_volume(self) -> float:
        """Return the accumulated daily filtration volume in m3."""
        return round(self._daily_volume, 3)

    @property
    def daily_turnovers(self) -> float | None:
        """Return the number of pool turnovers today (1.0 = one full turnover)."""
        if not hasattr(self, "data") or self.data is None:
            return None
        pool_volume = self.data.device.settings.pool.volume
        if not pool_volume or pool_volume <= 0:
            return None
        return round(self._daily_volume / pool_volume, 2)

    # ------------------------------------------------------------------
    # Cycle tracking
    # ------------------------------------------------------------------

    def _update_cycle_tracking(self, device: PoolCopDevice) -> dict[str, Any]:
        """Track cycle changes and update predictions."""
        cycle_status: dict[str, Any] = {
            "previous_mode": self._last_operation_mode,
            "predicted_end": None,
            "elapsed_time": None,
            "remaining_time": None,
        }

        try:
            current_mode = self._mode_id(device)
            if current_mode is None:
                return cycle_status

            now = time.time()

            # Check if operation mode changed
            if (
                self._last_operation_mode != current_mode
                and self._last_operation_mode is not None
            ):
                # Record cycle transition data
                if self._current_cycle_start is not None:
                    cycle_duration = now - self._current_cycle_start

                    # Only update duration for non-idle/pause/external modes
                    if self._last_operation_mode in [1, 2, 3, 4, 5]:
                        # Update the average duration using exponential moving average
                        # Weight: 30% new, 70% old
                        old_duration = self._cycle_durations[self._last_operation_mode]
                        if old_duration > 0:
                            new_duration = int(
                                (0.3 * cycle_duration) + (0.7 * old_duration)
                            )
                            self._cycle_durations[self._last_operation_mode] = (
                                new_duration
                            )
                            LOGGER.debug(
                                "Updated duration for mode %s: %.1f minutes",
                                self._last_operation_mode,
                                new_duration / 60,
                            )

                    # Record transition for analysis
                    self._cycle_transitions.append(
                        {
                            "from_mode": self._last_operation_mode,
                            "to_mode": current_mode,
                            "duration": cycle_duration,
                            "timestamp": now,
                        }
                    )

                    # Keep only last 20 transitions
                    if len(self._cycle_transitions) > 20:
                        self._cycle_transitions.pop(0)

                # New cycle started
                self._current_cycle_start = now
                LOGGER.debug(
                    "Cycle transition detected: %s -> %s",
                    self._last_operation_mode,
                    current_mode,
                )

            # Update last mode
            self._last_operation_mode = current_mode

            # Calculate elapsed and predicted remaining time
            if self._current_cycle_start is not None:
                elapsed_time = now - self._current_cycle_start
                cycle_status["elapsed_time"] = elapsed_time

                # Only predict for cycles with known durations
                if (
                    current_mode in [1, 2, 3, 4, 5]
                    and self._cycle_durations[current_mode] > 0
                ):
                    expected_duration = self._cycle_durations[current_mode]
                    remaining_time = max(0, expected_duration - elapsed_time)
                    cycle_status["remaining_time"] = remaining_time
                    cycle_status["predicted_end"] = now + remaining_time

        except (KeyError, TypeError):
            # Don't crash cycle tracking on data parsing errors
            pass

        return cycle_status

    def _seed_cycle_durations_from_settings(self, device: PoolCopDevice) -> None:
        """Seed cycle duration predictions from device settings."""
        if not device.settings.filtrations:
            return
        filtration = device.settings.filtrations[0]

        seeds: dict[int, str] = {
            2: filtration.backwash_duration,  # Backwash mode
            5: filtration.rinse_duration,  # Rinse mode
        }

        for mode, time_str in seeds.items():
            if not time_str or time_str == "00:00:00":
                continue
            try:
                parts = time_str.split(":")
                seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except (ValueError, IndexError):
                continue
            if (
                seconds > 0
                and self._cycle_durations[mode] == DEFAULT_CYCLE_DURATIONS[mode]
            ):
                self._cycle_durations[mode] = seconds
                LOGGER.debug(
                    "Seeded mode %d duration from settings: %ds", mode, seconds
                )

    # ------------------------------------------------------------------
    # Data update
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> PoolCopData:
        """Fetch data from PoolCop Client API."""
        try:
            device = await self.api.get_device(self.device_id)

            # Refresh pool info periodically (lat/lon/timezone)
            now_mono = time.monotonic()
            if now_mono - self._pool_last_fetch >= _POOL_REFRESH_INTERVAL:
                try:
                    pools = await self.api.get_pools()
                    # Find the pool that contains our device
                    for pool in pools:
                        for dev in pool.devices:
                            if dev.id == self.device_id:
                                self._pool = pool
                                break
                        if self._pool is not None and self._pool.id == pool.id:
                            break
                    self._pool_last_fetch = now_mono
                except Exception:
                    # Non-critical; keep stale pool data
                    LOGGER.debug("Failed to refresh pool info", exc_info=True)

            # Seed cycle durations from settings (only overrides defaults)
            self._seed_cycle_durations_from_settings(device)

            data = PoolCopData(
                device=device,
                pool=self._pool,
                cycle_status=self._update_cycle_tracking(device),
            )

            # Accumulate daily filtration volume
            self._update_daily_volume()

            # Save learned data periodically - every hour
            current_time = time.time()
            if (
                not hasattr(self, "_last_save_time")
                or current_time - getattr(self, "_last_save_time", 0) > 3600
            ):
                self.hass.async_create_task(self.async_save_learned_data())
                self._last_save_time = current_time

        except PoolCopClientAuthError as err:
            raise ConfigEntryAuthFailed("API key is invalid or expired") from err
        except PoolCopClientRateLimitError as err:
            # Back off until the rate limit window resets
            retry_after = err.retry_after if err.retry_after else MIN_UPDATE_INTERVAL
            self.update_interval = timedelta(seconds=retry_after)
            LOGGER.warning(
                "PoolCop Client API rate limit hit, retrying in %ds", retry_after
            )
            raise UpdateFailed("PoolCop Client API rate limit exceeded") from err
        except PoolCopClientConnectionError as err:
            raise UpdateFailed(
                "Error communicating with PoolCop Client API"
            ) from err
        except Exception as err:
            LOGGER.exception("Unexpected error processing PoolCop data: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err
        else:
            return data

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def async_save_learned_data(self) -> None:
        """Save learned data to storage."""
        data = {
            "cycle_durations": self._cycle_durations,
            "flow_rates": self.flow_rates,
            "daily_volume": self._daily_volume,
            "daily_volume_date": self._daily_volume_date,
        }
        await self._store.async_save(data)
        LOGGER.debug("Saved learned data to persistent storage")

    async def async_load_learned_data(self) -> None:
        """Load learned data from storage."""
        stored_data = await self._store.async_load()
        if stored_data:
            if "cycle_durations" in stored_data:
                # JSON serializes int keys as strings; convert back
                for k, v in stored_data["cycle_durations"].items():
                    self._cycle_durations[int(k)] = int(v)
                LOGGER.debug("Loaded saved cycle durations: %s", self._cycle_durations)

            if "flow_rates" in stored_data:
                # JSON serializes int keys as strings; convert back
                for k, v in stored_data["flow_rates"].items():
                    self.flow_rates[int(k)] = v
                LOGGER.debug("Loaded saved flow rates: %s", self.flow_rates)

            if "daily_volume" in stored_data and "daily_volume_date" in stored_data:
                today = datetime.now().strftime("%Y-%m-%d")
                if stored_data["daily_volume_date"] == today:
                    self._daily_volume = float(stored_data["daily_volume"])
                    self._daily_volume_date = today
                    LOGGER.debug("Restored daily volume: %.3f m3", self._daily_volume)

    async def async_config_entry_first_refresh(self) -> None:
        """First refresh handling."""
        # Load stored data before first refresh
        await self.async_load_learned_data()
        await super().async_config_entry_first_refresh()

    # ------------------------------------------------------------------
    # Command methods
    #
    # TODO: The client API enforces a 10s rate limit per entity (device ID).
    # Verify with PCFR whether this applies between consecutive commands
    # (e.g. set speed then immediately stop pump). If so, rapid command
    # sequences may be rejected with HTTP 429, which is a safety concern
    # for emergency stops. May need client-side queuing or a confirmation
    # that interaction endpoints are exempt from the per-entity limit.
    # ------------------------------------------------------------------

    async def set_pump(self, on: bool) -> None:
        """Turn the pump on or off."""
        await self.api.set_pump(self.device_id, on=on)
        LOGGER.debug("Set pump %s", "on" if on else "off")

    async def set_pump_speed(self, speed: str) -> None:
        """Set the pump speed (None, Speed1-Speed8)."""
        await self.api.set_pump_speed(self.device_id, speed)
        LOGGER.debug("Set pump speed to %s", speed)

    async def set_valve_position(self, position: str) -> None:
        """Set the valve position (Filter, Waste, Closed, Backwash, Bypass, Rinse)."""
        await self.api.set_valve_position(self.device_id, position)
        LOGGER.debug("Set valve position to %s", position)

    async def clear_alarm(self, code: str) -> None:
        """Clear a specific alarm by code."""
        await self.api.clear_alarm(self.device_id, code)
        LOGGER.debug("Cleared alarm %s", code)

    async def clear_all_alarms(self) -> None:
        """Clear all active alarms."""
        await self.api.clear_all_alarms(self.device_id)
        LOGGER.debug("Cleared all alarms")

    async def set_auxiliary(self, module: str, aux_id: int, *, on: bool) -> None:
        """Set an auxiliary output on or off."""
        await self.api.set_auxiliary(self.device_id, module, aux_id, on=on)
        LOGGER.debug(
            "Set auxiliary %s/%d %s", module, aux_id, "on" if on else "off"
        )

    async def set_forced_filtration(self, mode: str) -> None:
        """Set forced filtration mode (NotForced, Forced24H, Forced48H, Forced72H)."""
        await self.api.set_pump_forced(self.device_id, mode)
        LOGGER.debug("Set forced filtration mode to %s", mode)

    async def set_heating_setpoint(
        self, setpoint: float, aux_id: int, module: str = "None"
    ) -> None:
        """Set the heating setpoint for an auxiliary."""
        await self.api.set_heating_setpoint(
            self.device_id, setpoint, aux_id, module
        )
        LOGGER.debug("Set heating setpoint to %.1f for aux %d", setpoint, aux_id)

    async def set_jet_stream(self, on: bool) -> None:
        """Turn the jet stream on or off."""
        await self.api.set_jet_stream(self.device_id, on=on)
        LOGGER.debug("Set jet stream %s", "on" if on else "off")
