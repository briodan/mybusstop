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

# Route IDs change every school year and names change daily, so the route list
# is refreshed regularly. Routes not listed for this many days are dropped.
ROUTE_PRUNE_DAYS = 14
ROUTE_REFRESH_MINUTES = 30  # refresh route list on update calls at most this often

BASE_URL = "https://www.mybusstop.ca"
LOGIN_URL = f"{BASE_URL}/login.aspx?ReturnUrl=%2fLogin%2fIndex.aspx"
INDEX_URL = f"{BASE_URL}/Login/Index.aspx"
CURRENT_URL = f"{BASE_URL}/Login/Index.aspx/getCurrentNEW"

# The site sits behind Cloudflare, which may challenge non-browser user agents.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)
