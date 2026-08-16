import requests
from config import OTP_URL, TODAY_DATE

# Persistent session to reuse TCP connections across calls
session = requests.Session()
session.headers.update({"User-Agent": "OTP-Transit-Script/1.0 (Contact: local-dev)"})


def geocode_address(address: str) -> tuple[float | None, float | None]:
    """Geocodes an address via OpenStreetMap Nominatim API with structured logging."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}

    try:
        response = session.get(url, params=params, timeout=10)

        if response.status_code != 200:
            print(f"  ❌ Geocoding Error: API returned status {response.status_code} for '{address}'")
            return None, None

        res = response.json()
        if res:
            return float(res[0]["lat"]), float(res[0]["lon"])

        print(f"  ⚠️ Geocoding Fail: No results found for '{address}' (Likely bad address format)")

    except Exception as e:
        print(f"  ❌ Geocoding Exception for '{address}': {type(e).__name__} - {e}")

    return None, None


def get_transit_info(
    from_lat: float, from_lon: float, to_lat: float, to_lon: float
) -> tuple:
    """Queries OpenTripPlanner GraphQL API for route alternatives and bus frequencies."""

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
          startTime
          endTime
          legs {
            mode
            startTime
            endTime
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

    # Format: (min_trans_dur, min_trans_count, min_trans_routes, min_trans_freq,
    #          short_dur, short_count, short_routes, short_freq)
    empty_res = ("N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A")

    try:
        res = session.post(
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
                "No Route", "N/A", "N/A", "N/A",
                "No Route", "N/A", "N/A", "N/A"
            )

        itineraries = plan["itineraries"]
        parsed_itineraries = []

        # Collect departure start times per primary transit route across all returned itineraries
        # to estimate headway/frequency if multiple trips use the same route line
        route_departures: dict[str, list[int]] = {}

        for itin in itineraries:
            for leg in itin.get("legs", []):
                if leg["mode"] not in ["WALK", "BICYCLE", "CAR"]:
                    route_info = leg.get("route") or {}
                    r_name = (
                        route_info.get("shortName")
                        or route_info.get("longName")
                        or leg["mode"]
                    )
                    start_ts = leg.get("startTime", 0) // 1000  # ms to seconds
                    route_departures.setdefault(str(r_name), []).append(start_ts)

        for itin in itineraries:
            duration_sec = itin["duration"]
            transit_routes = []
            transit_headways = []

            for leg in itin.get("legs", []):
                if leg["mode"] not in ["WALK", "BICYCLE", "CAR"]:
                    route_info = leg.get("route") or {}
                    name = (
                        route_info.get("shortName")
                        or route_info.get("longName")
                        or leg["mode"]
                    )
                    transit_routes.append(str(name))

                    # Calculate average headway (frequency in mins) if multiple departures exist
                    deps = sorted(set(route_departures.get(str(name), [])))
                    if len(deps) > 1:
                        gaps = [deps[i] - deps[i - 1] for i in range(1, len(deps))]
                        avg_gap_min = round((sum(gaps) / len(gaps)) / 60)
                        transit_headways.append(f"~{avg_gap_min}m")
                    else:
                        transit_headways.append("Single Trip")

            transfers = max(0, len(transit_routes) - 1)

            if not transit_routes:
                routes_str = "Walk Only"
                freq_str = "N/A"
            elif len(transit_routes) == 1:
                routes_str = transit_routes[0]
                freq_str = transit_headways[0]
            else:
                routes_str = f"[{', '.join(transit_routes)}]"
                freq_str = f"[{', '.join(transit_headways)}]"

            hours = duration_sec // 3600
            minutes = (duration_sec % 3600) // 60
            duration_display = f"{hours}.{minutes:02d}"

            parsed_itineraries.append(
                {
                    "duration_sec": duration_sec,
                    "duration": duration_display,
                    "transfers": transfers,
                    "routes": routes_str,
                    "frequency": freq_str,
                }
            )

        min_transfer_route = sorted(
            parsed_itineraries,
            key=lambda x: (x["transfers"], x["duration_sec"]),
        )[0]

        shortest_time_route = sorted(
            parsed_itineraries,
            key=lambda x: (x["duration_sec"], x["transfers"]),
        )[0]

        return (
            min_transfer_route["duration"],
            min_transfer_route["transfers"],
            min_transfer_route["routes"],
            min_transfer_route["frequency"],
            shortest_time_route["duration"],
            shortest_time_route["transfers"],
            shortest_time_route["routes"],
            shortest_time_route["frequency"],
        )

    except Exception as e:
        print(f"  [OTP Request Failed]: {e}")
        return empty_res