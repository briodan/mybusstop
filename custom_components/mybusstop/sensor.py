from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .api import MyBusStopApi


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    routes = data.get("routes", [])
    apis = data.get("apis", {})

    entities = []
    for r in routes:
        rid = int(r["id"])
        api = apis.get(rid)
        route_name = r.get("name") or f"Route {rid}"
        unique_id = f"{entry.entry_id}_bus_{rid}"
        if api:
            entities.append(
                MyBusStopBusSensor(
                    hass=hass,
                    api=api,
                    route_name=route_name,
                    route_id=rid,
                    unique_id=unique_id,
                    entry_id=entry.entry_id,
                )
            )

    if entities:
        async_add_entities(entities)


class MyBusStopBusSensor(SensorEntity):
    """Primary sensor representing the bus / route status."""
    _attr_icon = "mdi:bus"

    def __init__(
        self,
        hass: HomeAssistant,
        api: MyBusStopApi,
        route_name: str,
        route_id: int,
        unique_id: str,
        entry_id: str,
    ) -> None:
        self.hass = hass
        self._api = api
        self._route_name = route_name
        self._route_id = route_id
        self._attr_unique_id = unique_id
        self._entry_id = entry_id
        self._attr_name = f"MyBusStop {route_name}"
        self._data: Optional[Dict[str, Any]] = None

    @property
    def available(self) -> bool:
        return self._data is not None

    @property
    def native_value(self) -> Optional[str]:
        if not self._data:
            return None
        return self._data.get("bus_number")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        if not self._data:
            return {}
        return {
            "latitude": self._data.get("latitude"),
            "longitude": self._data.get("longitude"),
            "checkin_time": self._data.get("checkin_time"),
            "last_seen": self._data.get("last_seen"),
            "timezone_offset": self._data.get("timezone_offset"),
            "route_id": self._route_id,
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, "mybusstop_device")},
            name="MyBusStop",
            manufacturer="MyBusStop",
        )

    async def async_added_to_hass(self) -> None:
        \"\"\"Register event listener when entity is added.\"\"\"
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_update",
                self._handle_update_event,
            )
        )

    async def _handle_update_event(self, event) -> None:
        \"\"\"Handle update event from service.\"\"\"
        route_id = event.data.get("route_id")
        # Update if it's for this route or for all routes
        if route_id is None or route_id == self._route_id:
            data_store = self.hass.data[DOMAIN][self._entry_id].get("data", {})
            self._data = data_store.get(self._route_id)
            self.async_write_ha_state()
