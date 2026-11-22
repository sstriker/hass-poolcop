"""Config flow for PoolCop integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import probatio as vol
from aiopoolcop import (
    Pool,
    PoolCopClientAuthError,
    PoolCopClientConnectionError,
    PoolCopClientError,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
    CONF_MAP_MODE,
    DOMAIN,
    LOGGER,
    MAP_MODE_ALWAYS,
    MAP_MODE_ATTENTION,
)
from .helpers import async_get_client

CONF_DEVICE_ID = "device_id"
CONF_PUMP_SPEEDS = "pump_speeds"
API_KEY_URL = "https://my.poolcop.com/profile/apikey"
FLOW_RATE_KEYS = (CONF_FLOW_RATE_1, CONF_FLOW_RATE_2, CONF_FLOW_RATE_3)

STEP_API_KEY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

FLOW_RATE_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=0,
        max=100,
        step=0.1,
        mode=NumberSelectorMode.BOX,
        unit_of_measurement="m³/h",
    )
)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


async def async_get_account_devices(
    hass: HomeAssistant, api_key: str
) -> list[tuple[Pool, int, str | None]]:
    """Return (pool, device id, device nickname) for every PoolCop of a key."""
    api = async_get_client(hass, api_key)
    try:
        pools = await api.get_pools()
    except PoolCopClientAuthError as err:
        raise InvalidAuth from err
    except PoolCopClientConnectionError as err:
        raise CannotConnect from err
    return [
        (pool, device.id, device.nickname) for pool in pools for device in pool.devices
    ]


def _speed_to_int(speed_str: str) -> int:
    """Convert Speed1/Speed2/Speed3 to int (1 if unknown)."""
    if speed_str.startswith("Speed"):
        try:
            return int(speed_str[5:])
        except ValueError:
            pass
    return 1


def _device_label(pool: Pool, nickname: str | None, device_id: int) -> str:
    """Return a readable label for a PoolCop in the device picker."""
    names = [name for name in (pool.nickname, nickname) if name]
    if len(names) == 2 and names[0] == names[1]:
        names = names[:1]
    location = ", ".join(part for part in (pool.city, pool.country) if part)
    label = " / ".join(names) or f"PoolCop {device_id}"
    if location:
        label = f"{label} ({location})"
    return f"{label} #{device_id}"


class PoolCopConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PoolCop."""

    VERSION = 3

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api_key: str = ""
        self._devices: dict[int, tuple[Pool, str | None]] = {}
        self._title: str = "PoolCop"
        self._pump_nb_speeds: int = 1
        self._pool_volume: float | None = None
        self._flowrate: float = 0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the Client API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY].strip()
            try:
                devices = await async_get_account_devices(self.hass, self._api_key)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except PoolCopClientError:
                LOGGER.exception("Unexpected error listing PoolCop devices")
                errors["base"] = "unknown"
            else:
                configured = self._async_current_ids(include_ignore=False)
                self._devices = {
                    device_id: (pool, nickname)
                    for pool, device_id, nickname in devices
                    if str(device_id) not in configured
                }
                if not devices:
                    errors["base"] = "no_devices"
                elif not self._devices:
                    return self.async_abort(reason="already_configured")
                elif len(self._devices) == 1:
                    return await self._async_select_device(next(iter(self._devices)))
                else:
                    return await self.async_step_device()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_API_KEY_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders={"api_key_url": API_KEY_URL},
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick one of the account's PoolCops."""
        if user_input is not None:
            return await self._async_select_device(int(user_input[CONF_DEVICE_ID]))

        options = [
            SelectOptionDict(
                value=str(device_id),
                label=_device_label(pool, nickname, device_id),
            )
            for device_id, (pool, nickname) in self._devices.items()
        ]
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.LIST
                        )
                    )
                }
            ),
        )

    async def _async_select_device(self, device_id: int) -> ConfigFlowResult:
        """Load the chosen PoolCop and continue to the flow rates."""
        await self.async_set_unique_id(str(device_id))
        self._abort_if_unique_id_configured()

        try:
            device = await async_get_client(self.hass, self._api_key).get_device(
                device_id
            )
        except PoolCopClientError:
            LOGGER.exception("Error loading PoolCop %s", device_id)
            return self.async_abort(reason="cannot_connect")

        pool, nickname = self._devices[device_id]
        self._title = device.nickname or nickname or pool.nickname or "PoolCop"
        self._pool_volume = device.settings.pool.volume
        self._flowrate = device.settings.pool.estimated_flowrate or 0
        filtrations = device.settings.filtrations
        if filtrations:
            self._pump_nb_speeds = min(
                3, max(1, _speed_to_int(filtrations[0].nb_speeds))
            )
        return await self.async_step_flow_rates()

    async def async_step_flow_rates(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the pump flow rate at each speed."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._title,
                data={
                    CONF_API_KEY: self._api_key,
                    CONF_PUMP_SPEEDS: self._pump_nb_speeds,
                },
                options={
                    key: user_input[key]
                    for key in FLOW_RATE_KEYS[: self._pump_nb_speeds]
                    if key in user_input
                },
            )

        return self.async_show_form(
            step_id="flow_rates",
            data_schema=vol.Schema(
                {
                    vol.Required(key, default=self._flowrate): FLOW_RATE_SELECTOR
                    for key in FLOW_RATE_KEYS[: self._pump_nb_speeds]
                }
            ),
            description_placeholders={
                "pump_speeds": str(self._pump_nb_speeds),
                "vol": str(self._pool_volume or "?"),
                "flowrate": str(self._flowrate),
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a rejected API key."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key that can see this PoolCop."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            if error := await self._async_validate_key_for_entry(entry, api_key):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: api_key}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_API_KEY_SCHEMA,
            errors=errors,
            description_placeholders={
                "api_key_url": API_KEY_URL,
                "title": entry.title,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the API key of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            if error := await self._async_validate_key_for_entry(entry, api_key):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: api_key}
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_API_KEY_SCHEMA,
            errors=errors,
            description_placeholders={
                "api_key_url": API_KEY_URL,
                "title": entry.title,
            },
        )

    async def _async_validate_key_for_entry(
        self, entry: ConfigEntry, api_key: str
    ) -> str | None:
        """Return an error key, or None if the key can see the entry's PoolCop."""
        try:
            devices = await async_get_account_devices(self.hass, api_key)
        except InvalidAuth:
            return "invalid_auth"
        except CannotConnect:
            return "cannot_connect"
        except PoolCopClientError:
            LOGGER.exception("Unexpected error validating PoolCop API key")
            return "unknown"
        if not any(str(device_id) == entry.unique_id for _, device_id, _ in devices):
            return "device_not_found"
        return None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> PoolCopOptionsFlow:
        """Get the options flow handler."""
        return PoolCopOptionsFlow()


class PoolCopOptionsFlow(OptionsFlow):
    """Handle PoolCop options: map visibility and pump flow rates."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options flow."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        data = self.config_entry.data
        pump_nb_speeds: int = data.get(CONF_PUMP_SPEEDS, 3)

        schema: dict[Any, Any] = {
            vol.Required(
                CONF_MAP_MODE, default=options.get(CONF_MAP_MODE, MAP_MODE_ALWAYS)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[MAP_MODE_ALWAYS, MAP_MODE_ATTENTION],
                    translation_key=CONF_MAP_MODE,
                )
            ),
        }
        for key in FLOW_RATE_KEYS[:pump_nb_speeds]:
            # Prefer options, fall back to data (pre-migration entries)
            schema[vol.Required(key, default=options.get(key, data.get(key, 0)))] = (
                FLOW_RATE_SELECTOR
            )

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
