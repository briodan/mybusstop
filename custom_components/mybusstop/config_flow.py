from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_ROUTE_ID
from .api import MyBusStopApi, MyBusStopAuthError

_LOGGER = logging.getLogger(__name__)


async def _validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the user input by logging in once."""
    session = async_get_clientsession(hass)
    api = MyBusStopApi(
        session,
        username=data["username"],
        password=data["password"],
        route_id=int(data[CONF_ROUTE_ID]),
    )

    await api.async_login()
    # If login succeeded, we can also test one getCurrentNEW
    await api.async_get_current()

    return {"title": f"MyBusStop Route {data[CONF_ROUTE_ID]}"}


class MyBusStopConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MyBusStop."""

    VERSION = 1

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
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
                    data={
                        "username": user_input["username"],
                        "password": user_input["password"],
                        CONF_ROUTE_ID: int(user_input[CONF_ROUTE_ID]),
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required("username"): str,
                vol.Required("password"): str,
                vol.Required(CONF_ROUTE_ID): int,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
