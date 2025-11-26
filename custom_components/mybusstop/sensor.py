from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_ROUTE_ID
from .coordinator import MyBusStopCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    routes = data.get("routes", [])
    coordinators = data.get("coordinators", {})

    entities = []
    if routes:
        for r in routes:
            rid = int(r["id"])
            coord = coordinators.get(rid)
            name = r.get("name") or f"MyBusStop Route {rid}"
            unique_id = f"{entry.entry_id}_bus_{rid}"
            if coord:
                entities.append(
                    MyBusStopBusSensor(
                        coordinator=coord,
                        name=name,
                        route_id=rid,
                        unique_id=unique_id,
                    )
                )
    else:
        # Fallback to single configured route
        coordinator: MyBusStopCoordinator = data.get("coordinator")
        name = entry.title or "MyBusStop Bus"
        route_id = entry.data[CONF_ROUTE_ID]
        entities.append(
            MyBusStopBusSensor(
                coordinator=coordinator,
                name=name,
                route_id=route_id,
                unique_id=f"{entry.entry_id}_bus",
            )
        )

    if entities:
        async_add_entities(entities)


class MyBusStopBusSensor(SensorEntity):
    """Primary sensor representing the bus / route status."""

    _attr_icon = "mdi:bus"

    def __init__(
        self,
        coordinator: MyBusStopCoordinator,
        name: str,
        route_id: int,
        unique_id: str,
    ) -> None:
        self._coordinator = coordinator
        self._attr_name = name
        self._route_id = route_id
        self._attr_unique_id = unique_id

    @property
    def available(self) -> bool:
        return self._coordinator.last_update_success

    @property
    def native_value(self) -> Optional[str]:
        data = self._coordinator.data
        if not data:
            return None
        return data.get("bus_number")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        data = self._coordinator.data or {}
        return {
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "checkin_time": data.get("checkin_time"),
            "last_seen": data.get("last_seen"),
            "timezone_offset": data.get("timezone_offset"),
            "route_id": self._route_id,
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._route_id))},
            name=f"MyBusStop Route {self._route_id}",
            manufacturer="MyBusStop",
        )

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        self._coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.async_remove_listener(self.async_write_ha_state)
