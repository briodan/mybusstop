from __future__ import annotations

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import logging

_LOGGER = logging.getLogger(__name__)

from .const import DOMAIN
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
            route_name = r.get("name") or f"Route {rid}"
            unique_id = f"{entry.entry_id}_bus_tracker_{rid}"

            if coord:
                entities.append(
                    MyBusStopBusTracker(
                        coordinator=coord,
                        unique_id=unique_id,
                        route_name=route_name,
                        route_id=rid,
                        entry_id=entry.entry_id,
                    )
                )
    else:
        # fallback
        coordinator: MyBusStopCoordinator = data.get("coordinator")
        route_id = entry.data.get('route_id')
        unique_id = f"{entry.entry_id}_bus_tracker"
        entities.append(
            MyBusStopBusTracker(
                coordinator=coordinator,
                unique_id=unique_id,
                route_name="Bus",
                route_id=route_id,
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
        coordinator: MyBusStopCoordinator,
        unique_id: str,
        route_name: str,
        route_id: int,
        entry_id: str,
    ) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = unique_id
        self._route_name = route_name
        self._route_id = route_id
        self._entry_id = entry_id
        self._attr_name = f"MyBusStop {route_name}"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def latitude(self) -> float | None:
        data = self.coordinator.data or {}
        return data.get("latitude")

    @property
    def longitude(self) -> float | None:
        data = self.coordinator.data or {}
        return data.get("longitude")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            "bus_number": data.get("bus_number"),
            "checkin_time": data.get("checkin_time"),
            "last_seen": data.get("last_seen"),
            "timezone_offset": data.get("timezone_offset"),
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

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        try:
            self.coordinator.async_remove_listener(self.async_write_ha_state)
        except AttributeError:
            _LOGGER.debug("Coordinator has no async_remove_listener, skipping removal")
