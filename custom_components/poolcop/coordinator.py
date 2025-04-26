"""The Coordinator for PoolCop."""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import reduce
import operator
import time
from typing import Any, NamedTuple, Optional

from poolcop import (
    PoolCopilot, 
    PoolCopilotConnectionError,
    PoolCopilotRateLimitError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, 
    LOGGER, 
    NORMAL_UPDATE_INTERVAL,
    TRANSITION_UPDATE_INTERVAL,
    CYCLE_END_PREDICTION_WINDOW,
    ALARM_FETCH_INTERVAL,
    STORAGE_KEY,
    STORAGE_VERSION,
    DEFAULT_FLOW_RATES,
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
)

# Default cycle durations (in seconds)
DEFAULT_CYCLE_DURATIONS = {
    0: 0,      # Idle - no duration 
    1: 7200,   # Cycle 1 - start with 2 hours as default
    2: 600,    # Backwash - start with 10 minutes as default
    3: 3600,   # Cycle 2 - start with 1 hour as default
    4: 900,    # Waste - start with 15 minutes as default
    5: 300,    # Rinse - start with 5 minutes as default
    6: 0,      # Pause - no predictable duration
    7: 0,      # External Filter - no predictable duration
}


class PoolCopData(NamedTuple):
    """Class for defining data in dict."""

    status: dict[str, Any] | None
    alarms: dict[str, Any] | None = None
    commands: dict[str, Any] | None = None
    active_alarms: list[dict[str, Any]] | None = None
    cycle_status: dict[str, Any] | None = None  # For tracking cycle information
    next_timer_event: dict[str, Any] | None = None  # For tracking upcoming timer events
    _coordinator = None  # Allow storing reference to coordinator for advanced calculations

    def status_value(self, path: str, prefix="PoolCop") -> Any:
        """Get value from a path (e.g. 'temperature.water') from the Poolcop status."""
        try:
            return reduce(operator.getitem, [prefix] + path.split("."), self.status)  # type: ignore[arg-type]
        except (KeyError, TypeError):
            return None
            
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
        
        # Initialize pump flow rates from defaults
        self.flow_rates = dict()
        
        # Update flow rates from config entry if available
        if CONF_FLOW_RATE_1 in config_entry.data:
            self.flow_rates[1] = config_entry.data[CONF_FLOW_RATE_1]
        if CONF_FLOW_RATE_2 in config_entry.data:
            self.flow_rates[2] = config_entry.data[CONF_FLOW_RATE_2]
        if CONF_FLOW_RATE_3 in config_entry.data:
            self.flow_rates[3] = config_entry.data[CONF_FLOW_RATE_3]
        
        # Setup storage for persisting learned data
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{api_key}")
        
        # Track when we last fetched alarms to avoid excessive API calls
        self._last_alarm_fetch = 0
        self._active_alarms = []
        self._previous_alarm_count = 0
        
        # Cycle tracking
        self._last_operation_mode = None
        self._current_cycle_start = None
        self._cycle_durations = DEFAULT_CYCLE_DURATIONS.copy()
        self._cycle_transitions = []  # Track recent cycle transitions for analysis
        self._next_update_time = time.time()  # When to perform next update
        
    def calculate_flow_rate(self, speed_level: int) -> float:
        """Calculate flow rate based on pump speed level using the configured flow rates.
        
        Args:
            speed_level: The pump speed level (0, 1, 2, or 3) from status.pumpspeed
            
        Note:
            The API uses discrete levels (0-3) for both control and status reporting.
            Level 0 means pump is off, levels 1-3 correspond to the three pump speeds.
        """
        # Ensure speed_level is an integer and handle None values
        if speed_level is None:
            LOGGER.debug("No pump speed level (None), returning 0 flow rate")
            return 0.0
            
        try:
            speed_level = int(speed_level)
            LOGGER.debug("Current pump speed level: %s", speed_level)
        except (ValueError, TypeError):
            LOGGER.warning("Invalid pump speed level: %s, returning 0 flow rate", speed_level)
            return 0.0
        
        # When pump is off (speed 0), flow rate is always 0
        if speed_level == 0:
            return 0.0
            
        # Return the flow rate directly from our configured values
        if speed_level in self.flow_rates:
            flow_rate = self.flow_rates[speed_level]
            LOGGER.debug("Using flow rate for speed %s: %s m³/h", speed_level, flow_rate)
            return flow_rate
            
        # Fallback to 0 for unknown speed levels
        LOGGER.warning("Unknown speed level: %s, returning 0 flow rate", speed_level)
        return 0.0

    def _adjust_update_interval(self) -> None:
        """Adjust the update interval based on cycle state."""
        now = time.time()
        cycle_mode = self.data.status_value("status.poolcop")
        
        # Default to normal interval
        new_interval = NORMAL_UPDATE_INTERVAL
        
        # If we have a current cycle and know its typical duration
        if (cycle_mode is not None and 
            self._current_cycle_start is not None and 
            cycle_mode in self._cycle_durations and
            self._cycle_durations[cycle_mode] > 0):
            
            # Calculate expected end time
            expected_duration = self._cycle_durations[cycle_mode]
            cycle_elapsed = now - self._current_cycle_start
            time_remaining = expected_duration - cycle_elapsed
            
            # If we're approaching the end of a cycle, increase update frequency
            if 0 < time_remaining < CYCLE_END_PREDICTION_WINDOW:
                new_interval = TRANSITION_UPDATE_INTERVAL
                LOGGER.debug(
                    "Cycle %s approaching end (%.1f minutes remaining). Using faster update interval.",
                    cycle_mode, time_remaining / 60
                )
        
        # Update the coordinator's update interval if it changed
        if self.update_interval.total_seconds() != new_interval:
            self.update_interval = timedelta(seconds=new_interval)
            LOGGER.debug("Adjusted update interval to %s seconds", new_interval)
            
        # Schedule next update
        self._next_update_time = now + new_interval
        
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
            if self._last_operation_mode != current_mode:
                if self._last_operation_mode is not None:
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
                                self._cycle_durations[self._last_operation_mode] = new_duration
                                LOGGER.debug(
                                    "Updated duration for mode %s: %.1f minutes", 
                                    self._last_operation_mode, new_duration / 60
                                )
                        
                        # Record transition for analysis
                        self._cycle_transitions.append({
                            "from_mode": self._last_operation_mode,
                            "to_mode": current_mode,
                            "duration": cycle_duration,
                            "timestamp": now,
                        })
                        
                        # Keep only last 20 transitions
                        if len(self._cycle_transitions) > 20:
                            self._cycle_transitions.pop(0)
                
                # New cycle started
                self._current_cycle_start = now
                LOGGER.debug(
                    "Cycle transition detected: %s -> %s", 
                    self._last_operation_mode, current_mode
                )
                
            # Update last mode
            self._last_operation_mode = current_mode
            
            # Calculate elapsed and predicted remaining time
            if self._current_cycle_start is not None:
                elapsed_time = now - self._current_cycle_start
                cycle_status["elapsed_time"] = elapsed_time
                
                # Only predict for cycles with known durations
                if current_mode in [1, 2, 3, 4, 5] and self._cycle_durations[current_mode] > 0:
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
                        seconds_until = (start_time.timestamp() - now_timestamp)
                        # Only consider events in the near future (next 30 minutes)
                        if 0 < seconds_until < 1800:
                            upcoming_events.append({
                                "type": f"{cycle_name}_start",
                                "time": start_time,
                                "seconds_until": seconds_until
                            })
                
                # Process stop time
                stop_time_str = cycle.get("stop")
                if stop_time_str and stop_time_str != "00:00:00":
                    stop_time = self._time_str_to_datetime(stop_time_str)
                    if stop_time:
                        seconds_until = (stop_time.timestamp() - now_timestamp)
                        # Only consider events in the near future (next 30 minutes)
                        if 0 < seconds_until < 1800:
                            upcoming_events.append({
                                "type": f"{cycle_name}_stop",
                                "time": stop_time,
                                "seconds_until": seconds_until
                            })
                
            # Process auxiliary timers that are enabled and switchable
            for aux_id in range(1, 7):
                # First check if this aux is switchable by checking the aux data
                aux_data = next((a for a in self.data.status_value("aux", []) if a.get("id") == aux_id), None)
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
                        seconds_until = (start_time.timestamp() - now_timestamp)
                        # Only consider events in the near future (next 30 minutes)
                        if 0 < seconds_until < 1800:
                            upcoming_events.append({
                                "type": f"aux{aux_id}_start",
                                "time": start_time,
                                "seconds_until": seconds_until
                            })
                
                # Process stop time
                stop_time_str = aux_timer.get("stop")
                if stop_time_str and stop_time_str != "00:00:00":
                    stop_time = self._time_str_to_datetime(stop_time_str)
                    if stop_time:
                        seconds_until = (stop_time.timestamp() - now_timestamp)
                        # Only consider events in the near future (next 30 minutes)
                        if 0 < seconds_until < 1800:
                            upcoming_events.append({
                                "type": f"aux{aux_id}_stop",
                                "time": stop_time,
                                "seconds_until": seconds_until
                            })
                
            # No upcoming events found
            if not upcoming_events:
                return None
                
            # Find the closest upcoming event
            upcoming_events.sort(key=lambda e: e["seconds_until"])
            next_event = upcoming_events[0]
            
            LOGGER.debug(
                "Found upcoming timer event: %s in %.1f minutes",
                next_event["type"],
                next_event["seconds_until"] / 60
            )
            
            return next_event
            
        except (KeyError, TypeError, ValueError) as err:
            LOGGER.debug("Error checking timer events: %s", err)
            return None

    def _time_str_to_datetime(self, time_str: str) -> datetime | None:
        """Convert a time string (HH:MM:SS) to a datetime object for today/tomorrow."""
        if not time_str or time_str == "00:00:00":
            return None
            
        try:
            hour, minute, second = map(int, time_str.split(':'))
            now = datetime.now()
            result = datetime(
                year=now.year, month=now.month, day=now.day,
                hour=hour, minute=minute, second=second
            )
            
            # Handle case where the time is for tomorrow (e.g., if now is 23:00 and time is 01:00)
            if result < now and hour < 12:
                result = result + timedelta(days=1)
                
            return result
        except (ValueError, TypeError):
            return None

    async def _async_update_data(self) -> PoolCopData:
        """Fetch data from PoolCop."""
        try:
            status = await self.poolcopilot.status()
            
            # Check for alarm counts in the status data
            alarm_data = None
            current_time = time.time()
            alarm_count = status.get("PoolCop", {}).get("alarms", {}).get("count", 0)
            
            # Only fetch alarm details when:
            # 1. We haven't fetched alarms in the last 4 hours AND there are alarms, OR
            # 2. The alarm count has changed since our last check
            should_fetch_alarms = (
                (current_time - self._last_alarm_fetch > ALARM_FETCH_INTERVAL and alarm_count > 0) or
                (alarm_count != self._previous_alarm_count)
            )
            
            if should_fetch_alarms:
                LOGGER.debug(
                    "Fetching alarm data: interval=%s, previous_count=%s, current_count=%s",
                    current_time - self._last_alarm_fetch,
                    self._previous_alarm_count,
                    alarm_count
                )
                # Fetch current alarms (only offsetting by 0 to get most recent)
                alarm_data = await self.poolcopilot.alarm_history(0)
                
                # Filter for active alarms
                if alarm_data and "alarms" in alarm_data:
                    # Get alarms that don't have a cleared timestamp
                    self._active_alarms = [
                        alarm for alarm in alarm_data.get("alarms", [])
                        if not alarm.get("cleared")
                    ]
                    
                self._last_alarm_fetch = current_time
                self._previous_alarm_count = alarm_count
            
            # Create a placeholder for the data
            data = PoolCopData(
                status=status,
                alarms=alarm_data,
                active_alarms=self._active_alarms,
                cycle_status=self._update_cycle_tracking(status),
                _coordinator=self,  # Store reference to coordinator for advanced calculations
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
                _coordinator=self,
            )
            
            # Dynamic update interval adjustment based on both cycle and timer events
            interval = NORMAL_UPDATE_INTERVAL
            
            # First check cycle-based timing
            if (data.cycle_status and 
                data.cycle_status.get("remaining_time") is not None and
                0 < data.cycle_status.get("remaining_time", 0) < CYCLE_END_PREDICTION_WINDOW):
                interval = TRANSITION_UPDATE_INTERVAL
                LOGGER.debug(
                    "Cycle approaching end (%.1f minutes remaining). Using faster update interval.",
                    data.cycle_status["remaining_time"] / 60
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
                        seconds_until / 60
                    )
                elif interval == NORMAL_UPDATE_INTERVAL:
                    # Don't wait longer than 5 minutes if there's an upcoming event
                    # but don't override transition interval if it's already set
                    interval = min(NORMAL_UPDATE_INTERVAL, int(seconds_until / 2))
                    LOGGER.debug(
                        "Upcoming timer event %s (%.1f minutes). Setting interval to %d seconds.",
                        next_timer_event["type"],
                        seconds_until / 60,
                        interval
                    )
            
            # Update the coordinator's update interval if needed
            if self.update_interval.total_seconds() != interval:
                self.update_interval = timedelta(seconds=interval)
                LOGGER.debug("Adjusted update interval to %d seconds", interval)
            
            # Save learned data periodically - every hour
            if not hasattr(self, "_last_save_time") or current_time - getattr(self, "_last_save_time", 0) > 3600:
                self.hass.async_create_task(self.async_save_learned_data())
                self._last_save_time = current_time
                
            return data
            
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
                backoff_time
            )
            
            # Update the coordinator's update interval temporarily
            self.update_interval = timedelta(seconds=backoff_time)
            
            # Propagate a more specific error
            raise UpdateFailed("PoolCopilot API rate limit reached, backing off") from err
            
        except PoolCopilotConnectionError as err:
            raise UpdateFailed("Error communicating with PoolCopilot API") from err

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
