"""The Coordinator for PoolCop."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from aiopoolcop import (
    PoolCopAlarm,
    PoolCopAuxiliary,
    PoolCopCloudAPI,
    PoolCopCloudAuthError,
    PoolCopCloudConnectionError,
    PoolCopCloudRateLimitError,
    PoolCopDevice,
    PoolCopState,
    Pool,
    PumpInfo,
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
    CONFIG_UPDATE_INTERVAL,
    DOMAIN,
    LOGGER,
    STORAGE_KEY,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
)

# Default cycle durations (in seconds)
DEFAULT_CYCLE_DURATIONS: dict[str, int] = {
    "Stop": 0,
    "Freeze": 7200,
    "Forced": 7200,
    "Auto": 3600,
    "Timer": 7200,
    "Manual": 0,
    "Paused": 0,
    "External": 0,
}


@dataclass
class PoolCopData:
    """Container for PoolCop cloud API data."""

    device: PoolCopDevice
    state: PoolCopState
    alarms: list[PoolCopAlarm]
    auxiliaries: list[PoolCopAuxiliary]
    pool: Pool | None = None

    # Configuration (fetched every 30 min)
    pump_config: dict[str, Any] | None = None
    filter_config: dict[str, Any] | None = None
    pool_config: dict[str, Any] | None = None
    ph_config: dict[str, Any] | None = None
    orp_config: dict[str, Any] | None = None
    waterlevel_config: dict[str, Any] | None = None
    equipments: dict[str, Any] | None = None
    history: dict[str, Any] | None = None

    # Computed (from coordinator)
    cycle_status: dict[str, Any] | None = None

    @property
    def pump(self) -> PumpInfo | None:
        """Return the first pump info or None."""
        return self.state.pumps[0] if self.state.pumps else None

    def has_active_alarms(self) -> bool:
        """Check if there are any active alarms."""
        return any(a.is_active for a in self.alarms)


class PoolCopDataUpdateCoordinator(DataUpdateCoordinator[PoolCopData]):
    """Class to manage fetching PoolCop data from cloud API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: PoolCopCloudAPI,
        poolcop_id: int,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize global PoolCop data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.api = api
        self.poolcop_id = poolcop_id

        # Initialize pump flow rates from options (preferred) or data
        self.flow_rates: dict[str, float] = {}
        for speed_key, conf_key in (
            ("Speed1", CONF_FLOW_RATE_1),
            ("Speed2", CONF_FLOW_RATE_2),
            ("Speed3", CONF_FLOW_RATE_3),
        ):
            value = config_entry.options.get(conf_key, config_entry.data.get(conf_key))
            if value is not None:
                self.flow_rates[speed_key] = float(value)

        # Setup storage for persisting learned data
        self._store: Store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{poolcop_id}")

        # Daily filtration volume tracking
        self._daily_volume: float = 0.0
        self._daily_volume_date: str | None = None
        self._last_flow_update: float | None = None

        # Cycle tracking
        self._last_operation_mode: str | None = None
        self._current_cycle_start: float | None = None
        self._cycle_durations: dict[str, int] = dict(DEFAULT_CYCLE_DURATIONS)

        # Config fetch tracking
        self._last_config_fetch: float = 0.0

    def get_current_flow_rate(self) -> float:
        """Return the current effective flow rate in m3/h."""
        if not hasattr(self, "data") or self.data is None:
            return 0.0

        pump = self.data.pump
        if pump is None or not pump.pump_state:
            return 0.0

        # Valve must be in a flowing position
        if pump.valve_position not in ("Filter", "Bypass", "Rinse"):
            return 0.0

        return self.flow_rates.get(pump.current_speed, 0.0)

    def _update_daily_volume(self) -> None:
        """Accumulate filtered volume based on current flow rate and elapsed time."""
        now = time.monotonic()

        try:
            today = datetime.now().strftime("%Y-%m-%d")
        except Exception:
            today = None

        if today and today != self._daily_volume_date:
            self._daily_volume = 0.0
            self._daily_volume_date = today

        if self._last_flow_update is not None:
            elapsed_seconds = now - self._last_flow_update
            if 0 < elapsed_seconds <= 600:
                flow_rate = self.get_current_flow_rate()
                self._daily_volume += flow_rate * (elapsed_seconds / 3600.0)

        self._last_flow_update = now

    @property
    def planned_remaining_volume(self) -> float:
        """Return the planned remaining filtration volume in m3 for today."""
        if not self.data:
            return 0.0

        pump = self.data.pump
        if pump is None:
            return 0.0

        flow = self.get_current_flow_rate()
        if flow <= 0:
            return 0.0

        # Estimate remaining hours until midnight
        try:
            now = datetime.now()
            midnight = now.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)
            remaining_hours = min((midnight - now).total_seconds() / 3600.0, 23.0)
        except Exception:
            return 0.0

        return round(flow * remaining_hours, 3)

    @property
    def planned_remaining_turnovers(self) -> float | None:
        """Return planned remaining turnovers."""
        if not self.data or not self.data.pool_config:
            return None
        pool_volume = self.data.pool_config.get("volume")
        if not pool_volume or pool_volume <= 0:
            return None
        return round(self.planned_remaining_volume / pool_volume, 2)

    @property
    def daily_volume(self) -> float:
        """Return the accumulated daily filtration volume in m3."""
        return round(self._daily_volume, 3)

    @property
    def daily_turnovers(self) -> float | None:
        """Return the number of pool turnovers today."""
        if not hasattr(self, "data") or self.data is None or not self.data.pool_config:
            return None
        pool_volume = self.data.pool_config.get("volume")
        if not pool_volume or pool_volume <= 0:
            return None
        return round(self._daily_volume / pool_volume, 2)

    def _update_cycle_tracking(self, state: PoolCopState) -> dict[str, Any]:
        """Track cycle changes and update predictions."""
        cycle_status: dict[str, Any] = {
            "previous_mode": self._last_operation_mode,
            "predicted_end": None,
            "elapsed_time": None,
            "remaining_time": None,
        }

        try:
            current_mode = state.status
            now = time.time()

            if (
                self._last_operation_mode != current_mode
                and self._last_operation_mode is not None
            ):
                if self._current_cycle_start is not None:
                    cycle_duration = now - self._current_cycle_start
                    old_duration = self._cycle_durations.get(
                        self._last_operation_mode, 0
                    )
                    if old_duration > 0:
                        new_duration = int(
                            (0.3 * cycle_duration) + (0.7 * old_duration)
                        )
                        self._cycle_durations[self._last_operation_mode] = new_duration

                self._current_cycle_start = now

            self._last_operation_mode = current_mode

            if self._current_cycle_start is not None:
                elapsed_time = now - self._current_cycle_start
                cycle_status["elapsed_time"] = elapsed_time

                expected = self._cycle_durations.get(current_mode, 0)
                if expected > 0:
                    remaining_time = max(0, expected - elapsed_time)
                    cycle_status["remaining_time"] = remaining_time
                    cycle_status["predicted_end"] = now + remaining_time

        except (KeyError, TypeError):
            pass

        return cycle_status

    async def _async_fetch_configs(self) -> dict[str, Any]:
        """Fetch configuration endpoints (less frequently)."""
        configs: dict[str, Any] = {}
        try:
            configs["pump_config"] = await self.api.get_pump_config(self.poolcop_id)
        except Exception:
            LOGGER.debug("Failed to fetch pump config")

        try:
            configs["filter_config"] = await self.api.get_filter_config(self.poolcop_id)
        except Exception:
            LOGGER.debug("Failed to fetch filter config")

        try:
            configs["pool_config"] = await self.api.get_pool_config(self.poolcop_id)
        except Exception:
            LOGGER.debug("Failed to fetch pool config")

        try:
            configs["ph_config"] = await self.api.get_ph_config(self.poolcop_id)
        except Exception:
            LOGGER.debug("Failed to fetch pH config")

        try:
            configs["orp_config"] = await self.api.get_orp_config(self.poolcop_id)
        except Exception:
            LOGGER.debug("Failed to fetch ORP config")

        try:
            configs["waterlevel_config"] = await self.api.get_waterlevel_config(
                self.poolcop_id
            )
        except Exception:
            LOGGER.debug("Failed to fetch water level config")

        try:
            configs["equipments"] = await self.api.get_equipments(self.poolcop_id)
        except Exception:
            LOGGER.debug("Failed to fetch equipments")

        try:
            configs["history"] = await self.api.get_history(self.poolcop_id)
        except Exception:
            LOGGER.debug("Failed to fetch history")

        return configs

    async def _async_update_data(self) -> PoolCopData:
        """Fetch data from PoolCop cloud API."""
        try:
            # Always fetch state, alarms, auxiliaries
            state = await self.api.get_state(self.poolcop_id)
            alarms = await self.api.get_alarms(self.poolcop_id)
            auxiliaries = await self.api.get_auxiliaries(self.poolcop_id)

            # Fetch device info (contains nickname, connection status)
            device = await self.api.get_poolcop(self.poolcop_id)

            # Fetch pool info
            pool = None
            if device.pool_id:
                try:
                    pool = await self.api.get_pool(device.pool_id)
                except Exception:
                    LOGGER.debug("Failed to fetch pool info")

            # Fetch configs less frequently
            now = time.time()
            configs: dict[str, Any] = {}
            if now - self._last_config_fetch > CONFIG_UPDATE_INTERVAL:
                configs = await self._async_fetch_configs()
                self._last_config_fetch = now
            elif hasattr(self, "data") and self.data is not None:
                # Carry forward previous configs
                configs = {
                    "pump_config": self.data.pump_config,
                    "filter_config": self.data.filter_config,
                    "pool_config": self.data.pool_config,
                    "ph_config": self.data.ph_config,
                    "orp_config": self.data.orp_config,
                    "waterlevel_config": self.data.waterlevel_config,
                    "equipments": self.data.equipments,
                    "history": self.data.history,
                }

            data = PoolCopData(
                device=device,
                state=state,
                alarms=alarms,
                auxiliaries=auxiliaries,
                pool=pool,
                cycle_status=self._update_cycle_tracking(state),
                **configs,
            )

            # Accumulate daily filtration volume
            self._update_daily_volume()

            # Save learned data periodically
            current_time = time.time()
            if (
                not hasattr(self, "_last_save_time")
                or current_time - getattr(self, "_last_save_time", 0) > 3600
            ):
                self.hass.async_create_task(self.async_save_learned_data())
                self._last_save_time = current_time

        except PoolCopCloudAuthError as err:
            raise ConfigEntryAuthFailed("OAuth2 token is invalid or expired") from err
        except PoolCopCloudRateLimitError as err:
            retry_after = err.retry_after or 60
            self.update_interval = timedelta(seconds=retry_after)
            LOGGER.warning("Cloud API rate limit hit, retrying in %ds", retry_after)
            raise UpdateFailed("Cloud API rate limit exceeded") from err
        except PoolCopCloudConnectionError as err:
            raise UpdateFailed("Error communicating with PoolCop cloud API") from err
        except Exception as err:
            LOGGER.exception("Unexpected error processing PoolCop data: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err
        else:
            return data

    async def async_save_learned_data(self) -> None:
        """Save learned data to storage."""
        save_data = {
            "cycle_durations": self._cycle_durations,
            "flow_rates": self.flow_rates,
            "daily_volume": self._daily_volume,
            "daily_volume_date": self._daily_volume_date,
        }
        await self._store.async_save(save_data)

    async def async_load_learned_data(self) -> None:
        """Load learned data from storage."""
        stored_data = await self._store.async_load()
        if stored_data:
            if "cycle_durations" in stored_data:
                self._cycle_durations.update(stored_data["cycle_durations"])

            if "flow_rates" in stored_data:
                self.flow_rates.update(stored_data["flow_rates"])

            if "daily_volume" in stored_data and "daily_volume_date" in stored_data:
                today = datetime.now().strftime("%Y-%m-%d")
                if stored_data["daily_volume_date"] == today:
                    self._daily_volume = float(stored_data["daily_volume"])
                    self._daily_volume_date = today

    async def async_config_entry_first_refresh(self) -> None:
        """First refresh handling."""
        await self.async_load_learned_data()
        # Force config fetch on first refresh
        self._last_config_fetch = 0.0
        await super().async_config_entry_first_refresh()

    # Command methods — direct on/off via cloud API

    async def set_pump(self, on: bool) -> None:
        """Turn pump on or off."""
        await self.api.set_pump(self.poolcop_id, on=on)
        LOGGER.debug("Set pump %s", "on" if on else "off")

    async def set_pump_speed(self, speed: str) -> None:
        """Set the pump speed."""
        await self.api.set_pump_speed(self.poolcop_id, speed)
        LOGGER.debug("Set pump speed to %s", speed)

    async def set_valve_position(self, position: str) -> None:
        """Set the valve position."""
        await self.api.set_valve_position(self.poolcop_id, position)
        LOGGER.debug("Set valve position to %s", position)

    async def clear_alarm(self, code: str) -> None:
        """Clear a specific alarm by code."""
        await self.api.clear_alarm(self.poolcop_id, code)
        LOGGER.debug("Cleared alarm %s", code)

    async def clear_all_alarms(self) -> None:
        """Clear all active alarms."""
        if not self.data:
            return
        for alarm in self.data.alarms:
            if alarm.is_active and alarm.code:
                await self.api.clear_alarm(self.poolcop_id, alarm.code)
        LOGGER.debug("Cleared all active alarms")

    async def set_auxiliary(self, module: str, aux: str, on: bool) -> None:
        """Set an auxiliary output on or off."""
        await self.api.set_auxiliary(self.poolcop_id, module, aux, on=on)
        LOGGER.debug("Set auxiliary %s/%s %s", module, aux, "on" if on else "off")

    async def set_forced_filtration(self, mode: str) -> None:
        """Set forced filtration mode."""
        await self.api.set_forced_filtration(self.poolcop_id, mode)
        LOGGER.debug("Set forced filtration to %s", mode)
