"""Config flow for PoolCop integration."""
from __future__ import annotations

from typing import Any

from poolcop import (
    PoolCopilot,
    PoolCopilotConnectionError,
    PoolCopilotError,
    PoolCopilotInvalidKeyError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    LOGGER,
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for poolcop."""

    VERSION = 1
    
    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api_key: str | None = None
        self._unique_id: str | None = None
        self._pool_info: dict[str, Any] = {}
        self._pump_nb_speeds: int = 3  # Default to 3 speeds if not found
        self._pump_flowrate: float = 0  # Store detected pump flow rate, default to 0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
            
            # Store API key and pool info for next steps
            self._api_key = user_input[CONF_API_KEY]
            self._unique_id = info.get(CONF_UNIQUE_ID)
            self._pool_info = info.get("pool_info", {})
            
            # Get the number of pump speeds if available
            settings = self._pool_info.get("settings", {})
            pump_settings = settings.get("pump", {})
            nb_speed = pump_settings.get("nb_speed")
            
            if nb_speed is not None:
                self._pump_nb_speeds = int(nb_speed)
                LOGGER.debug("Detected pump with %s speeds", self._pump_nb_speeds)
            
            # Get the pump flow rate if available
            single_flowrate = pump_settings.get("flowrate")
            if single_flowrate and isinstance(single_flowrate, (str, int, float)):
                try:
                    self._pump_flowrate = float(single_flowrate)
                    LOGGER.debug("Detected flow rate from API: %s m³/h", self._pump_flowrate)
                except (ValueError, TypeError):
                    LOGGER.warning("Failed to convert flowrate value to float: %s", single_flowrate)
                
            # Continue to the flow rate configuration step
            return await self.async_step_flow_rates()
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
        
    async def async_step_flow_rates(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the flow rates configuration step."""
        if user_input is None:
            # Create a dynamic schema based on number of pump speeds
            schema_dict = {}
            
            # Just use the single pump flowrate for all speeds
            flow_rate = self._pump_flowrate
            
            # Add flow rate fields based on detected speeds (always include speed 1)
            schema_dict[vol.Required(CONF_FLOW_RATE_1, default=flow_rate)] = vol.Coerce(float)
            
            # Add speed 2 if pump has at least 2 speeds
            if self._pump_nb_speeds >= 2:
                schema_dict[vol.Required(CONF_FLOW_RATE_2, default=flow_rate)] = vol.Coerce(float)
                
            # Add speed 3 if pump has 3 speeds
            if self._pump_nb_speeds >= 3:
                schema_dict[vol.Required(CONF_FLOW_RATE_3, default=flow_rate)] = vol.Coerce(float)
                
            # Create schema with just the relevant flow rate fields
            data_schema = vol.Schema(schema_dict)
            
            # Display pump info in the form description
            description_placeholders = {
                "pump_speeds": self._pump_nb_speeds,
                "vol": self._pool_info.get("settings", {}).get("pool", {}).get("volume", "Unknown"),
                "flowrate": self._pump_flowrate
            }
            
            return self.async_show_form(
                step_id="flow_rates", 
                data_schema=data_schema,
                description_placeholders=description_placeholders,
            )
            
        # Now that we have both API key and flow rates, create the config entry
        data = {
            CONF_API_KEY: self._api_key,
        }
        
        # Only include configured flow rates
        if CONF_FLOW_RATE_1 in user_input:
            data[CONF_FLOW_RATE_1] = user_input[CONF_FLOW_RATE_1]
            
        if CONF_FLOW_RATE_2 in user_input and self._pump_nb_speeds >= 2:
            data[CONF_FLOW_RATE_2] = user_input[CONF_FLOW_RATE_2]
            
        if CONF_FLOW_RATE_3 in user_input and self._pump_nb_speeds >= 3:
            data[CONF_FLOW_RATE_3] = user_input[CONF_FLOW_RATE_3]

        # Include pump speeds information to help with sensor creation
        data["pump_speeds"] = self._pump_nb_speeds
        
        await self.async_set_unique_id(self._unique_id, raise_on_progress=False)
        
        return self.async_create_entry(
            title="PoolCop",
            data=data,
        )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

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

    # Return info that you want to store in the config entry.
    return {
        "title": "PoolCop",
        CONF_UNIQUE_ID: poolcopilot.poolcop_id,
        "pool_info": status.get("PoolCop", {}),  # Store full pool info for configuration
    }


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
