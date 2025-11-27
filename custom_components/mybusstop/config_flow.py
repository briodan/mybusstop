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
    CONF_MORNING_PICKUP_TIME,
    CONF_AFTERNOON_DROPOFF_TIME,
    CONF_FRIDAY_DROPOFF_TIME,
)
from .api import MyBusStopApi, MyBusStopAuthError

_LOGGER = logging.getLogger(__name__)


async def _validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the user input by logging in once."""
    session = async_get_clientsession(hass)
    api = MyBusStopApi(
        session,
        username=data["username"],
        password=data["password"],
        route_id=None,
    )

    await api.async_login()
    # If login succeeded, try to discover routes to provide a friendly title.
    try:
        routes = await api.async_get_routes()
    except Exception:
        routes = []

    if routes:
        first = routes[0]
        return {"title": f"MyBusStop {first.get('name', first.get('id'))}"}

    return {"title": "MyBusStop"}


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
                        CONF_MORNING_PICKUP_TIME: user_input.get(CONF_MORNING_PICKUP_TIME, "08:19"),
                        CONF_AFTERNOON_DROPOFF_TIME: user_input.get(CONF_AFTERNOON_DROPOFF_TIME, "15:52"),
                        CONF_FRIDAY_DROPOFF_TIME: user_input.get(CONF_FRIDAY_DROPOFF_TIME, "13:16"),
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required("username"): str,
                vol.Required("password"): str,
                # Route ID is no longer requested at setup; routes will be
                # discovered from the logged-in page instead.
                vol.Optional(CONF_MORNING_PICKUP_TIME, default="08:19"): str,
                vol.Optional(CONF_AFTERNOON_DROPOFF_TIME, default="15:52"): str,
                vol.Optional(CONF_FRIDAY_DROPOFF_TIME, default="13:16"): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
