"""The Coordinator for PoolCop."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any, NamedTuple

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    ConfigEntryAuthFailed,
    DataUpdateCoordinator,
    UpdateFailed,
)

from poolcop import (  # type: ignore[attr-defined]  # namespace collision with integration dir
    PoolCopilot,
    PoolCopilotConnectionError,
    PoolCopilotInvalidKeyError,
    PoolCopilotRateLimitError,
)

from .const import (
    ALARM_FETCH_INTERVAL,
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
    DOMAIN,
    LOGGER,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    STORAGE_KEY,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
)

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


class PoolCopData(NamedTuple):
    """Class for defining data in dict."""

    status: dict[str, Any] | None
    alarms: dict[str, Any] | None = None
    commands: dict[str, Any] | None = None
    active_alarms: list[dict[str, Any]] | None = None
    cycle_status: dict[str, Any] | None = None  # For tracking cycle information
    last_command_result: dict[str, Any] | None = (
        None  # Result from the most recent command
    )

    def status_value(self, path: str, prefix: str = "PoolCop") -> Any:
        """Get value from a path (e.g. 'temperature.water') from the Poolcop status."""
        full_path = f"{prefix}.{path}"

        result = self.status
        for part in filter(None, full_path.split(".")):
            if not isinstance(result, dict):
                return None
            result = result.get(part)
            if result is None:
                return None
        return result

    def has_active_alarms(self) -> bool:
        """Check if there are any active alarms."""
        return bool(self.active_alarms)


class PoolCopDataUpdateCoordinator(DataUpdateCoordinator[PoolCopData]):
    """Class to manage fetching PoolCop data from single endpoint."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize global PoolCop data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.poolcopilot = PoolCopilot(
            session=async_get_clientsession(hass),
            api_key=api_key,
        )

        # Initialize pump flow rates from options (preferred) or data (pre-migration)
        self.flow_rates = {}
        for speed, key in (
            (1, CONF_FLOW_RATE_1),
            (2, CONF_FLOW_RATE_2),
            (3, CONF_FLOW_RATE_3),
        ):
            value = config_entry.options.get(key, config_entry.data.get(key))
            if value is not None:
                self.flow_rates[speed] = value

        # Setup storage for persisting learned data
        self._store: Store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{api_key}")

        # Track when we last fetched alarms to avoid excessive API calls
        self._last_alarm_fetch: float = 0
        self._active_alarms: list[dict[str, Any]] = []
        self._previous_alarm_count: int = 0

        # Daily filtration volume tracking
        self._daily_volume: float = 0.0  # m³ filtered today
        self._daily_volume_date: str | None = None  # YYYY-MM-DD of current accumulation
        self._last_flow_update: float | None = (
            None  # monotonic timestamp of last update
        )

        # Cycle tracking
        self._last_operation_mode: int | None = None
        self._current_cycle_start: float | None = None
        self._cycle_durations: dict[int, int] = dict(DEFAULT_CYCLE_DURATIONS)
        self._cycle_transitions: list[dict[str, Any]] = []

    def get_current_flow_rate(self) -> float:
        """Return the current effective flow rate in m³/h.

        Returns 0.0 if pump is off or valve is not in a flowing position.
        Uses configured flow rates based on pump speed level.
        """
        if not hasattr(self, "data") or self.data is None:
            return 0.0

        # Pump must be on
        if not self.data.status_value("status.pump"):
            return 0.0

        # Valve must be in a position that moves water through the filter
        # 0=Filter, 4=Bypass (still flowing), 5=Rinse (flowing)
        valve_pos = self.data.status_value("status.valveposition")
        if valve_pos is not None and valve_pos not in (0, 4, 5):
            return 0.0

        # Look up flow rate for current speed
        speed_level = self.data.status_value("status.pumpspeed")
        if speed_level is None:
            return 0.0

        try:
            speed_level = int(speed_level)
        except ValueError, TypeError:
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

    def _get_remaining_cycle_seconds(self, cycle_name: str) -> float:
        """Return remaining filtration seconds for a cycle timer today.

        Returns 0 if the cycle is disabled, has no valid times, or has already finished.
        Unlike _time_str_to_datetime, this always interprets times as today (no tomorrow shift).
        """
        if not self.data or not self.data.status:
            return 0.0

        timer = self.data.status_value(f"timers.{cycle_name}")
        if not timer or timer.get("enabled") != 1:
            return 0.0

        start_str = timer.get("start")
        stop_str = timer.get("stop")
        if (
            not start_str
            or not stop_str
            or start_str == "00:00:00"
            or stop_str == "00:00:00"
        ):
            return 0.0

        try:
            # Get timezone
            tz = None
            pool_data = self.data.status_value("", prefix="Pool")
            if pool_data and isinstance(pool_data, dict) and "timezone" in pool_data:
                try:
                    import zoneinfo

                    tz = zoneinfo.ZoneInfo(pool_data["timezone"])
                except ImportError, zoneinfo.ZoneInfoNotFoundError:
                    pass

            now = datetime.now(tz=tz)

            sh, sm, ss = map(int, start_str.split(":"))
            eh, em, es = map(int, stop_str.split(":"))

            start_dt = now.replace(hour=sh, minute=sm, second=ss, microsecond=0)
            stop_dt = now.replace(hour=eh, minute=em, second=es, microsecond=0)
        except ValueError, TypeError:
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
        """Return flow rate for a given pump speed, with fallback."""
        if speed is not None:
            rate = self.flow_rates.get(speed, 0.0)
            if rate > 0:
                return rate
        # Fallback to current pump speed
        current_speed = (
            self.data.status_value("status.pumpspeed") if self.data else None
        )
        if current_speed is not None:
            try:
                return self.flow_rates.get(int(current_speed), 0.0)
            except ValueError, TypeError:
                pass
        # Last fallback: speed 1
        return self.flow_rates.get(1, 0.0)

    @property
    def planned_remaining_volume(self) -> float:
        """Return the planned remaining filtration volume in m³ for today.

        Dispatches on the actual operating mode (status.poolcop), not
        the configured filter timer setting, so forced filtration activated
        via command is handled correctly.
        """
        if not self.data or not self.data.status:
            return 0.0

        op_mode = self.data.status_value("status.poolcop")
        if op_mode is None:
            return 0.0

        # Modes with no predictable planned filtration
        # 0=Stop, 1=Freeze, 5=Manual, 6=Paused, 7=External
        if op_mode in (0, 1, 5, 6, 7):
            return 0.0

        # Check the configured filter timer mode for modes that the
        # operating mode alone cannot distinguish.
        filter_timer = self.data.status_value("settings.filter.timer")

        # Filter timer 8 (24/24 Always On): pump runs 24/7, no cycles.
        # The operating mode may report as Continuous (9) or another
        # mode, but the intent is always-on filtration until midnight.
        if filter_timer == 8:
            return self._remaining_hours_volume()

        # Filter timer 4 (CONTINUOUS 23h/day): two 11h30 cycles,
        # always reports as op_mode 9.  Use remaining hours capped.
        if filter_timer == 4 or op_mode == 9:
            return self._remaining_hours_volume()

        # Mode 2: Forced - use status.forced.remaining_hours x flow rate
        if op_mode == 2:
            remaining_hours = self.data.status_value("status.forced.remaining_hours")
            if remaining_hours is not None and remaining_hours > 0:
                current_speed = self.data.status_value("status.pumpspeed")
                if current_speed is not None:
                    try:
                        current_speed = int(current_speed)
                    except ValueError, TypeError:
                        current_speed = None
                flow = self._get_flow_rate_for_speed(current_speed)
                return round(flow * remaining_hours, 3)
            return 0.0

        # Modes 3 (Auto), 4 (Timer), 8 (Eco+) - use cycle timers
        if op_mode in (3, 4, 8):
            total = 0.0
            for cycle_name, speed_key in (
                ("cycle1", "speed_cycle1"),
                ("cycle2", "speed_cycle2"),
            ):
                remaining_secs = self._get_remaining_cycle_seconds(cycle_name)
                if remaining_secs > 0:
                    speed = self.data.status_value(f"settings.pump.{speed_key}")
                    if speed is not None:
                        try:
                            speed = int(speed)
                        except ValueError, TypeError:
                            speed = None
                    flow = self._get_flow_rate_for_speed(speed)
                    total += flow * (remaining_secs / 3600.0)
            return round(total, 3)

        return 0.0

    def _remaining_hours_volume(self) -> float:
        """Calculate volume from remaining hours today x current flow rate."""
        try:
            # Get timezone
            tz = None
            if self.data and self.data.status:
                pool_data = self.data.status_value("", prefix="Pool")
                if (
                    pool_data
                    and isinstance(pool_data, dict)
                    and "timezone" in pool_data
                ):
                    try:
                        import zoneinfo

                        tz = zoneinfo.ZoneInfo(pool_data["timezone"])
                    except ImportError, zoneinfo.ZoneInfoNotFoundError:
                        pass

            now = datetime.now(tz=tz) if tz else datetime.now()
            midnight = now.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)
            remaining_hours = (midnight - now).total_seconds() / 3600.0
            # Cap at 23 hours
            remaining_hours = min(remaining_hours, 23.0)
        except Exception:
            return 0.0

        current_speed = (
            self.data.status_value("status.pumpspeed") if self.data else None
        )
        if current_speed is not None:
            try:
                current_speed = int(current_speed)
            except ValueError, TypeError:
                current_speed = None
        flow = self._get_flow_rate_for_speed(current_speed)
        return round(flow * remaining_hours, 3)

    @property
    def planned_remaining_turnovers(self) -> float | None:
        """Return planned remaining turnovers (volume / pool_volume)."""
        if not self.data or not self.data.status:
            return None
        pool_volume = self.data.status_value("settings.pool.volume")
        if not pool_volume or pool_volume <= 0:
            return None
        return round(self.planned_remaining_volume / pool_volume, 2)

    @property
    def daily_volume(self) -> float:
        """Return the accumulated daily filtration volume in m³."""
        return round(self._daily_volume, 3)

    @property
    def daily_turnovers(self) -> float | None:
        """Return the number of pool turnovers today (1.0 = one full turnover)."""
        if not hasattr(self, "data") or self.data is None:
            return None
        pool_volume = self.data.status_value("settings.pool.volume")
        if not pool_volume or pool_volume <= 0:
            return None
        return round(self._daily_volume / pool_volume, 2)

    def _update_cycle_tracking(self, status_data: dict) -> dict:
        """Track cycle changes and update predictions."""
        cycle_status: dict[str, Any] = {
            "previous_mode": self._last_operation_mode,
            "predicted_end": None,
            "elapsed_time": None,
            "remaining_time": None,
        }

        try:
            current_mode = status_data["PoolCop"]["status"]["poolcop"]
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

        except KeyError, TypeError:
            # Don't crash cycle tracking on data parsing errors
            pass

        return cycle_status

    def _seed_cycle_durations_from_settings(self, status_data: dict) -> None:
        """Seed cycle duration predictions from API settings."""
        settings = status_data.get("PoolCop", {}).get("settings", {})

        seeds = {
            2: settings.get("filter", {}).get("backwash_duration"),  # Backwash mode
            5: settings.get("filter", {}).get("rinse_duration"),  # Rinse mode
        }

        for mode, value in seeds.items():
            if (
                value
                and isinstance(value, int | float)
                and value > 0
                and self._cycle_durations[mode] == DEFAULT_CYCLE_DURATIONS[mode]
            ):
                self._cycle_durations[mode] = int(value)
                LOGGER.debug("Seeded mode %d duration from settings: %ds", mode, value)

    async def _async_update_data(self) -> PoolCopData:
        """Fetch data from PoolCop."""
        try:
            status = await self.poolcopilot.status()

            # Seed cycle durations from settings (only overrides defaults)
            self._seed_cycle_durations_from_settings(status)

            # Active alarms from status alerts array (always present, no extra API call)
            alarm_data = None
            status_alerts = status.get("PoolCop", {}).get("alerts", [])
            self._active_alarms = status_alerts if status_alerts else []

            # Optionally fetch detailed alarm history for richer data
            current_time = time.time()
            alarm_count = len(status_alerts)
            should_fetch_alarms = alarm_count > 0 and (
                current_time - self._last_alarm_fetch > ALARM_FETCH_INTERVAL
                or alarm_count != self._previous_alarm_count
            )

            if should_fetch_alarms:
                LOGGER.debug(
                    "Fetching alarm history: previous_count=%s, current_count=%s",
                    self._previous_alarm_count,
                    alarm_count,
                )
                try:
                    alarm_data = await self.poolcopilot.alarm_history(0)

                    # If alarm_history returns richer data, prefer it
                    if alarm_data and "alarms" in alarm_data:
                        history_alarms = [
                            alarm
                            for alarm in alarm_data.get("alarms", [])
                            if not alarm.get("cleared")
                        ]
                        if history_alarms:
                            self._active_alarms = history_alarms

                    self._last_alarm_fetch = float(current_time)
                    self._previous_alarm_count = int(alarm_count)
                except (PoolCopilotConnectionError, PoolCopilotRateLimitError) as err:
                    LOGGER.warning("Failed to fetch alarm history: %s", err)
                    # Still mark as fetched to avoid retrying every cycle
                    self._last_alarm_fetch = float(current_time)

            data = PoolCopData(
                status=status,
                alarms=alarm_data,
                active_alarms=self._active_alarms,
                cycle_status=self._update_cycle_tracking(status),
            )

            # Accumulate daily filtration volume
            self._update_daily_volume()

            # Dynamic polling: distribute remaining quota evenly across the window
            remaining_quota = self.poolcopilot.token_limit
            token_expire = self.poolcopilot.token_expire
            if remaining_quota and remaining_quota > 0 and token_expire > 0:
                time_remaining = max(0, token_expire - time.time())
                if time_remaining > 0:
                    interval = time_remaining / remaining_quota
                    interval = max(
                        MIN_UPDATE_INTERVAL,
                        min(MAX_UPDATE_INTERVAL, interval),
                    )
                    self.update_interval = timedelta(seconds=interval)
                    LOGGER.debug(
                        "Dynamic interval: %.1fs (quota=%d, window=%.0fs)",
                        interval,
                        remaining_quota,
                        time_remaining,
                    )

            # Save learned data periodically - every hour
            if (
                not hasattr(self, "_last_save_time")
                or current_time - getattr(self, "_last_save_time", 0) > 3600
            ):
                self.hass.async_create_task(self.async_save_learned_data())
                self._last_save_time = current_time
        except PoolCopilotInvalidKeyError as err:
            raise ConfigEntryAuthFailed("API key is invalid or expired") from err
        except PoolCopilotRateLimitError as err:
            # Add specific handling for rate limit errors with exponential backoff
            retry_after = getattr(err, "retry_after", None)

            # Use retry_after if available, otherwise use exponential backoff
            if retry_after and isinstance(retry_after, int | float):
                backoff_time = retry_after
            else:
                # Calculate exponential backoff based on update interval
                # Start with 2x normal interval, cap at 30 minutes
                current_interval = (
                    self.update_interval.total_seconds()
                    if self.update_interval
                    else UPDATE_INTERVAL
                )
                backoff_time = min(current_interval * 2, 1800)  # Max 30 minutes

            LOGGER.warning(
                "PoolCopilot API rate limit reached. Backing off for %d seconds",
                backoff_time,
            )

            # Update the coordinator's update interval temporarily
            self.update_interval = timedelta(seconds=backoff_time)

            # Propagate a more specific error
            raise UpdateFailed(
                "PoolCopilot API rate limit reached, backing off"
            ) from err
        except PoolCopilotConnectionError as err:
            raise UpdateFailed("Error communicating with PoolCopilot API") from err
        except Exception as err:
            LOGGER.exception("Unexpected error processing PoolCop data: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err
        else:
            return data

    async def async_get_alarm_history(self, offset: int = 0) -> dict[str, Any]:
        """Get alarm history from PoolCop."""
        try:
            return await self.poolcopilot.alarm_history(offset)
        except PoolCopilotConnectionError as err:
            LOGGER.error("Error fetching alarm history: %s", err)
            raise

    async def async_get_command_history(self, offset: int = 0) -> dict[str, Any]:
        """Get command history from PoolCop."""
        try:
            return await self.poolcopilot.command_history(offset)
        except PoolCopilotConnectionError as err:
            LOGGER.error("Error fetching command history: %s", err)
            raise

    async def async_save_learned_data(self) -> None:
        """Save learned data to storage."""
        data = {
            "cycle_durations": self._cycle_durations,
            "flow_rates": self.flow_rates,
        }
        await self._store.async_save(data)
        LOGGER.debug("Saved learned data to persistent storage")

    async def async_load_learned_data(self) -> None:
        """Load learned data from storage."""
        stored_data = await self._store.async_load()
        if stored_data:
            if "cycle_durations" in stored_data:
                self._cycle_durations.update(stored_data["cycle_durations"])
                LOGGER.debug("Loaded saved cycle durations: %s", self._cycle_durations)

            if "flow_rates" in stored_data:
                self.flow_rates.update(stored_data["flow_rates"])
                LOGGER.debug("Loaded saved flow rates: %s", self.flow_rates)

    async def async_config_entry_first_refresh(self) -> None:
        """First refresh handling."""
        # Load stored data before first refresh
        await self.async_load_learned_data()
        await super().async_config_entry_first_refresh()

    def _update_command_result(self, result: dict[str, Any]) -> None:
        """Update data with a command result, preserving all other fields."""
        self.data = self.data._replace(last_command_result=result)

    async def set_pump_speed(self, speed: int) -> None:
        """Set the pump speed."""
        result = await self.poolcopilot.set_pump_speed(speed)
        self._update_command_result(result)
        LOGGER.debug("Set pump speed to %s, result: %s", speed, result)

    async def toggle_pump(self, turn_on: bool | None = None) -> None:
        """Toggle the pump. If turn_on is specified, only toggle if state differs."""
        if turn_on is not None:
            current_state = bool(self.data.status_value("status.pump"))
            if current_state == turn_on:
                LOGGER.debug(
                    "Pump already in requested state (%s), no action needed",
                    "on" if turn_on else "off",
                )
                return
        result = await self.poolcopilot.toggle_pump()
        self._update_command_result(result)
        LOGGER.debug("Toggled pump, result: %s", result)

    async def set_valve_position(self, position: int) -> None:
        """Set the valve position."""
        result = await self.poolcopilot.set_valve_position(position)
        self._update_command_result(result)
        LOGGER.debug("Set valve position to %s, result: %s", position, result)

    async def clear_alarm(self) -> None:
        """Clear active alarms."""
        result = await self.poolcopilot.clear_alarm()
        self._update_command_result(result)
        self._last_alarm_fetch = 0
        self._active_alarms = []
        LOGGER.debug("Cleared alarms, result: %s", result)

    async def toggle_auxiliary(self, aux_id: int) -> None:
        """Toggle an auxiliary output."""
        result = await self.poolcopilot.toggle_auxiliary(aux_id)
        self._update_command_result(result)
        LOGGER.debug("Toggled auxiliary %s, result: %s", aux_id, result)

    async def set_force_filtration_mode(self, mode: int) -> None:
        """Set forced filtration mode."""
        result = await self.poolcopilot.set_force_filtration(mode)
        self._update_command_result(result)
        LOGGER.debug("Set force filtration mode to %s, result: %s", mode, result)
