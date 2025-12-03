# MyBusStop Home Assistant Integration

A Home Assistant custom integration that connects to [MyBusStop](https://www.mybusstop.ca) to track your bus and display real-time location data across all your routes.

## Features

- **Automatic Route Discovery**: Automatically discovers all available bus routes from your MyBusStop account
- **Single Bus View**: One unified bus sensor and tracker that intelligently shows the active route
- **Route Status Sensor**: Overview sensor showing all routes and their current status
- **On-Demand Updates**: Manual polling via service call - you control when to fetch bus location
- **Daily Route Discovery**: Configurable scheduled check for new routes (e.g., Friday-only routes)
- **Multi-Route Support**: Polls all routes but displays the most recently active one

## Installation via HACS

### Prerequisites

- Home Assistant with [HACS](https://hacs.xyz/) installed
- MyBusStop account credentials (username/email and password)

### Steps

1. **Add Custom Repository to HACS**:
   - Open Home Assistant and go to **Settings** → **Devices & Services** → **HACS**
   - Click the three-dot menu (⋮) in the top right and select **Custom repositories**
   - Paste the repository URL: `https://github.com/briodan/mybusstop`
   - Select **Category**: `Integration`
   - Click **Create**

2. **Install the Integration**:
   - In HACS, search for "MyBusStop"
   - Click on the integration and select **Install**
   - Restart Home Assistant

3. **Add the Integration to Home Assistant**:
   - Go to **Settings** → **Devices & Services** → **Integrations**
   - Click **Add Integration** (or the + button)
   - Search for "MyBusStop"
   - Enter your MyBusStop credentials:
     - **Username/Email**: Your MyBusStop login email
     - **Password**: Your MyBusStop password
   - Click **Submit**
   - The integration will automatically discover all routes available in your account

4. **Verify Setup**:
   - Home Assistant will discover all available routes from your account
   - You should see the following entities:
     - `sensor.mybusstop_bus` - Current bus information
     - `sensor.mybusstop_routes` - All routes status
     - `device_tracker.mybusstop_bus` - GPS location tracker
   - Check **Developer Tools** → **States** to view these entities

## What You Get

### Sensors
- **`sensor.mybusstop_bus`** — Displays the current bus number from the most recently active route
  - **State**: Bus number (e.g., "Bus 42")
  - **Attributes**: 
    - `current_route_id` - The route ID currently being displayed
    - `current_route_name` - Name of the current route
    - `latitude` - GPS latitude
    - `longitude` - GPS longitude
    - `checkin_time` - Last check-in time
    - `last_seen` - Last seen timestamp
    - `timezone_offset` - Timezone offset

- **`sensor.mybusstop_routes`** — Overview of all discovered routes
  - **State**: Count of routes (e.g., "2 routes")
  - **Attributes**:
    - `routes` - Dictionary containing all routes with their status, name, last_seen, and bus_number

### Device Trackers
- **`device_tracker.mybusstop_bus`** — Tracks the real-time GPS location of the active bus
  - **Location**: GPS coordinates from the most recent route
  - **Attributes**: 
    - `current_route_id` - The route ID currently being tracked
    - `current_route_name` - Name of the current route
    - `bus_number` - Bus identifier
    - `checkin_time` - Last check-in time
    - `last_seen` - Last seen timestamp
    - `timezone_offset` - Timezone offset

## Services

### `mybusstop.update_bus_location`

Manually poll the MyBusStop API to update bus location and status. Since automatic polling is disabled, use this service to fetch fresh data.

**Parameters:**
- `route_id` (optional): Specific route ID to update. If not provided, all routes will be updated.

**Examples:**

```yaml
# Update all routes
service: mybusstop.update_bus_location

# Update specific route
service: mybusstop.update_bus_location
data:
  route_id: "103427"
```

**Automation Example:**
```yaml
automation:
  - alias: "Update bus location before pickup"
    trigger:
      - platform: time
        at: "08:00:00"
    action:
      - service: mybusstop.update_bus_location
```

## Configuration

### Route Discovery Time

After initial setup, you can configure when the integration checks for new routes:

1. Go to **Settings** → **Devices & Services** → **Integrations**
2. Find **MyBusStop** and click **Configure**
3. Set **Daily route discovery time** (HH:MM format, 24-hour)
   - Default: `02:00` (2:00 AM)

The integration will check for new routes at this time every day and automatically add any newly discovered routes (e.g., Friday-only routes).

## How It Works

1. **Login**: Uses your MyBusStop credentials to authenticate
2. **Route Discovery**: Automatically parses the account to extract all available bus routes
3. **On-Demand Polling**: No automatic polling - you control updates via service calls
4. **Intelligent Aggregation**: When multiple routes exist:
   - All routes are polled when the service is called
   - The sensor and tracker show data from the route with the most recent `last_seen` timestamp
   - This ensures you always see the currently active bus, even if it switches routes
5. **Daily Route Check**: Runs once daily at your configured time to discover new routes

## Troubleshooting

### "Failed to set up" Error During Initial Setup

This usually means one of the following:

- **Invalid credentials**: Double-check your MyBusStop username/password
- **No routes found**: Ensure your account has at least one active route
- **Network issue**: Check your internet connection and MyBusStop website availability

### No Entities Created

- Check Home Assistant logs for errors: **Settings** → **System** → **Logs** (filter for `custom_components.mybusstop`)
- Verify your account has at least one active route
- Ensure the integration is fully loaded (check **Settings** → **Devices & Services** → **Integrations**)

### Empty Attributes or "Unknown" State

The entities start with no data until the first service call is made:
- Call `mybusstop.update_bus_location` service manually
- Or set up an automation to call it periodically
- The integration fetches initial data on setup, but may need a manual refresh

### Empty Coordinates

If latitude/longitude are empty (`None`), the bus may not have checked in yet or the tracker may be offline. The device tracker will be unavailable until valid coordinates are received.

## Development

If you'd like to contribute or modify this integration:

1. Clone the repository
2. Copy `custom_components/mybusstop` to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant to load the integration
4. Make your changes and test in a development Home Assistant instance

## License

This integration is provided as-is for personal use with MyBusStop. Use at your own risk.

## Support

For issues, feature requests, or bug reports, please visit the [GitHub Issues](https://github.com/briodan/mybusstop/issues) page.