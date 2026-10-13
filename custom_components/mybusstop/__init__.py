from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_time_change
from datetime import date, timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_DISCOVERY_TIME,
    DEFAULT_DISCOVERY_TIME,
    ROUTE_PRUNE_DAYS,
    ROUTE_REFRESH_MINUTES,
)
from .api import MyBusStopApi, MyBusStopAuthError

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "device_tracker"]


def _merge_routes(known: list[dict], listed: list[dict], today: date) -> list[dict]:
    """Merge routes currently listed on the site into the known routes.

    Listed routes are added or get their (daily changing) name refreshed. Known
    routes that are not listed today are kept, since AM/PM/Friday runs are not
    always visible, but are dropped once they have not been listed for
    ROUTE_PRUNE_DAYS (e.g. last school year's route IDs). Nothing is dropped
    when the site lists no routes at all, so a holiday break keeps the list.
    """
    today_str = today.isoformat()
    cutoff = (today - timedelta(days=ROUTE_PRUNE_DAYS)).isoformat()
    listed_by_id = {int(r["id"]): r for r in listed}

    merged: list[dict] = []
    for r in known:
        rid = int(r["id"])
        if rid in listed_by_id:
            continue
        # Routes stored by older versions have no last_listed; start them today.
        last_listed = r.get("last_listed") or today_str
        if listed_by_id and last_listed < cutoff:
            _LOGGER.info(
                "Dropping route %s (%s): not listed since %s",
                rid, r.get("name"), last_listed,
            )
            continue
        merged.append({"id": rid, "name": r.get("name", f"Route {rid}"), "last_listed": last_listed})

    for rid, r in listed_by_id.items():
        merged.append({"id": rid, "name": r["name"], "last_listed": today_str})

    merged.sort(key=lambda r: r["id"])
    return merged

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

    # Discover routes from the logged-in page and merge with the stored ones
    listed = await api_template.async_get_routes()
    if not listed:
        _LOGGER.warning("No routes currently visible on MyBusStop (routes may not be running)")

    stored_routes = entry.data.get("discovered_routes", [])
    routes = _merge_routes(stored_routes, listed, dt_util.now().date())

    if not routes:
        _LOGGER.error(
            "No routes found and no previously stored routes available. "
            "Please set up the integration when at least one bus route is active."
        )
        return False

    _LOGGER.info("Using %d route(s): %s", len(routes), [r["id"] for r in routes])
    if routes != stored_routes:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "discovered_routes": routes}
        )

    # API instances log in lazily on first use (they share the session cookies)
    apis: dict[int, MyBusStopApi] = {
        int(r["id"]): MyBusStopApi(session, username, password, int(r["id"]))
        for r in routes
    }

    # Initialize data storage
    hass.data[DOMAIN][entry.entry_id] = {
        "routes": routes,
        "apis": apis,
        "data": {},
        "options": dict(entry.options),
        "routes_refreshed": dt_util.utcnow(),
    }
    
    # Fetch initial data for all routes
    for rid, api in apis.items():
        try:
            data = await api.async_get_current()
            if data is not None:
                hass.data[DOMAIN][entry.entry_id]["data"][rid] = data
                _LOGGER.debug("Initial data fetched for route %s", rid)
            else:
                _LOGGER.info("Route %s: No data available (route may not be running today)", rid)
        except Exception as err:
            _LOGGER.warning("Failed to fetch initial data for route %s: %s", rid, err)

    async def _async_refresh_routes() -> None:
        """Refresh the route list in place: new IDs, new names, dropped IDs."""
        store = hass.data[DOMAIN][entry.entry_id]
        store["routes_refreshed"] = dt_util.utcnow()
        try:
            listed = await api_template.async_get_routes()
        except Exception as err:  # don't crash the event loop
            _LOGGER.debug("Route discovery failed: %s", err)
            return

        routes_list = store["routes"]
        merged = _merge_routes(routes_list, listed, dt_util.now().date())
        if merged == routes_list:
            return

        old_ids = {int(r["id"]) for r in routes_list}
        new_ids = {int(r["id"]) for r in merged}
        added, removed = new_ids - old_ids, old_ids - new_ids
        if added or removed:
            _LOGGER.info("MyBusStop routes changed: added %s, removed %s", sorted(added), sorted(removed))

        apis_dict = store["apis"]
        for rid in added:
            apis_dict[rid] = MyBusStopApi(session, username, password, rid)
        for rid in removed:
            apis_dict.pop(rid, None)
            store["data"].pop(rid, None)

        # Update in place: the entities hold a reference to this list
        routes_list[:] = merged
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "discovered_routes": merged}
        )
        hass.bus.async_fire(f"{DOMAIN}_update", {})

    async def _scheduled_refresh_routes(now) -> None:
        await _async_refresh_routes()

    # Schedule discovery at specific time daily
    discovery_time_str = entry.options.get(CONF_DISCOVERY_TIME, DEFAULT_DISCOVERY_TIME)
    try:
        hour, minute = map(int, discovery_time_str.split(":"))
    except (ValueError, AttributeError):
        _LOGGER.warning("Invalid discovery time '%s', using default", discovery_time_str)
        hour, minute = 2, 0
    
    handle = async_track_time_change(
        hass, _scheduled_refresh_routes, hour=hour, minute=minute, second=0
    )
    hass.data[DOMAIN][entry.entry_id]["routes_update_unsub"] = handle
    
    # Register listener for options updates
    async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Handle options update (route list saves to entry data don't reload)."""
        store = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
        if store.get("options") == dict(entry.options):
            return
        await hass.config_entries.async_reload(entry.entry_id)
    
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    # Register service for on-demand polling
    async def handle_update_bus_location(call):
        """Handle the service call to update bus location."""
        # Route names change daily and new runs (e.g. Friday PM) can appear
        refreshed = hass.data[DOMAIN][entry.entry_id]["routes_refreshed"]
        if dt_util.utcnow() - refreshed >= timedelta(minutes=ROUTE_REFRESH_MINUTES):
            await _async_refresh_routes()

        apis_dict = hass.data[DOMAIN][entry.entry_id]["apis"]
        
        # Update all routes
        if "data" not in hass.data[DOMAIN][entry.entry_id]:
            hass.data[DOMAIN][entry.entry_id]["data"] = {}
        
        for route_key, api in list(apis_dict.items()):
            try:
                data = await api.async_get_current()
                if data is not None:
                    hass.data[DOMAIN][entry.entry_id]["data"][route_key] = data
                    _LOGGER.debug("Updated route %s with new data", route_key)
                else:
                    _LOGGER.debug("Route %s: No data available (route may not be running)", route_key)
            except Exception as err:
                _LOGGER.error("Failed to update route %s: %s", route_key, err)
        
        # Trigger entity updates
        hass.bus.async_fire(f"{DOMAIN}_update", {})
        _LOGGER.debug("Bus location update completed")
    
    hass.services.async_register(
        DOMAIN,
        "update_bus_location",
        handle_update_bus_location,
    )
    
    # Perform initial data fetch (non-blocking - entities will show as unavailable until data arrives)
    try:
        await handle_update_bus_location(None)
    except Exception as err:
        _LOGGER.warning("Initial data fetch failed (routes may not be running): %s", err)
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
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
