from datetime import timedelta, datetime, time
import logging
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MyBusStopApi, MyBusStopApiError
from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    POLLING_WINDOW_MINUTES,
    ACTIVE_SCAN_INTERVAL,
    INACTIVE_SCAN_INTERVAL,
    CONF_MORNING_PICKUP_TIME,
    CONF_AFTERNOON_DROPOFF_TIME,
    CONF_FRIDAY_DROPOFF_TIME,
)

_LOGGER = logging.getLogger(__name__)


class MyBusStopCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Coordinator to fetch MyBusStop data with smart polling intervals."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: MyBusStopApi,
        morning_pickup_time: str = "08:19",
        afternoon_dropoff_time: str = "15:52",
        friday_dropoff_time: str = "13:16",
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        
        # Parse schedule times (HH:MM format)
        self._morning_pickup = self._parse_time(morning_pickup_time)
        self._afternoon_dropoff = self._parse_time(afternoon_dropoff_time)
        self._friday_dropoff = self._parse_time(friday_dropoff_time)
        self._polling_window = timedelta(minutes=POLLING_WINDOW_MINUTES)

    @staticmethod
    def _parse_time(time_str: str) -> time:
        """Parse time string in HH:MM format."""
        try:
            h, m = map(int, time_str.split(":"))
            return time(h, m)
        except (ValueError, AttributeError):
            _LOGGER.warning("Invalid time format '%s', defaulting to 08:19", time_str)
            return time(8, 19)

    def _should_poll_now(self) -> bool:
        """Check if current time falls within polling windows."""
        now = datetime.now()
        current_time = now.time()
        is_friday = now.weekday() == 4  # Friday is 4
        
        # Define polling windows
        windows = []
        
        # Morning pickup window (every day)
        morning_start = self._time_minus(self._morning_pickup, POLLING_WINDOW_MINUTES)
        morning_end = self._time_plus(self._morning_pickup, POLLING_WINDOW_MINUTES)
        windows.append((morning_start, morning_end))
        
        # Afternoon dropoff (Monday-Thursday)
        if not is_friday:
            afternoon_start = self._time_minus(self._afternoon_dropoff, POLLING_WINDOW_MINUTES)
            afternoon_end = self._time_plus(self._afternoon_dropoff, POLLING_WINDOW_MINUTES)
            windows.append((afternoon_start, afternoon_end))
        
        # Friday dropoff (Friday only)
        if is_friday:
            friday_start = self._time_minus(self._friday_dropoff, POLLING_WINDOW_MINUTES)
            friday_end = self._time_plus(self._friday_dropoff, POLLING_WINDOW_MINUTES)
            windows.append((friday_start, friday_end))
        
        # Check if current time falls in any window
        for start, end in windows:
            if start <= current_time <= end:
                return True
        
        return False

    @staticmethod
    def _time_minus(t: time, minutes: int) -> time:
        """Subtract minutes from a time object."""
        dt = datetime.combine(datetime.today(), t) - timedelta(minutes=minutes)
        return dt.time()

    @staticmethod
    def _time_plus(t: time, minutes: int) -> time:
        """Add minutes to a time object."""
        dt = datetime.combine(datetime.today(), t) + timedelta(minutes=minutes)
        return dt.time()

    async def _async_update_data(self) -> Dict[str, Any]:
        try:
            return await self.api.async_get_current()
        except MyBusStopApiError as err:
            raise UpdateFailed(str(err)) from err

    async def async_request_refresh(self) -> None:
        """Override refresh to use smart polling intervals."""
        # Determine the next update interval
        if self._should_poll_now():
            self.update_interval = timedelta(seconds=ACTIVE_SCAN_INTERVAL)
            _LOGGER.debug("Active polling window - updating every %s seconds", ACTIVE_SCAN_INTERVAL)
        else:
            self.update_interval = timedelta(seconds=INACTIVE_SCAN_INTERVAL)
            _LOGGER.debug("Inactive polling window - updating every %s seconds", INACTIVE_SCAN_INTERVAL)
        
        await super().async_request_refresh()
