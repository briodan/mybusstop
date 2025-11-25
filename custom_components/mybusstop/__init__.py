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

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MyBusStop from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    username: str = entry.data["username"]
    password: str = entry.data["password"]
    route_id: int = entry.data[CONF_ROUTE_ID]

    api = MyBusStopApi(session, username, password, route_id)

    # Test login at setup time
    try:
        await api.async_login()
    except MyBusStopAuthError as err:
        _LOGGER.error("Failed to log in to MyBusStop: %s", err)
        raise

    coordinator = MyBusStopCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a MyBusStop config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
