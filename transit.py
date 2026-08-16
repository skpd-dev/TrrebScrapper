import requests
from config import OTP_URL, TODAY_DATE


def geocode_address(address: str) -> tuple[float | None, float | None]:
    """Geocodes an address via OpenStreetMap Nominatim API."""
    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "OTP-Transit-Script/1.0"}
    params = {"q": address, "format": "json", "limit": 1}
    try:
        response = requests.get(url, params=params, headers=headers)
        res = response.json()
        if res:
            return float(res[0]["lat"]), float(res[0]["lon"])
    except Exception as e:
        print(f"  ❌ Geocoding error for {address}: {e}")
    return None, None

def get_transit_info(
    from_lat: float, from_lon: float, to_lat: float, to_lon: float
) -> tuple:
    """Queries OpenTripPlanner GraphQL API for route alternatives."""

    query = """
    query TripQuery($fromLat: Float!, $fromLon: Float!, $toLat: Float!, $toLon: Float!, $date: String!, $time: String!) {
      plan(
        from: {lat: $fromLat, lon: $fromLon}
        to: {lat: $toLat, lon: $toLon}
        date: $date
        time: $time
        transportModes: [{mode: TRANSIT}, {mode: WALK}]
        numItineraries: 10
      ) {
        itineraries {
          duration
          legs {
            mode
            route {
              shortName
              longName
            }
          }
        }
      }
    }
    """

    variables = {
        "fromLat": from_lat,
        "fromLon": from_lon,
        "toLat": to_lat,
        "toLon": to_lon,
        "date": TODAY_DATE,
        "time": "08:30:00",
    }

    empty_res = ("N/A", "N/A", "N/A", "N/A", "N/A", "N/A")

    try:
        res = requests.post(
            OTP_URL,
            json={"query": query, "variables": variables},
            timeout=10,
        )

        res_data = res.json()

        if "errors" in res_data:
            print(f"  [OTP GraphQL Error]: {res_data['errors']}")
            return empty_res

        plan = res_data.get("data", {}).get("plan")

        if not plan or not plan.get("itineraries"):
            return (
                "No Route",
                "N/A",
                "N/A",
                "No Route",
                "N/A",
                "N/A",
            )

        parsed_itineraries = []

        for itin in plan["itineraries"]:
            # OTP returns duration in seconds.
            duration_sec = itin["duration"]

            transit_routes = []

            for leg in itin.get("legs", []):
                if leg["mode"] not in ["WALK", "BICYCLE", "CAR"]:
                    route_info = leg.get("route", {}) or {}

                    name = (
                        route_info.get("shortName")
                        or route_info.get("longName")
                        or leg["mode"]
                    )

                    transit_routes.append(str(name))

            # Number of transfers = number of transit routes - 1
            transfers = max(0, len(transit_routes) - 1)

            if not transit_routes:
                routes_str = "Walk Only"

            elif len(transit_routes) == 1:
                routes_str = transit_routes[0]

            else:
                routes_str = f"[{', '.join(transit_routes)}]"

            # Convert seconds into hours + minutes.
            #
            # Examples:
            # 45 minutes    -> 0.45
            # 1h 10m        -> 1.10
            # 1h 50m        -> 1.50
            # 2h 05m        -> 2.05
            #
            # Keep the original seconds separately for accurate sorting.
            hours = duration_sec // 3600
            minutes = (duration_sec % 3600) // 60

            duration_display = f"{hours}.{minutes:02d}"

            parsed_itineraries.append(
                {
                    "duration_sec": duration_sec,
                    "duration": duration_display,
                    "transfers": transfers,
                    "routes": routes_str,
                }
            )

        # Route with the fewest transfers.
        # If two routes have the same number of transfers,
        # choose the shorter one.
        min_transfer_route = sorted(
            parsed_itineraries,
            key=lambda x: (
                x["transfers"],
                x["duration_sec"],
            ),
        )[0]

        # Route with the shortest total travel time.
        # If two routes have the same duration,
        # choose the one with fewer transfers.
        shortest_time_route = sorted(
            parsed_itineraries,
            key=lambda x: (
                x["duration_sec"],
                x["transfers"],
            ),
        )[0]

        return (
            min_transfer_route["duration"],
            min_transfer_route["transfers"],
            min_transfer_route["routes"],
            shortest_time_route["duration"],
            shortest_time_route["transfers"],
            shortest_time_route["routes"],
        )

    except Exception as e:
        print(f"  [OTP Request Failed]: {e}")
        return empty_res