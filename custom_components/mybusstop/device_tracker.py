from __future__ import annotations

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
        if api:
            entities.append(
                MyBusStopBusTracker(
                    hass=hass,
                    api=api,
                    unique_id=f"{entry.entry_id}_bus_tracker_{rid}",
                    route_name=route_name,
                    route_id=rid,
                    entry_id=entry.entry_id,
                )
            )

    if entities:
        async_add_entities(entities)


class MyBusStopBusTracker(TrackerEntity):
    """Device tracker for the bus from MyBusStop."""
    # Some Home Assistant versions expose SOURCE_TYPE_GPS as a constant;
    # others do not. Use the literal string to remain compatible.
    _attr_source_type = "gps"

    def __init__(
        self,
        hass: HomeAssistant,
        api: MyBusStopApi,
        unique_id: str,
        route_name: str,
        route_id: int,
        entry_id: str,
    ) -> None:
        self.hass = hass
        self._api = api
        self._attr_unique_id = unique_id
        self._route_name = route_name
        self._route_id = route_id
        self._entry_id = entry_id
        self._attr_name = f"MyBusStop {route_name}"
        self._data: dict | None = None

    @property
    def available(self) -> bool:
        return self._data is not None

    @property
    def latitude(self) -> float | None:
        if not self._data:
            return None
        return self._data.get("latitude")

    @property
    def longitude(self) -> float | None:
        if not self._data:
            return None
        return self._data.get("longitude")

    @property
    def extra_state_attributes(self) -> dict:
        if not self._data:
            return {}
        return {
            "bus_number": self._data.get("bus_number"),
            "checkin_time": self._data.get("checkin_time"),
            "last_seen": self._data.get("last_seen"),
            "timezone_offset": self._data.get("timezone_offset"),
            "route_id": self._route_id,
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
        route_id = event.data.get("route_id")
        # Update if it's for this route or for all routes
        if route_id is None or route_id == self._route_id:
            data_store = self.hass.data[DOMAIN][self._entry_id].get("data", {})
            self._data = data_store.get(self._route_id)
            self.async_write_ha_state()
