from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


def _find_most_recent_route_data(all_data: Dict[int, Dict[str, Any]]) -> Optional[tuple[int, Dict[str, Any]]]:
    """Find the route with the most recent last_seen timestamp."""
    if not all_data:
        return None
    
    most_recent = None
    most_recent_route_id = None
    
    for route_id, data in all_data.items():
        last_seen = data.get("last_seen")
        if not last_seen:
            continue
        
        if most_recent is None or last_seen > most_recent:
            most_recent = last_seen
            most_recent_route_id = route_id
    
    if most_recent_route_id is not None:
        return most_recent_route_id, all_data[most_recent_route_id]
    
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    routes = data.get("routes", [])

    entities = [
        MyBusStopBusTracker(
            hass=hass,
            entry_id=entry.entry_id,
            routes=routes,
        ),
    ]

    async_add_entities(entities)


class MyBusStopBusTracker(TrackerEntity):
    """Device tracker for the active bus across all routes."""
    _attr_source_type = "gps"

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        routes: list,
    ) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._routes = routes
        self._attr_unique_id = f"{entry_id}_bus_tracker"
        self._attr_name = "MyBusStop Bus"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        all_data = self.hass.data[DOMAIN][self._entry_id].get("data", {})
        result = _find_most_recent_route_data(all_data)
        return result is not None and result[1].get("latitude") is not None

    @property
    def latitude(self) -> float | None:
        """Return latitude from most recent route."""
        all_data = self.hass.data[DOMAIN][self._entry_id].get("data", {})
        result = _find_most_recent_route_data(all_data)
        if result:
            _, data = result
            return data.get("latitude")
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude from most recent route."""
        all_data = self.hass.data[DOMAIN][self._entry_id].get("data", {})
        result = _find_most_recent_route_data(all_data)
        if result:
            _, data = result
            return data.get("longitude")
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return attributes including current route."""
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
            "bus_number": data.get("bus_number"),
            "checkin_time": data.get("checkin_time"),
            "last_seen": data.get("last_seen"),
            "timezone_offset": data.get("timezone_offset"),
        }

    @property
    def device_info(self):
        from homeassistant.helpers.entity import DeviceInfo
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
