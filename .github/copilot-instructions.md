<!-- Copilot / AI instructions for contributors and coding agents -->
# MyBusStop — AI Coding Instructions

Purpose: give an AI or contributor the minimal, actionable knowledge to work productively on this Home Assistant custom integration.

**Big Picture:**
- **What this repo is:** a Home Assistant custom integration (`custom_components/mybusstop`) that polls the MyBusStop website to surface a bus sensor and GPS device tracker.
- **Key runtime pieces:** `MyBusStopApi` (HTTP client + parsing), `MyBusStopCoordinator` (DataUpdateCoordinator), platforms `sensor` and `device_tracker`, and `config_flow` for onboarding.

**Key files to read first:**
- `custom_components/mybusstop/manifest.json` — integration metadata (no external requirements).
- `custom_components/mybusstop/api.py` — HTTP login + `getCurrentNEW` JSON parsing. Critical: parsing expects `data["d"]` list with specific indices (see code comments).
- `custom_components/mybusstop/coordinator.py` — uses `DataUpdateCoordinator` with `DEFAULT_SCAN_INTERVAL` (seconds).
- `custom_components/mybusstop/sensor.py` and `device_tracker.py` — entity implementations that read `coordinator.data`.
- `custom_components/mybusstop/config_flow.py` — validates login during setup using the API client.

**Data flow & important details:**
- On setup (`async_setup_entry` in `__init__.py`): creates `MyBusStopApi`, logs in, creates a `MyBusStopCoordinator`, refreshes first data, and forwards to `PLATFORMS = ["sensor","device_tracker"]`.
- `MyBusStopApi.async_get_current()` returns a dict with keys: `bus_number`, `checkin_time`, `timezone_offset`, `latitude`, `longitude`, `last_seen`. The function:
  - Relies on a POST to `CURRENT_URL` and expects `data['d']` to be a list with known index positions.
  - Converts lat/long to floats.
  - On failure it will try a re-login once, then raise `MyBusStopApiError`.
- Entities access `coordinator.data` directly. The sensor uses `native_value` -> `bus_number`. The tracker exposes `latitude` and `longitude` and includes `route_id` in attributes.

**Patterns & conventions used here:**
- Async-first style matching Home Assistant core conventions (async def, `async_get_clientsession`).
- Use of `DataUpdateCoordinator` for polling and central data storage.
- Config entries store `username`, `password`, and `route_id` (see `config_flow.py`).
- Logging uses module `_LOGGER` and the manifest defines `loggers: ["custom_components.mybusstop"]`.
- Unique IDs: entities use `f"{entry.entry_id}_bus"` and `f"{entry.entry_id}_bus_tracker"`. Device identifiers use `(DOMAIN, str(route_id))`.

**Code smells / gotchas to watch for:**
- `api._route_id` is accessed from `device_tracker.extra_state_attributes` (protected attr). If you change how route_id is stored, update uses accordingly.
- Login success checks are "naive" (string presence). Modifying login flow needs careful validation to avoid false positives/negatives.
- HTML hidden-field extraction uses a simple regex — if the login page changes, update `_extract_hidden_value`.
- `async_get_current` expects a very specific JSON shape (`data['d']` list length >= 6). Any change to MyBusStop response will require updates here.

**How to run / test locally:**
- There are no unit tests in the repo. To test integration in HA developer environment:
  - Copy this `custom_components/mybusstop` into a Home Assistant config under `config/custom_components/mybusstop`.
  - Start Home Assistant (supervised/core dev) and use UI to add the integration via the Config Flow.
  - Monitor logs for `custom_components.mybusstop` messages — manifest exposes this logger.

**When modifying or adding features:**
- If adding platforms, add to `PLATFORMS` in `__init__.py` and create the platform module (e.g., `binary_sensor.py`) following the pattern in `sensor.py`.
- Keep API parsing and login logic centralized in `api.py`. Tests / mocks should simulate the `data['d']` payload and login HTML.
- Preserve async patterns; use `async_get_clientsession(hass)` to get `aiohttp` session.

**Merging with existing content:**
- No existing `.github/copilot-instructions.md` was found. If you want content merged from a different internal doc, paste it and request a merge.

If anything here is unclear or you'd like more examples (e.g., a sample mocked `data['d']` payload, or suggested pytest scaffolding), tell me which part to expand.
