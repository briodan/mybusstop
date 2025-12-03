from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_time_change
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_DISCOVERY_TIME,
    DEFAULT_DISCOVERY_TIME,
)
from .api import MyBusStopApi, MyBusStopAuthError

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "device_tracker"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MyBusStop from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    username: str = entry.data["username"]
    password: str = entry.data["password"]

    # Create a temporary API to log in and discover available routes
    api_template = MyBusStopApi(session, username, password, 0)

    try:
        await api_template.async_login()
    except MyBusStopAuthError as err:
        _LOGGER.error("Failed to log in to MyBusStop: %s", err)
        raise

    # Discover routes from the logged-in page
    routes = await api_template.async_get_routes()
    if not routes:
        _LOGGER.error("No routes found for this account")
        return False

    apis: dict[int, MyBusStopApi] = {}

    for r in routes:
        rid = int(r["id"])
        api_i = MyBusStopApi(session, username, password, rid)
        # ensure logged in for each API instance (cookies/session already set)
        try:
            await api_i.async_login()
        except MyBusStopAuthError:
            _LOGGER.warning("Login failed for route %s, skipping", rid)
            continue

        apis[rid] = api_i

    # Initialize data storage
    hass.data[DOMAIN][entry.entry_id] = {
        "routes": routes,
        "apis": apis,
        "data": {},
    }
    
    # Fetch initial data for all routes
    for rid, api in apis.items():
        try:
            data = await api.async_get_current()
            hass.data[DOMAIN][entry.entry_id]["data"][rid] = data
            _LOGGER.debug("Initial data fetched for route %s", rid)
        except Exception as err:
            _LOGGER.warning("Failed to fetch initial data for route %s: %s", rid, err)

    # Schedule daily route discovery to catch changes (e.g., Friday-only route).
    async def _discover_and_reload_if_changed(now) -> None:
        try:
            new_routes = await api_template.async_get_routes()
        except Exception as err:  # don't crash the event loop
            _LOGGER.debug("Route discovery failed: %s", err)
            return

        old_routes = hass.data[DOMAIN][entry.entry_id].get("routes", [])
        old_ids = [int(r["id"]) for r in old_routes]
        new_ids = [int(r["id"]) for r in new_routes]

        # Compute newly discovered routes (add-only; do not remove disappeared routes)
        add_ids = sorted(set(new_ids) - set(old_ids))
        if add_ids:
            _LOGGER.info("MyBusStop new routes discovered, adding: %s", add_ids)
            
            # Create API instances for new routes
            apis_dict = hass.data[DOMAIN][entry.entry_id]["apis"]
            routes_list = hass.data[DOMAIN][entry.entry_id]["routes"]
            
            for rid in add_ids:
                api_i = MyBusStopApi(session, username, password, rid)
                try:
                    await api_i.async_login()
                    apis_dict[rid] = api_i
                    
                    # Find route name from new_routes
                    route_info = next((r for r in new_routes if int(r["id"]) == rid), None)
                    route_name = route_info.get("name", f"Route {rid}") if route_info else f"Route {rid}"
                    routes_list.append({"id": rid, "name": route_name})
                    
                    _LOGGER.info("Added new route %s: %s", rid, route_name)
                except MyBusStopAuthError:
                    _LOGGER.warning("Login failed for new route %s, skipping", rid)
                    continue
            
            # Reload to create new entities
            try:
                await hass.config_entries.async_reload(entry.entry_id)
            except Exception as err:
                _LOGGER.exception("Failed to reload MyBusStop entry after adding new routes: %s", err)

    # Schedule discovery at specific time daily
    discovery_time_str = entry.options.get(CONF_DISCOVERY_TIME, DEFAULT_DISCOVERY_TIME)
    try:
        hour, minute = map(int, discovery_time_str.split(":"))
    except (ValueError, AttributeError):
        _LOGGER.warning("Invalid discovery time '%s', using default", discovery_time_str)
        hour, minute = 2, 0
    
    handle = async_track_time_change(
        hass, _discover_and_reload_if_changed, hour=hour, minute=minute, second=0
    )
    hass.data[DOMAIN][entry.entry_id]["routes_update_unsub"] = handle
    
    # Register listener for options updates
    async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Handle options update."""
        await hass.config_entries.async_reload(entry.entry_id)
    
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register service for on-demand polling
    async def handle_update_bus_location(call):
        """Handle the service call to update bus location."""
        route_id = call.data.get("route_id")
        apis_dict = hass.data[DOMAIN][entry.entry_id]["apis"]
        
        if route_id:
            # Update specific route - try to convert to int for lookup
            try:
                route_key = int(route_id)
            except (ValueError, TypeError):
                route_key = route_id
            
            api = apis_dict.get(route_key)
            if api:
                try:
                    data = await api.async_get_current()
                    # Store the data for entities to access
                    if "data" not in hass.data[DOMAIN][entry.entry_id]:
                        hass.data[DOMAIN][entry.entry_id]["data"] = {}
                    hass.data[DOMAIN][entry.entry_id]["data"][route_key] = data
                    # Trigger entity updates
                    hass.bus.async_fire(f"{DOMAIN}_update", {"route_id": route_key})
                    _LOGGER.info("Updated bus location for route %s", route_id)
                except Exception as err:
                    _LOGGER.error("Failed to update route %s: %s", route_id, err)
            else:
                _LOGGER.warning("Route %s not found", route_id)
        else:
            # Update all routes
            if "data" not in hass.data[DOMAIN][entry.entry_id]:
                hass.data[DOMAIN][entry.entry_id]["data"] = {}
            for route_key, api in apis_dict.items():
                try:
                    data = await api.async_get_current()
                    hass.data[DOMAIN][entry.entry_id]["data"][route_key] = data
                except Exception as err:
                    _LOGGER.error("Failed to update route %s: %s", route_key, err)
            # Trigger entity updates for all routes
            hass.bus.async_fire(f"{DOMAIN}_update", {})
            _LOGGER.info("Updated bus location for all routes")
    
    hass.services.async_register(
        DOMAIN,
        "update_bus_location",
        handle_update_bus_location,
    )
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a MyBusStop config entry."""
    # Cancel scheduled route discovery if present
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    unsub = data.get("routes_update_unsub")
    if unsub:
        try:
            unsub()
        except Exception:
            _LOGGER.debug("Failed to cancel route discovery unsub", exc_info=True)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # Unregister service if this is the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "update_bus_location")
    return unload_ok
