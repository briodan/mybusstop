from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_ROUTE_ID
from .api import MyBusStopApi, MyBusStopAuthError
from .coordinator import MyBusStopCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "device_tracker"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MyBusStop from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    username: str = entry.data["username"]
    password: str = entry.data["password"]
    route_id: int = entry.data[CONF_ROUTE_ID]

    # Create a temporary API to log in and discover available routes
    api_template = MyBusStopApi(session, username, password, route_id)

    try:
        await api_template.async_login()
    except MyBusStopAuthError as err:
        _LOGGER.error("Failed to log in to MyBusStop: %s", err)
        raise

    # Try to discover routes from the logged-in page. If discovery fails,
    # fall back to the configured `route_id` only.
    routes = await api_template.async_get_routes()
    if not routes:
        # fallback: single route from config entry
        routes = [{"id": route_id, "name": f"Route {route_id}"}]

    apis: dict[int, MyBusStopApi] = {}
    coordinators: dict[int, MyBusStopCoordinator] = {}

    for r in routes:
        rid = int(r["id"])
        api_i = MyBusStopApi(session, username, password, rid)
        # ensure logged in for each API instance (cookies/session already set)
        try:
            await api_i.async_login()
        except MyBusStopAuthError:
            _LOGGER.warning("Login failed for route %s, skipping", rid)
            continue

        coord = MyBusStopCoordinator(hass, api_i)
        # perform initial refresh for each coordinator
        try:
            await coord.async_config_entry_first_refresh()
        except Exception as err:  # keep going if one route fails
            _LOGGER.debug("Initial refresh failed for route %s: %s", rid, err)

        apis[rid] = api_i
        coordinators[rid] = coord

    hass.data[DOMAIN][entry.entry_id] = {
        "routes": routes,
        "apis": apis,
        "coordinators": coordinators,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a MyBusStop config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
