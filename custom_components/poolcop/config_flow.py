"""Config flow for PoolCop integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from poolcop import (  # type: ignore[attr-defined]  # namespace collision with integration dir
    PoolCopilot,
    PoolCopilotConnectionError,
    PoolCopilotError,
    PoolCopilotInvalidKeyError,
)

from .const import CONF_FLOW_RATE_1, CONF_FLOW_RATE_2, CONF_FLOW_RATE_3, DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for poolcop."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api_key: str | None = None
        self._unique_id: str | None = None
        self._pool_info: dict[str, Any] = {}
        self._pump_nb_speeds: int = 3
        self._pump_flowrate: float = 0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)

            self._api_key = user_input[CONF_API_KEY]
            self._unique_id = info.get(CONF_UNIQUE_ID)
            self._pool_info = info.get("pool_info", {})

            settings = self._pool_info.get("settings", {})
            pump_settings = settings.get("pump", {})
            nb_speed = pump_settings.get("nb_speed")

            if nb_speed is not None:
                self._pump_nb_speeds = int(nb_speed)
                LOGGER.debug("Detected pump with %s speeds", self._pump_nb_speeds)

            single_flowrate = pump_settings.get("flowrate")
            if single_flowrate and isinstance(single_flowrate, (str, int, float)):
                try:
                    self._pump_flowrate = float(single_flowrate)
                    LOGGER.debug(
                        "Detected flow rate from API: %s m³/h", self._pump_flowrate
                    )
                except ValueError, TypeError:
                    LOGGER.warning(
                        "Failed to convert flowrate value to float: %s", single_flowrate
                    )

            return await self.async_step_flow_rates()
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except (PoolCopilotError, ValueError, KeyError, AttributeError) as err:
            LOGGER.exception("Error during configuration: %s", err)
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_flow_rates(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the flow rates configuration step."""
        if user_input is None:
            schema_dict = {}
            flow_rate = self._pump_flowrate

            schema_dict[vol.Required(CONF_FLOW_RATE_1, default=flow_rate)] = vol.Coerce(
                float
            )

            if self._pump_nb_speeds >= 2:
                schema_dict[vol.Required(CONF_FLOW_RATE_2, default=flow_rate)] = (
                    vol.Coerce(float)
                )

            if self._pump_nb_speeds >= 3:
                schema_dict[vol.Required(CONF_FLOW_RATE_3, default=flow_rate)] = (
                    vol.Coerce(float)
                )

            data_schema = vol.Schema(schema_dict)

            description_placeholders = {
                "pump_speeds": self._pump_nb_speeds,
                "vol": self._pool_info.get("settings", {})
                .get("pool", {})
                .get("volume", "Unknown"),
                "flowrate": self._pump_flowrate,
            }

            return self.async_show_form(
                step_id="flow_rates",
                data_schema=data_schema,
                description_placeholders=description_placeholders,
            )

        # Store API key in data, flow rates in options
        data = {
            CONF_API_KEY: self._api_key,
            "pump_speeds": self._pump_nb_speeds,
        }

        options: dict[str, Any] = {}
        if CONF_FLOW_RATE_1 in user_input:
            options[CONF_FLOW_RATE_1] = user_input[CONF_FLOW_RATE_1]
        if CONF_FLOW_RATE_2 in user_input and self._pump_nb_speeds >= 2:
            options[CONF_FLOW_RATE_2] = user_input[CONF_FLOW_RATE_2]
        if CONF_FLOW_RATE_3 in user_input and self._pump_nb_speeds >= 3:
            options[CONF_FLOW_RATE_3] = user_input[CONF_FLOW_RATE_3]

        await self.async_set_unique_id(self._unique_id, raise_on_progress=False)

        return self.async_create_entry(
            title="PoolCop",
            data=data,
            options=options,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauth when the API key becomes invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation step."""
        errors = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except (PoolCopilotError, ValueError, KeyError, AttributeError) as err:
                LOGGER.exception("Error during reauth: %s", err)
                errors["base"] = "unknown"
            else:
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                if entry:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={**entry.data, CONF_API_KEY: user_input[CONF_API_KEY]},
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> PoolCopOptionsFlow:
        """Get the options flow handler."""
        return PoolCopOptionsFlow(config_entry)


class PoolCopOptionsFlow(config_entries.OptionsFlow):
    """Handle PoolCop options flow for reconfiguring flow rates."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current flow rate values from options (or data for migrated entries)
        current_options = self._config_entry.options
        current_data = self._config_entry.data

        pump_nb_speeds = current_data.get("pump_speeds", 3)

        schema_dict = {}

        # Current values: prefer options, fall back to data (pre-migration entries)
        fr1 = current_options.get(
            CONF_FLOW_RATE_1, current_data.get(CONF_FLOW_RATE_1, 0)
        )
        schema_dict[vol.Required(CONF_FLOW_RATE_1, default=fr1)] = vol.Coerce(float)

        if pump_nb_speeds >= 2:
            fr2 = current_options.get(
                CONF_FLOW_RATE_2, current_data.get(CONF_FLOW_RATE_2, 0)
            )
            schema_dict[vol.Required(CONF_FLOW_RATE_2, default=fr2)] = vol.Coerce(float)

        if pump_nb_speeds >= 3:
            fr3 = current_options.get(
                CONF_FLOW_RATE_3, current_data.get(CONF_FLOW_RATE_3, 0)
            )
            schema_dict[vol.Required(CONF_FLOW_RATE_3, default=fr3)] = vol.Coerce(float)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    poolcopilot = PoolCopilot(
        session=async_get_clientsession(hass),
        api_key=data[CONF_API_KEY],
    )

    try:
        status = await poolcopilot.status()
    except PoolCopilotConnectionError as exception:
        raise CannotConnect from exception
    except PoolCopilotInvalidKeyError as exception:
        raise InvalidAuth from exception
    except PoolCopilotError as exception:
        raise CannotConnect from exception

    return {
        "title": "PoolCop",
        CONF_UNIQUE_ID: poolcopilot.poolcop_id,
        "pool_info": status.get("PoolCop", {}),
    }


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
