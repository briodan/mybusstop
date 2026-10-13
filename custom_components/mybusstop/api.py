import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

from aiohttp import ClientSession, ClientError, ClientResponseError

from .const import BASE_URL, LOGIN_URL, INDEX_URL, CURRENT_URL, USER_AGENT

_LOGGER = logging.getLogger(__name__)


def parse_last_seen(value: Any) -> Optional[datetime]:
    """Parse a last_seen string like '10/13/2026 8:39:54 AM' into a datetime."""
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip(), "%m/%d/%Y %I:%M:%S %p")
    except ValueError:
        _LOGGER.debug("Could not parse last_seen value: %s", value)
        return None


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
            resp = await self._session.get(
                LOGIN_URL,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
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
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": LOGIN_URL,
            "Origin": BASE_URL,
        }

        try:
            resp = await self._session.post(LOGIN_URL, data=data, headers=headers)
            resp.raise_for_status()
            text = await resp.text()
        except ClientError as err:
            raise MyBusStopAuthError(f"Login POST failed: {err}") from err

        # A successful login redirects to Index.aspx. A failed one returns the
        # login form again (which still contains "MyBusStop" in its footer).
        final_url = str(resp.url)
        still_on_login = 'id="txtPassword"' in text
        on_index = "hiddenUser" in text or final_url.lower().startswith(INDEX_URL.lower())
        if still_on_login or not on_index:
            if "Just a moment" in text or "cf-chl" in text or "challenge-platform" in text:
                reason = "blocked by Cloudflare challenge"
            elif still_on_login:
                reason = "login form returned again (bad credentials or login rejected)"
            else:
                reason = "unexpected response page"
            _LOGGER.debug(
                "Login failed (%s); final URL %s; response sample: %s",
                reason,
                final_url,
                text[:1000],
            )
            raise MyBusStopAuthError(f"MyBusStop login failed: {reason}")

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
            try:
                resp = await self._session.get(INDEX_URL, headers={"User-Agent": USER_AGENT})
                resp.raise_for_status()
                html = await resp.text()
                _LOGGER.debug("Fetched Index.aspx page (length: %d bytes)", len(html))
            except ClientError as err:
                _LOGGER.error("Failed to fetch routes page: %s", err)
                return []
        else:
            _LOGGER.debug("Using saved login page HTML (length: %d bytes)", len(html))

        # Log a sample of the HTML to help debug
        _LOGGER.debug("HTML sample (first 1000 chars): %s", html[:1000])

        # Parse <option value="12345">Route Name</option>
        # Also try to find select/dropdown elements for debugging
        select_matches = re.findall(r'<select[^>]*>(.*?)</select>', html, re.IGNORECASE | re.DOTALL)
        _LOGGER.debug("Found %d <select> elements in HTML", len(select_matches))
        
        routes = []
        for m in re.finditer(r'<option[^>]*value="(\d+)"[^>]*>([^<]+)</option>', html, re.IGNORECASE):
            rid = m.group(1)
            name = m.group(2).strip()
            # Skip empty or "Select" placeholder options
            if name.lower() in ["", "select", "-- select --", "please select"]:
                continue
            try:
                routes.append({"id": int(rid), "name": name})
                _LOGGER.debug("Found route: id=%s, name=%s", rid, name)
            except ValueError:
                _LOGGER.warning("Could not parse route id '%s' as integer", rid)
                continue

        _LOGGER.info("Discovered %d route(s) from MyBusStop", len(routes))
        return routes

    async def async_get_current(self) -> Optional[Dict[str, Any]]:
        """Call getCurrentNEW and return parsed data, or None if route is not active."""
        if not self._logged_in:
            await self.async_login()

        payload = {"route_detail_id": self._route_id}

        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": INDEX_URL,
            "Origin": BASE_URL,
            "User-Agent": USER_AGENT,
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
            except ClientResponseError as err2:
                if err2.status == 401:
                    raise MyBusStopApiError(
                        "getCurrentNEW returned 401 Unauthorized right after a fresh login; "
                        "the session is being rejected by the server"
                    ) from err2
                raise MyBusStopApiError(f"Failed to call getCurrentNEW: {err2}") from err2
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
