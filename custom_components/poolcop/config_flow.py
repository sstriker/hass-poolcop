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
from homeassistant.const import CONF_API_KEY, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for poolcop."""

    VERSION = 1

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
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(
                info[CONF_UNIQUE_ID], raise_on_progress=False
            )
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
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
        await poolcopilot.status()
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
    }


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
