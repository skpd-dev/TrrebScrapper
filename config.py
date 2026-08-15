from datetime import datetime
from urllib.parse import urlencode

# Base settings
BASE_URL = "https://onlistings.trreb.ca"
BASE_SEARCH_URL = f"{BASE_URL}/listings"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Search parameters
# Add $top and $skip to your default parameters
SEARCH_PARAMS = {
    "$loc": "Toronto",
    "$zoom": 10,
    "$latitude": 43.91695703891578,
    "$longitude": -79.06320945935686,
    "$orderby": "address",
    "$gid": "treb",
    "$top": 100,  # Fetch up to 100 results per request
    "$skip": 0,  # Start at offset 0
    "latitude": [">=43.509984771114674", "<=44.3211647695919"],
    "longitude": [">=-80.16184227185687", "<=-77.96457664685687"],
    "class": ["FREE", "CONDO"],
    "availability": "A",
    "saleOrRent": "RENT",
    "area": "Toronto",
    "price": [">=1750", "<=2500"],
    "bedrooms": [2, 3, 4],
    "bathrooms": [2, 3],
    "laundryAccess": "Ensuite",
}


def build_search_url(base_url: str, params: dict) -> str:
    """Constructs a URL with query parameters, expanding lists properly."""
    query_string = urlencode(params, doseq=True)
    return f"{base_url}?{query_string}"


SEARCH_URL = build_search_url(BASE_SEARCH_URL, SEARCH_PARAMS)

# Transit & Storage settings
DEST_LAT = 43.650268690498
DEST_LON = -79.376506311529
OTP_URL = "http://localhost:8080/otp/routers/default/index/graphql"
TODAY_DATE = datetime.now().strftime("%Y-%m-%d")
CSV_FILENAME = "trreb_full_listings_with_transit.csv"