from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_DISCOVERY_TIME,
    DEFAULT_DISCOVERY_TIME,
)
from .api import MyBusStopApi, MyBusStopAuthError

_LOGGER = logging.getLogger(__name__)


async def _validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the user input by logging in."""
    session = async_get_clientsession(hass)
    api = MyBusStopApi(
        session,
        username=data["username"],
        password=data["password"],
    )

    await api.async_login()
    
    return {"title": "MyBusStop"}


class MyBusStopConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MyBusStop."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow for this handler."""
        return MyBusStopOptionsFlow(config_entry)

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial step - username and password."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            try:
                info = await _validate_input(self.hass, user_input)
            except MyBusStopAuthError:
                errors["base"] = "auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during MyBusStop validation")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=info["title"],
                    data={"username": user_input["username"], "password": user_input["password"]},
                    options={CONF_DISCOVERY_TIME: DEFAULT_DISCOVERY_TIME},
                )

        data_schema = vol.Schema(
            {
                vol.Required("username"): str,
                vol.Required("password"): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )


class MyBusStopOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for MyBusStop."""

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DISCOVERY_TIME,
                        default=self.config_entry.options.get(
                            CONF_DISCOVERY_TIME, DEFAULT_DISCOVERY_TIME
                        ),
                    ): str,
                }
            ),
        )
