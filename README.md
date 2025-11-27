# MyBusStop Home Assistant Integration

A Home Assistant custom integration that connects to [MyBusStop](https://www.mybusstop.ca) to track your bus routes and display real-time location data.

## Features

- **Multi-Route Support**: Automatically discovers all available bus routes from your MyBusStop account
- **Dynamic Route Discovery**: Detects new routes (e.g., Friday-only routes) and adds them automatically
- **Real-Time Tracking**: Device tracker with GPS coordinates for current bus location
- **Bus Sensor**: Displays current bus number with additional metadata
- **Automatic Updates**: Polls bus location every 60 seconds (configurable)

## Installation via HACS

### Prerequisites

- Home Assistant with [HACS](https://hacs.xyz/) installed
- MyBusStop account credentials (username/email and password)
- Your MyBusStop route detail ID (the integration will prompt you during setup)

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
   - Click **Create Integration** (or the + button)
   - Search for "MyBusStop"
   - Enter your MyBusStop credentials and bus times:
     - **Username/Email**: Your MyBusStop login email
     - **Password**: Your MyBusStop password
     - **Morning Pickup Time**: When your bus is picked up in the morning (default: `08:19`)
     - **Afternoon Dropoff Time**: Afternoon bus dropoff time (default: `15:52`)
     - **Friday Dropoff Time**: Friday bus dropoff time (default: `13:16`)
   - Click **Create**
   - The integration will automatically discover all routes available in your account

4. **Verify Setup**:
   - Home Assistant will discover all available routes from your account
   - You should see sensors and device trackers created for each route
   - Check **Developer Tools** → **States** to view entities like `sensor.mybusstop_bus_*` and `device_tracker.mybusstop_bus_tracker_*`

## What You Get

### Sensors
- `sensor.mybusstop_bus_*` — Displays the current bus number for each route
  - **Attributes**: latitude, longitude, checkin_time, last_seen, timezone_offset, route_id

### Device Trackers
- `device_tracker.mybusstop_bus_tracker_*` — Tracks the real-time GPS location of the bus
  - **Attributes**: bus_number, checkin_time, last_seen, timezone_offset, route_id

## Configuration

### Bus Times

When you set up the integration, you can configure three bus times to optimize polling:

- **Morning Pickup Time**: When your morning bus is picked up (default: `08:19`)
- **Afternoon Dropoff Time**: Afternoon bus schedule (default: `15:52`)
- **Friday Dropoff Time**: Different schedule for Fridays (default: `13:16`)

The integration uses these times to intelligently poll:
- **Active polling** (every 60 seconds) within a 15-minute window around each scheduled time
- **Inactive polling** (every 1 hour) outside those windows to save bandwidth

### Polling Intervals

By default:
- `ACTIVE_SCAN_INTERVAL = 60` seconds (when actively tracking around bus times)
- `INACTIVE_SCAN_INTERVAL = 3600` seconds (1 hour when not near bus times)
- `POLLING_WINDOW_MINUTES = 15` minutes before/after scheduled times

### Automatic Route Discovery

The integration automatically discovers all available routes from your MyBusStop account on setup. A daily check runs to detect any new routes (e.g., Friday-only routes) and adds them to your setup.

## Troubleshooting

### "Failed to set up" Error During Initial Setup

This usually means one of the following:

- **Invalid credentials**: Double-check your MyBusStop username/password
- **Route ID not found**: Ensure the Route Detail ID exists in your account
- **Network issue**: Check your internet connection and MyBusStop website availability

### No Entities Created

- Check Home Assistant logs for errors: **Settings** → **System** → **Logs** (filter for `custom_components.mybusstop`)
- Verify your account has at least one active route
- Ensure the integration is fully loaded (check **Settings** → **Devices & Services** → **Integrations**)

### Empty Coordinates

If latitude/longitude are empty (`None`), the bus may not have checked in yet or the tracker may be offline. The device tracker will be unavailable until coordinates are available.

## How It Works

1. **Login**: Uses your MyBusStop credentials to authenticate and fetch available routes
2. **Route Discovery**: Automatically parses the login page to extract all available bus routes
3. **Smart Polling**: Creates a separate coordinator for each route with intelligent polling:
   - Active polling every 60 seconds within 15 minutes of scheduled bus times
   - Inactive polling every 1 hour outside those windows
4. **Daily Refresh**: Checks for newly available routes (e.g., Friday-only routes) and adds them automatically
5. **Entity Creation**: Generates sensors and device trackers for each discovered route

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