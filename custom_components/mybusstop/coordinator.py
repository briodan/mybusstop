from datetime import timedelta
import logging
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MyBusStopApi, MyBusStopApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MyBusStopCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Coordinator to fetch MyBusStop data on demand."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: MyBusStopApi,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_interval=None,  # Disable automatic polling
        )
        self.api = api

    async def _async_update_data(self) -> Dict[str, Any]:
        try:
            return await self.api.async_get_current()
        except MyBusStopApiError as err:
            raise UpdateFailed(str(err)) from err
