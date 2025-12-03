from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_MORNING_PICKUP_TIME,
    CONF_AFTERNOON_DROPOFF_TIME,
    CONF_FRIDAY_DROPOFF_TIME,
)
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

        coord = MyBusStopCoordinator(
            hass,
            api_i,
            morning_pickup_time=entry.data.get(CONF_MORNING_PICKUP_TIME, "08:19"),
            afternoon_dropoff_time=entry.data.get(CONF_AFTERNOON_DROPOFF_TIME, "15:52"),
            friday_dropoff_time=entry.data.get(CONF_FRIDAY_DROPOFF_TIME, "13:16"),
        )
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
            # Build a mapping of id -> name from existing and newly discovered routes
            id_to_name: dict[int, str] = {}
            for r in old_routes:
                try:
                    id_to_name[int(r["id"])] = r.get("name", f"Route {r['id']}")
                except Exception:
                    continue
            for r in new_routes:
                try:
                    id_to_name[int(r["id"])] = r.get("name", f"Route {r['id']}")
                except Exception:
                    continue

            # Append any new routes to the stored list (preserve existing ones)
            updated_routes = list(old_routes)
            for aid in add_ids:
                updated_routes.append({"id": aid, "name": id_to_name.get(aid, f"Route {aid}")})

            hass.data[DOMAIN][entry.entry_id]["routes"] = updated_routes
            try:
                await hass.config_entries.async_reload(entry.entry_id)
            except Exception as err:
                _LOGGER.exception("Failed to reload MyBusStop entry after adding new routes: %s", err)

    # Run discovery once a day. Keep the unsubscribe handle so we can cancel on unload.
    handle = async_track_time_interval(hass, _discover_and_reload_if_changed, timedelta(hours=24))
    hass.data[DOMAIN][entry.entry_id]["routes_update_unsub"] = handle

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
    return unload_ok
