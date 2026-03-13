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

from poolcop import (
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
    CYCLE_END_PREDICTION_WINDOW,
    DOMAIN,
    LOGGER,
    NORMAL_UPDATE_INTERVAL,
    STORAGE_KEY,
    STORAGE_VERSION,
    TRANSITION_UPDATE_INTERVAL,
)

# Default cycle durations (in seconds)
DEFAULT_CYCLE_DURATIONS = {
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
    next_timer_event: dict[str, Any] | None = None  # For tracking upcoming timer events
    last_command_result: dict[str, Any] | None = (
        None  # Result from the most recent command
    )

    def status_value(self, path: str, prefix: str = "PoolCop") -> Any:
        """Get value from a path (e.g. 'temperature.water') from the Poolcop status."""
        full_path = f"{prefix}.{path}"

        try:
            result = self.status
            for part in filter(None, full_path.split(".")):
                if not isinstance(result, dict):
                    return None
                result = result.get(part)
                if result is None:
                    return None
        except (KeyError, TypeError) as err:
            LOGGER.debug(
                "Error accessing path %s with prefix %s: %s", path, prefix, err
            )
            return None
        else:
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
            update_interval=timedelta(seconds=NORMAL_UPDATE_INTERVAL),
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
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{api_key}")

        # Track when we last fetched alarms to avoid excessive API calls
        self._last_alarm_fetch = 0
        self._active_alarms = []
        self._previous_alarm_count = 0

        # Daily filtration volume tracking
        self._daily_volume: float = 0.0  # m³ filtered today
        self._daily_volume_date: str | None = None  # YYYY-MM-DD of current accumulation
        self._last_flow_update: float | None = None  # monotonic timestamp of last update

        # Cycle tracking
        self._last_operation_mode = None
        self._current_cycle_start = None
        self._cycle_durations = DEFAULT_CYCLE_DURATIONS.copy()
        self._cycle_transitions = []  # Track recent cycle transitions for analysis
        self._next_update_time = time.time()  # When to perform next update

    def _adjust_update_interval(self) -> None:
        """Adjust the update interval based on cycle state."""
        now = time.time()
        cycle_mode = self.data.status_value("status.poolcop")

        # Default to normal interval
        new_interval = NORMAL_UPDATE_INTERVAL

        # If we have a current cycle and know its typical duration
        if (
            cycle_mode is not None
            and self._current_cycle_start is not None
            and cycle_mode in self._cycle_durations
            and self._cycle_durations[cycle_mode] > 0
        ):
            # Calculate expected end time
            expected_duration = self._cycle_durations[cycle_mode]
            cycle_elapsed = now - self._current_cycle_start
            time_remaining = expected_duration - cycle_elapsed

            # If we're approaching the end of a cycle, increase update frequency
            if 0 < time_remaining < CYCLE_END_PREDICTION_WINDOW:
                new_interval = TRANSITION_UPDATE_INTERVAL
                LOGGER.debug(
                    "Cycle %s approaching end (%.1f minutes remaining). Using faster update interval.",
                    cycle_mode,
                    time_remaining / 60,
                )

        # Update the coordinator's update interval if it changed
        if self.update_interval.total_seconds() != new_interval:
            self.update_interval = timedelta(seconds=new_interval)
            LOGGER.debug("Adjusted update interval to %s seconds", new_interval)

        # Schedule next update
        self._next_update_time = now + new_interval

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
        except (ValueError, TypeError):
            return 0.0

        return self.flow_rates.get(speed_level, 0.0)

    def _update_daily_volume(self) -> None:
        """Accumulate filtered volume based on current flow rate and elapsed time."""
        now = time.monotonic()

        # Reset at midnight (check date string)
        try:
            today = datetime.now().strftime("%Y-%m-%d")
        except Exception:  # noqa: BLE001
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
        cycle_status = {
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
                            new_duration = (0.3 * cycle_duration) + (0.7 * old_duration)
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

    def _check_upcoming_timer_events(self) -> dict | None:
        """Check for upcoming timer events and adjust update interval accordingly."""
        if not self.data or not self.data.status:
            return None

        now = datetime.now()
        now_timestamp = now.timestamp()
        upcoming_events = []

        try:
            # Check enabled filtration cycles
            timers_data = self.data.status_value("timers")
            if not timers_data:
                return None

            # Process cycle timers
            for cycle_name in ["cycle1", "cycle2"]:
                cycle = timers_data.get(cycle_name)
                if not cycle or cycle.get("enabled") != 1:
                    continue

                # Process start time
                start_time_str = cycle.get("start")
                if start_time_str and start_time_str != "00:00:00":
                    start_time = self._time_str_to_datetime(start_time_str)
                    if start_time:
                        seconds_until = start_time.timestamp() - now_timestamp
                        # Only consider events in the near future (next 30 minutes)
                        if 0 < seconds_until < 1800:
                            upcoming_events.append(
                                {
                                    "type": f"{cycle_name}_start",
                                    "time": start_time,
                                    "seconds_until": seconds_until,
                                }
                            )

                # Process stop time
                stop_time_str = cycle.get("stop")
                if stop_time_str and stop_time_str != "00:00:00":
                    stop_time = self._time_str_to_datetime(stop_time_str)
                    if stop_time:
                        seconds_until = stop_time.timestamp() - now_timestamp
                        # Only consider events in the near future (next 30 minutes)
                        if 0 < seconds_until < 1800:
                            upcoming_events.append(
                                {
                                    "type": f"{cycle_name}_stop",
                                    "time": stop_time,
                                    "seconds_until": seconds_until,
                                }
                            )

            # Process auxiliary timers that are enabled and switchable
            for aux_id in range(1, 7):
                # First check if this aux is switchable by checking the aux data
                aux_data = next(
                    (
                        a
                        for a in self.data.status_value("aux", [])
                        if a.get("id") == aux_id
                    ),
                    None,
                )
                if not aux_data or not aux_data.get("switchable"):
                    continue

                # Now check the timer
                aux_timer = timers_data.get(f"aux{aux_id}")
                if not aux_timer or aux_timer.get("enabled") != 1:
                    continue

                # Process start time
                start_time_str = aux_timer.get("start")
                if start_time_str and start_time_str != "00:00:00":
                    start_time = self._time_str_to_datetime(start_time_str)
                    if start_time:
                        seconds_until = start_time.timestamp() - now_timestamp
                        # Only consider events in the near future (next 30 minutes)
                        if 0 < seconds_until < 1800:
                            upcoming_events.append(
                                {
                                    "type": f"aux{aux_id}_start",
                                    "time": start_time,
                                    "seconds_until": seconds_until,
                                }
                            )

                # Process stop time
                stop_time_str = aux_timer.get("stop")
                if stop_time_str and stop_time_str != "00:00:00":
                    stop_time = self._time_str_to_datetime(stop_time_str)
                    if stop_time:
                        seconds_until = stop_time.timestamp() - now_timestamp
                        # Only consider events in the near future (next 30 minutes)
                        if 0 < seconds_until < 1800:
                            upcoming_events.append(
                                {
                                    "type": f"aux{aux_id}_stop",
                                    "time": stop_time,
                                    "seconds_until": seconds_until,
                                }
                            )

            # No upcoming events found
            if not upcoming_events:
                return None

            # Find the closest upcoming event
            upcoming_events.sort(key=lambda e: e["seconds_until"])
            next_event = upcoming_events[0]

            LOGGER.debug(
                "Found upcoming timer event: %s in %.1f minutes",
                next_event["type"],
                next_event["seconds_until"] / 60,
            )
        except (KeyError, TypeError, ValueError) as err:
            LOGGER.debug("Error checking timer events: %s", err)
            return None
        else:
            return next_event

    def _time_str_to_datetime(self, time_str: str) -> datetime | None:
        """Convert a time string (HH:MM:SS) to a datetime object for today/tomorrow."""
        if not time_str or time_str == "00:00:00":
            return None

        try:
            # Get timezone from Pool data
            timezone = None
            if self.data and self.data.status:
                pool_data = self.data.status_value("", prefix="Pool")
                if (
                    pool_data
                    and isinstance(pool_data, dict)
                    and "timezone" in pool_data
                ):
                    try:
                        import zoneinfo

                        timezone = zoneinfo.ZoneInfo(pool_data["timezone"])
                    except (ImportError, zoneinfo.ZoneInfoNotFoundError):
                        LOGGER.debug("Could not use timezone %s", pool_data["timezone"])

            # If we couldn't get the timezone from pool data, use local timezone
            if timezone is None:
                from datetime import timezone as dt_timezone
                from time import localtime

                utc_offset = -localtime().tm_gmtoff
                timezone = dt_timezone(timedelta(seconds=utc_offset))

            hour, minute, second = map(int, time_str.split(":"))
            now = datetime.now(tz=timezone)
            result = datetime(
                year=now.year,
                month=now.month,
                day=now.day,
                hour=hour,
                minute=minute,
                second=second,
                tzinfo=timezone,
            )

            # Handle case where the time is for tomorrow (e.g., if now is 23:00 and time is 01:00)
            if result < now and hour < 12:
                result = result + timedelta(days=1)
        except (ValueError, TypeError) as err:
            LOGGER.debug("Error parsing time string %s: %s", time_str, err)
            return None
        else:
            return result

    async def _async_update_data(self) -> PoolCopData:
        """Fetch data from PoolCop."""
        try:
            status = await self.poolcopilot.status()

            # Active alarms from status alerts array (always present, no extra API call)
            alarm_data = None
            status_alerts = status.get("PoolCop", {}).get("alerts", [])
            self._active_alarms = status_alerts if status_alerts else []

            # Optionally fetch detailed alarm history for richer data
            current_time = time.time()
            alarm_count = len(status_alerts)
            should_fetch_alarms = (
                alarm_count > 0
                and (
                    current_time - self._last_alarm_fetch > ALARM_FETCH_INTERVAL
                    or alarm_count != self._previous_alarm_count
                )
            )

            if should_fetch_alarms:
                LOGGER.debug(
                    "Fetching alarm history: previous_count=%s, current_count=%s",
                    self._previous_alarm_count,
                    alarm_count,
                )
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

                self._last_alarm_fetch = current_time
                self._previous_alarm_count = alarm_count

            # Create a placeholder for the data
            data = PoolCopData(
                status=status,
                alarms=alarm_data,
                active_alarms=self._active_alarms,
                cycle_status=self._update_cycle_tracking(status),
            )

            # Check for upcoming timer events
            if hasattr(self, "data") and self.data:
                # We need to create temporary data before checking timer events
                # to ensure the status_value method works correctly
                self.data = data

            # Check for timer events now that we have data
            next_timer_event = self._check_upcoming_timer_events()

            # Create the final data object with the timer event
            data = PoolCopData(
                status=status,
                alarms=alarm_data,
                active_alarms=self._active_alarms,
                cycle_status=self._update_cycle_tracking(status),
                next_timer_event=next_timer_event,
            )

            # Accumulate daily filtration volume
            self._update_daily_volume()

            # Dynamic update interval adjustment based on both cycle and timer events
            interval = NORMAL_UPDATE_INTERVAL

            # First check cycle-based timing
            if (
                data.cycle_status
                and data.cycle_status.get("remaining_time") is not None
                and 0
                < data.cycle_status.get("remaining_time", 0)
                < CYCLE_END_PREDICTION_WINDOW
            ):
                interval = TRANSITION_UPDATE_INTERVAL
                LOGGER.debug(
                    "Cycle approaching end (%.1f minutes remaining). Using faster update interval.",
                    data.cycle_status["remaining_time"] / 60,
                )

            # Then check timer-based timing (takes precedence if closer)
            if next_timer_event:
                seconds_until = next_timer_event["seconds_until"]
                if seconds_until < 300:  # 5 minutes
                    # Use faster polling as we approach a timer event
                    interval = TRANSITION_UPDATE_INTERVAL
                    LOGGER.debug(
                        "Timer event %s approaching (%.1f minutes remaining). Using faster update interval.",
                        next_timer_event["type"],
                        seconds_until / 60,
                    )
                elif interval == NORMAL_UPDATE_INTERVAL:
                    # Don't wait longer than 5 minutes if there's an upcoming event
                    # but don't override transition interval if it's already set
                    interval = min(NORMAL_UPDATE_INTERVAL, int(seconds_until / 2))
                    LOGGER.debug(
                        "Upcoming timer event %s (%.1f minutes). Setting interval to %d seconds.",
                        next_timer_event["type"],
                        seconds_until / 60,
                        interval,
                    )

            # Update the coordinator's update interval if needed
            if self.update_interval.total_seconds() != interval:
                self.update_interval = timedelta(seconds=interval)
                LOGGER.debug("Adjusted update interval to %d seconds", interval)

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
            if retry_after and isinstance(retry_after, (int, float)):
                backoff_time = retry_after
            else:
                # Calculate exponential backoff based on update interval
                # Start with 2x normal interval, cap at 30 minutes
                current_interval = self.update_interval.total_seconds()
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
