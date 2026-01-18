import logging
import re
from typing import Any, Dict, Optional

from aiohttp import ClientSession, ClientError

from .const import LOGIN_URL, CURRENT_URL

_LOGGER = logging.getLogger(__name__)


class MyBusStopAuthError(Exception):
    """Authentication / Login Error."""


class MyBusStopApiError(Exception):
    """Generic API error."""


class MyBusStopApi:
    """Simple client for MyBusStop WebForms API."""

    def __init__(
        self,
        session: ClientSession,
        username: str,
        password: str,
        route_id: Optional[int] = None,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._route_id = route_id
        self._logged_in = False

    async def _fetch_login_page(self) -> str:
        """Fetch the login page to get VIEWSTATE, etc."""
        try:
            resp = await self._session.get(LOGIN_URL)
            resp.raise_for_status()
            text = await resp.text()
            return text
        except ClientError as err:
            raise MyBusStopAuthError(f"Error fetching login page: {err}") from err

    @staticmethod
    def _extract_hidden_value(name: str, html: str) -> Optional[str]:
        """Extract a hidden input value from the HTML."""
        # Simple regex, good enough for this specific page structure.
        m = re.search(
            rf'id="{re.escape(name)}"\s+value="([^"]*)"', html, re.IGNORECASE
        )
        return m.group(1) if m else None

    async def async_login(self) -> None:
        """Log in to MyBusStop and establish a session."""
        _LOGGER.debug("MyBusStop: starting login sequence")
        html = await self._fetch_login_page()

        viewstate = self._extract_hidden_value("__VIEWSTATE", html)
        viewstate_gen = self._extract_hidden_value("__VIEWSTATEGENERATOR", html)
        event_validation = self._extract_hidden_value("__EVENTVALIDATION", html)

        if not all([viewstate, viewstate_gen, event_validation]):
            raise MyBusStopAuthError("Failed to extract VIEWSTATE / EVENTVALIDATION")

        data = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": viewstate_gen,
            "__EVENTVALIDATION": event_validation,
            "txtUserName": self._username,
            "txtPassword": self._password,
            "cmdLogin": "Log in",
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "HomeAssistant-MyBusStop/0.1",
        }

        try:
            resp = await self._session.post(LOGIN_URL, data=data, headers=headers)
            resp.raise_for_status()
            text = await resp.text()
        except ClientError as err:
            raise MyBusStopAuthError(f"Login POST failed: {err}") from err

        # Very naive success check: we expect to be redirected to Index.aspx
        if "hiddenUser" not in text and "MyBusStop" not in text:
            _LOGGER.debug("Login response did not look like logged-in page")
            raise MyBusStopAuthError("MyBusStop login appears to have failed")

        _LOGGER.info("MyBusStop login successful")
        self._logged_in = True
        # Save last logged-in page HTML for callers who want to parse routes
        self._last_login_page = text

    async def async_get_routes(self) -> list[dict]:
        """Return list of available routes from the logged-in page.

        Each route is a dict:{"id": <route_id>, "name": <route_name>}.
        If no routes are found, returns an empty list.
        """
        if not getattr(self, "_logged_in", False):
            await self.async_login()

        # Try to use saved login page HTML if available; otherwise fetch the page
        html = getattr(self, "_last_login_page", None)
        if html is None:
            # Fetch the index page which contains the route dropdown
            index_url = LOGIN_URL.replace("login.aspx?ReturnUrl=%2fLogin%2fIndex.aspx", "Login/Index.aspx")
            try:
                resp = await self._session.get(index_url)
                resp.raise_for_status()
                html = await resp.text()
            except ClientError as err:
                _LOGGER.debug("Failed to fetch routes page: %s", err)
                return []

        # Parse <option value="12345">Route Name</option>
        routes = []
        for m in re.finditer(r'<option[^>]*value="(\d+)"[^>]*>([^<]+)</option>', html, re.IGNORECASE):
            rid = m.group(1)
            name = m.group(2).strip()
            try:
                routes.append({"id": int(rid), "name": name})
            except ValueError:
                continue

        return routes

    async def async_get_current(self) -> Optional[Dict[str, Any]]:
        """Call getCurrentNEW and return parsed data, or None if route is not active."""
        if not self._logged_in:
            await self.async_login()

        payload = {"route_detail_id": self._route_id}

        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": LOGIN_URL.replace("login.aspx?ReturnUrl=%2fLogin%2fIndex.aspx", "Login/Index.aspx"),
            "Origin": "https://www.mybusstop.ca",
            "User-Agent": "HomeAssistant-MyBusStop/0.1",
        }

        try:
            resp = await self._session.post(CURRENT_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = await resp.json()
        except ClientError as err:
            _LOGGER.warning("Error calling getCurrentNEW: %s", err)
            # Try re-login once
            self._logged_in = False
            await self.async_login()
            try:
                resp = await self._session.post(CURRENT_URL, json=payload, headers=headers)
                resp.raise_for_status()
                data = await resp.json()
            except ClientError as err2:
                raise MyBusStopApiError(f"Failed to call getCurrentNEW: {err2}") from err2

        if "d" not in data or not isinstance(data["d"], list) or len(data["d"]) < 6:
            _LOGGER.debug("Unexpected getCurrentNEW response (route may not be active): %s", data)
            return None  # Route not active/no data available

        d = data["d"]
        def _to_float(val: Any) -> Optional[float]:
            try:
                if val is None:
                    return None
                s = str(val).strip()
                if s == "" or s.lower() == "null":
                    return None
                return float(s)
            except (ValueError, TypeError):
                return None
        # Based on the page JS OnSuccessCurrent:
        # response[0] = sUnit (bus number)
        # response[1] = checkin_time
        # response[2] = time_zone
        # response[3] = lat
        # response[4] = long
        # response[5] = time
        result = {
            "bus_number": d[0],
            "checkin_time": d[1],
            "timezone_offset": d[2],
            "latitude": _to_float(d[3]),
            "longitude": _to_float(d[4]),
            "last_seen": d[5],
        }
        _LOGGER.debug("Route %s: async_get_current returned: %s", self._route_id, result)
        return result
