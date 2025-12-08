from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)


def _find_most_recent_route_data(all_data: Dict[int, Dict[str, Any]]) -> Optional[tuple[int, Dict[str, Any]]]:
    """Find the route with the most recent last_seen timestamp."""
    if not all_data:
        _LOGGER.debug("_find_most_recent_route_data: all_data is empty")
        return None
    
    _LOGGER.debug("_find_most_recent_route_data: checking %d routes: %s", len(all_data), list(all_data.keys()))
    
    most_recent = None
    most_recent_route_id = None
    
    for route_id, data in all_data.items():
        last_seen = data.get("last_seen")
        _LOGGER.debug("Route %s: last_seen=%s, data keys=%s", route_id, last_seen, list(data.keys()))
        if not last_seen:
            continue
        
        if most_recent is None or last_seen > most_recent:
            most_recent = last_seen
            most_recent_route_id = route_id
    
    if most_recent_route_id is not None:
        _LOGGER.debug("Selected route %s with last_seen=%s", most_recent_route_id, most_recent)
        return most_recent_route_id, all_data[most_recent_route_id]
    
    _LOGGER.warning("No route with valid last_seen found. Routes data: %s", all_data)
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    routes = data.get("routes", [])

    entities = [
        MyBusStopBusSensor(
            hass=hass,
            entry_id=entry.entry_id,
            routes=routes,
        ),
        MyBusStopRoutesSensor(
            hass=hass,
            entry_id=entry.entry_id,
            routes=routes,
        ),
    ]

    async_add_entities(entities)


class MyBusStopBusSensor(SensorEntity):
    """Aggregated sensor representing the active bus across all routes."""
    _attr_icon = "mdi:bus"

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        routes: list,
    ) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._routes = routes
        self._attr_unique_id = f"{entry_id}_bus"
        self._attr_name = "MyBusStop Bus"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        all_data = self.hass.data[DOMAIN][self._entry_id].get("data", {})
        result = _find_most_recent_route_data(all_data) is not None
        if not result:
            _LOGGER.debug("%s: Entity unavailable, data: %s", self._attr_unique_id, all_data)
        return result

    @property
    def native_value(self) -> Optional[str]:
        """Return bus number from most recent route."""
        all_data = self.hass.data[DOMAIN][self._entry_id].get("data", {})
        result = _find_most_recent_route_data(all_data)
        if result:
            _, data = result
            return data.get("bus_number")
        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return attributes including current route and location."""
        all_data = self.hass.data[DOMAIN][self._entry_id].get("data", {})
        result = _find_most_recent_route_data(all_data)
        
        if not result:
            return {}
        
        route_id, data = result
        
        # Find route name
        route_name = None
        for r in self._routes:
            if int(r["id"]) == route_id:
                route_name = r.get("name", f"Route {route_id}")
                break
        
        return {
            "current_route_id": route_id,
            "current_route_name": route_name or f"Route {route_id}",
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "checkin_time": data.get("checkin_time"),
            "last_seen": data.get("last_seen"),
            "timezone_offset": data.get("timezone_offset"),
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, "mybusstop_device")},
            name="MyBusStop",
            manufacturer="MyBusStop",
        )

    async def async_added_to_hass(self) -> None:
        """Register event listener when entity is added."""
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_update",
                self._handle_update_event,
            )
        )

    async def _handle_update_event(self, event) -> None:
        """Handle update event from service."""
        self.async_write_ha_state()


class MyBusStopRoutesSensor(SensorEntity):
    """Sensor showing all routes and their status."""
    _attr_icon = "mdi:routes"

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        routes: list,
    ) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._routes = routes
        self._attr_unique_id = f"{entry_id}_routes"
        self._attr_name = "MyBusStop Routes"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return len(self._routes) > 0

    @property
    def native_value(self) -> str:
        """Return count of routes."""
        count = len(self._routes)
        return f"{count} route{'s' if count != 1 else ''}"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return detailed status of all routes."""
        all_data = self.hass.data[DOMAIN][self._entry_id].get("data", {})
        routes_status = {}
        
        for route in self._routes:
            route_id = int(route["id"])
            route_name = route.get("name", f"Route {route_id}")
            route_data = all_data.get(route_id, {})
            
            # Determine if route is active (has recent data)
            last_seen = route_data.get("last_seen")
            status = "unknown"
            
            if last_seen:
                # Parse last_seen if it's a string, assume it's relatively recent for now
                # You may need to adjust this logic based on the actual format
                status = "active"
            else:
                status = "inactive"
            
            routes_status[str(route_id)] = {
                "name": route_name,
                "status": status,
                "last_seen": last_seen,
                "bus_number": route_data.get("bus_number"),
            }
        
        return {"routes": routes_status}

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, "mybusstop_device")},
            name="MyBusStop",
            manufacturer="MyBusStop",
        )

    async def async_added_to_hass(self) -> None:
        """Register event listener when entity is added."""
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_update",
                self._handle_update_event,
            )
        )

    async def _handle_update_event(self, event) -> None:
        """Handle update event from service."""
        self.async_write_ha_state()
