"""Config flow for PoolCop integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from aiopoolcop import (
    PoolCopCloudAPI,
    PoolCopCloudAuthError,
    PoolCopCloudConnectionError,
)
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow

from .const import (
    CONF_FLOW_RATE_1,
    CONF_FLOW_RATE_2,
    CONF_FLOW_RATE_3,
    CONF_POOLCOP_ID,
    DOMAIN,
    LOGGER,
)


class ConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Handle a config flow for PoolCop."""

    DOMAIN = DOMAIN
    VERSION = 3

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._devices: list[dict[str, Any]] = []
        self._selected_device: dict[str, Any] | None = None
        self._pump_nb_speeds: int = 3
        self._pump_flowrate: float = 0.0

    @property
    def logger(self):
        """Return logger."""
        return LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": "profile pool.read pool.write"}

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow after OAuth2 completes.

        After OAuth2 is done, we need to select a device and configure flow rates.
        """
        self._async_abort_entries_match()

        # Store the OAuth2 data for later
        self._oauth_data = data

        # Fetch available PoolCop devices
        token = data["token"]["access_token"]
        api = PoolCopCloudAPI(token=token)

        try:
            devices = await api.get_poolcops()
        except PoolCopCloudAuthError:
            return self.async_abort(reason="invalid_auth")
        except PoolCopCloudConnectionError:
            return self.async_abort(reason="cannot_connect")
        finally:
            await api.close()

        if not devices:
            return self.async_abort(reason="no_devices")

        self._devices = [
            {"id": d.id, "nickname": d.nickname or f"PoolCop {d.id}", "uuid": d.uuid}
            for d in devices
        ]

        if len(self._devices) == 1:
            self._selected_device = self._devices[0]
            return await self.async_step_flow_rates()

        return await self.async_step_device_select()

    async def async_step_device_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device selection when multiple PoolCops are available."""
        if user_input is not None:
            device_id = user_input[CONF_POOLCOP_ID]
            self._selected_device = next(
                d for d in self._devices if str(d["id"]) == str(device_id)
            )
            return await self.async_step_flow_rates()

        device_options = {str(d["id"]): d["nickname"] for d in self._devices}

        return self.async_show_form(
            step_id="device_select",
            data_schema=vol.Schema(
                {vol.Required(CONF_POOLCOP_ID): vol.In(device_options)}
            ),
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

            return self.async_show_form(
                step_id="flow_rates",
                data_schema=vol.Schema(schema_dict),
            )

        assert self._selected_device is not None
        device = self._selected_device

        # Set unique_id to prevent duplicate entries
        await self.async_set_unique_id(str(device["id"]))
        self._abort_if_unique_id_configured()

        # Store device ID in data alongside OAuth2 data
        data = {
            **self._oauth_data,
            CONF_POOLCOP_ID: device["id"],
            "pump_speeds": self._pump_nb_speeds,
        }

        options: dict[str, Any] = {}
        if CONF_FLOW_RATE_1 in user_input:
            options[CONF_FLOW_RATE_1] = user_input[CONF_FLOW_RATE_1]
        if CONF_FLOW_RATE_2 in user_input and self._pump_nb_speeds >= 2:
            options[CONF_FLOW_RATE_2] = user_input[CONF_FLOW_RATE_2]
        if CONF_FLOW_RATE_3 in user_input and self._pump_nb_speeds >= 3:
            options[CONF_FLOW_RATE_3] = user_input[CONF_FLOW_RATE_3]

        return self.async_create_entry(
            title=device["nickname"],
            data=data,
            options=options,
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

        current_options = self._config_entry.options
        current_data = self._config_entry.data
        pump_nb_speeds = current_data.get("pump_speeds", 3)

        schema_dict = {}

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
