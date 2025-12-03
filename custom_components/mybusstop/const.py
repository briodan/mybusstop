DOMAIN = "mybusstop"

CONF_ROUTE_ID = "route_id"
CONF_MORNING_PICKUP_TIME = "morning_pickup_time"
CONF_AFTERNOON_DROPOFF_TIME = "afternoon_dropoff_time"
CONF_FRIDAY_DROPOFF_TIME = "friday_dropoff_time"
CONF_DISCOVERY_TIME = "discovery_time"

DEFAULT_DISCOVERY_TIME = "02:00"  # 2:00 AM default

DEFAULT_SCAN_INTERVAL = 60  # seconds
POLLING_WINDOW_MINUTES = 15  # Start polling 15 minutes before and after scheduled times
ACTIVE_SCAN_INTERVAL = 60  # seconds, when actively polling around bus times
INACTIVE_SCAN_INTERVAL = 3600  # 1 hour, when not near bus times

BASE_URL = "https://www.mybusstop.ca"
LOGIN_URL = f"{BASE_URL}/login.aspx?ReturnUrl=%2fLogin%2fIndex.aspx"
CURRENT_URL = f"{BASE_URL}/Login/Index.aspx/getCurrentNEW"
