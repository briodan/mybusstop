from __future__ import annotations

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MyBusStopCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: MyBusStopCoordinator = data["coordinator"]

    entity = MyBusStopBusTracker(
        coordinator=coordinator,
        unique_id=f"{entry.entry_id}_bus_tracker",
        name=f"MyBusStop Bus Tracker {entry.data['route_id']}",
    )
    async_add_entities([entity])


class MyBusStopBusTracker(TrackerEntity):
    """Device tracker for the bus from MyBusStop."""

    # Some Home Assistant versions expose SOURCE_TYPE_GPS as a constant;
    # others do not. Use the literal string to remain compatible.
    _attr_source_type = "gps"

    def __init__(self, coordinator: MyBusStopCoordinator, unique_id: str, name: str) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = unique_id
        self._attr_name = name

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
            "route_id": self.coordinator.api._route_id,
        }

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        self.coordinator.async_remove_listener(self.async_write_ha_state)
