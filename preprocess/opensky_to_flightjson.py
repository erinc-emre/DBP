#!/usr/bin/env python3
"""Fetch a real flight trajectory from the OpenSky Network REST API and emit a
`flight.json` conforming to FLIGHT_SCHEMA.md (v1).

It resolves an
aircraft (by ICAO callsign + departure airport, or directly by icao24 hex),
pulls its trajectory via the experimental ``/tracks/all`` endpoint, and maps
each waypoint into the shared schema. All output is in SI units (meters,
m/s, Unix seconds).

Important REST-track limitations (see opensky_api.Waypoint):
  * waypoints carry NO speed/velocity field  -> speed_mps is DERIVED via
    haversine over consecutive waypoints.
  * waypoints carry NO geo_altitude          -> alt_m falls back to
    baro_altitude (0.0 when null / on_ground).
  * the tracks endpoint only serves the last 30 days of data.

Auth uses OAuth2 client-credentials (a ``credentials.json`` with keys
``clientId`` / ``clientSecret``). With no credentials, anonymous access is
used (reduced rate limits).

Usage examples
--------------
  # Resolve by callsign + departure airport, fill origin/destination:
  python3 opensky_to_flightjson.py \
      --callsign DLH401 --date 2024-03-21 \
      --dep-icao KJFK --arr-icao EDDF \
      --flight-number LH401 \
      --credentials credentials.json \
      --out output/flight.json

  # Resolve directly by transponder hex address (no airport needed):
  python3 opensky_to_flightjson.py \
      --icao24 3c6589 --date 2024-03-21 \
      --credentials credentials.json
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

# Make the cloned official OpenSky client importable at runtime.
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "opensky-api", "python")
)

import opensky_api  # noqa: E402  (path injected above)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EARTH_R = 6_371_000.0  # mean Earth radius, meters
SCHEMA_VERSION = 1
SOURCE = "opensky-rest-tracks"

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "output", "flight.json")


# ---------------------------------------------------------------------------
# Pure geo helpers (stdlib math only, no numpy)
# ---------------------------------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points, in METERS."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_R * c


def initial_bearing(lat1, lon1, lat2, lon2):
    """Initial great-circle bearing from point 1 to point 2, degrees in [0,360)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlon)
    theta = math.atan2(x, y)
    return (math.degrees(theta) + 360.0) % 360.0


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------
def utc_day_bounds(date_str):
    """Return (begin, end) Unix timestamps spanning the given UTC calendar day.

    The interval [begin, end) covers exactly one UTC day, which respects the
    OpenSky airport endpoints' "<= 1 UTC calendar day" limit.
    """
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise SystemExit(
            f"ERROR: invalid --date '{date_str}', expected YYYY-MM-DD ({exc})"
        )
    begin = int(day.timestamp())
    end = int((day + timedelta(days=1)).timestamp())
    return begin, end


def fmt_duration(seconds):
    """Human-friendly H:MM:SS for the stdout summary."""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Airport resolution
# ---------------------------------------------------------------------------
def airport_from_waypoint(icao, wp):
    """Build a schema airport dict dynamically from the API data.

    The OpenSky track already contains the departure/arrival *positions* (its
    first / last waypoints), so we never hardcode airport coordinates: lat/lon
    come straight from the relevant track endpoint, and the ICAO code from the
    flight record. iata/name are not provided by the API and stay null.

    Returns None if neither an ICAO code nor a waypoint is available.
    """
    icao = (icao or "").strip().upper() or None
    if icao is None and wp is None:
        return None
    return {
        "icao": icao,
        "iata": None,
        "name": None,
        "lat": float(wp["lat"]) if wp else None,
        "lon": float(wp["lon"]) if wp else None,
    }


# ---------------------------------------------------------------------------
# Aircraft / flight resolution
# ---------------------------------------------------------------------------
def resolve_by_callsign(api, callsign, dep_icao, begin, end, date_str):
    """Find the flight matching `callsign` departing `dep_icao` on the given day.

    Returns a FlightData object. Exits non-zero with a clear message on failure.
    """
    if not dep_icao:
        raise SystemExit(
            "ERROR: --callsign resolution requires --dep-icao (the departure "
            "airport ICAO). Without it we cannot look up departures, and a full "
            "interval scan is impractical. Either provide --dep-icao, or supply "
            "--icao24 directly."
        )

    target = callsign.strip().upper()
    dep = dep_icao.strip().upper()
    flights = api.get_departures_by_airport(dep, begin, end)
    if flights is None:
        raise SystemExit(
            f"ERROR: departures lookup for {dep} failed (None response: rate "
            "limit, auth, or server error). Try again or add --credentials."
        )
    if not flights:
        raise SystemExit(
            f"ERROR: no departures found for {dep} on {date_str}. "
            "Check the date / airport ICAO."
        )

    matches = []
    for fd in flights:
        cs = (fd.callsign or "").strip().upper()
        if cs == target:
            matches.append(fd)

    if not matches:
        seen_callsigns = sorted(
            {(fd.callsign or "").strip().upper() for fd in flights if fd.callsign}
        )[:15]
        raise SystemExit(
            f"ERROR: callsign {target} not found among departures from {dep} on "
            f"{date_str}. Some callsigns seen: {', '.join(seen_callsigns) or '(none)'}"
        )

    # Prefer a flight whose firstSeen is on the requested UTC date.
    on_date = [fd for fd in matches if begin <= (fd.firstSeen or 0) < end]
    chosen = on_date[0] if on_date else matches[0]
    return chosen


def resolve_by_icao24(api, icao24, begin, end, date_str):
    """Find the flight for `icao24` on the given UTC day via get_flights_by_aircraft."""
    hexid = icao24.strip().lower()
    flights = api.get_flights_by_aircraft(hexid, begin, end)
    if flights is None:
        raise SystemExit(
            f"ERROR: flights lookup for {hexid} failed (None response: rate "
            "limit, auth, or server error). Try again or add --credentials."
        )
    if not flights:
        raise SystemExit(f"ERROR: no flights found for icao24 {hexid} on {date_str}.")

    on_date = [fd for fd in flights if begin <= (fd.firstSeen or 0) < end]
    return on_date[0] if on_date else flights[0]


# ---------------------------------------------------------------------------
# Track -> waypoints
# ---------------------------------------------------------------------------
def build_waypoints(track):
    """Convert a FlightTrack into a list of schema waypoint dicts.

    Drops waypoints with null lat/lon. Fills alt_m, heading_deg, speed_mps per
    the schema rules. `track.path` is assumed roughly chronological; we sort by
    time defensively.
    """
    raw = [
        wp for wp in track.path if wp.latitude is not None and wp.longitude is not None
    ]
    raw.sort(key=lambda wp: wp.time if wp.time is not None else 0)
    n = len(raw)
    if n < 2:
        raise SystemExit(
            f"ERROR: track has {n} valid waypoint(s) (need >= 2). Nothing to write."
        )

    lats = [float(wp.latitude) for wp in raw]
    lons = [float(wp.longitude) for wp in raw]
    times = [int(wp.time) for wp in raw]
    on_ground = [bool(wp.on_ground) for wp in raw]

    # Altitude: baro_altitude only for REST tracks; 0.0 if null or on-ground.
    alts = []
    for wp in raw:
        ba = wp.baro_altitude
        if ba is None or wp.on_ground:
            alts.append(0.0)
        else:
            alts.append(float(ba))

    # Heading: use true_track when present, else great-circle bearing to next.
    headings = []
    for i in range(n):
        tt = raw[i].true_track
        if tt is not None:
            headings.append(float(tt) % 360.0)
        elif i < n - 1:
            headings.append(initial_bearing(lats[i], lons[i], lats[i + 1], lons[i + 1]))
        else:
            headings.append(headings[-1] if headings else 0.0)
    headings = [h % 360.0 for h in headings]

    # Speed: derived from consecutive waypoints (REST tracks lack velocity).
    speeds = [0.0] * n
    for i in range(1, n):
        dt = times[i] - times[i - 1]
        if dt > 0:
            dist = haversine(lats[i - 1], lons[i - 1], lats[i], lons[i])
            speeds[i] = dist / dt
        else:
            speeds[i] = speeds[i - 1]
    # First point copies the second's speed (or 0 if on ground).
    if n >= 2:
        speeds[0] = 0.0 if on_ground[0] else speeds[1]

    t0 = times[0]
    waypoints = []
    for i in range(n):
        waypoints.append(
            {
                "t": int(times[i]),
                "t_rel": float(times[i] - t0),
                "lat": float(lats[i]),
                "lon": float(lons[i]),
                "alt_m": float(alts[i]),
                "heading_deg": float(headings[i]),
                "speed_mps": float(max(speeds[i], 0.0)),
                "on_ground": bool(on_ground[i]),
            }
        )
    return waypoints


def compute_stats(waypoints):
    """Compute the schema `stats` block from a list of waypoint dicts."""
    n = len(waypoints)
    distance_m = 0.0
    for i in range(1, n):
        a, b = waypoints[i - 1], waypoints[i]
        distance_m += haversine(a["lat"], a["lon"], b["lat"], b["lon"])
    return {
        "num_waypoints": int(n),
        "duration_s": int(waypoints[-1]["t"] - waypoints[0]["t"]),
        "distance_km": round(distance_m / 1000.0, 3),
        "max_alt_m": float(max(wp["alt_m"] for wp in waypoints)),
        "max_speed_mps": float(max(wp["speed_mps"] for wp in waypoints)),
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def make_api(credentials):
    """Build an OpenSkyApi, authenticated if credentials are supplied."""
    if credentials:
        if not os.path.isfile(credentials):
            raise SystemExit(f"ERROR: credentials file not found: {credentials}")
        try:
            tm = opensky_api.TokenManager.from_json_file(credentials)
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise SystemExit(f"ERROR: bad credentials file {credentials}: {exc}")
        return opensky_api.OpenSkyApi(token_manager=tm)
    return opensky_api.OpenSkyApi()


def build_flight(args):
    if not args.callsign and not args.icao24:
        raise SystemExit("ERROR: provide at least one of --callsign or --icao24.")

    begin, end = utc_day_bounds(args.date)
    api = make_api(args.credentials)

    try:
        if args.icao24:
            flight = resolve_by_icao24(api, args.icao24, begin, end, args.date)
        else:
            flight = resolve_by_callsign(
                api, args.callsign, args.dep_icao, begin, end, args.date
            )

        icao24 = (flight.icao24 or "").strip().lower()
        if not icao24:
            raise SystemExit("ERROR: resolved flight has no icao24 address.")

        first_seen = int(flight.firstSeen) if flight.firstSeen else begin
        track = api.get_track_by_aircraft(icao24, t=first_seen)
        if track is None:
            raise SystemExit(
                f"ERROR: no track returned for icao24 {icao24} at t={first_seen} "
                "(None response: 404/no-data, rate limit, or the >30-day window). "
                "The /tracks/all endpoint only serves the last 30 days."
            )
        if not getattr(track, "path", None):
            raise SystemExit(
                f"ERROR: track for icao24 {icao24} has an empty path. Nothing to write."
            )

        waypoints = build_waypoints(track)
        stats = compute_stats(waypoints)
    finally:
        api.close()

    # Origin/destination: ICAO from the API (CLI args take precedence), and the
    # coordinates derived dynamically from the track's first/last waypoints.
    dep_icao = args.dep_icao or getattr(flight, "estDepartureAirport", None)
    arr_icao = args.arr_icao or getattr(flight, "estArrivalAirport", None)
    origin = airport_from_waypoint(dep_icao, waypoints[0] if waypoints else None)
    destination = airport_from_waypoint(arr_icao, waypoints[-1] if waypoints else None)

    callsign = (flight.callsign or args.callsign or "").strip().upper() or None

    meta = {
        "flight_number": args.flight_number,
        "callsign": callsign,
        "icao24": icao24,
        "date": args.date,
        "source": SOURCE,
        "generated_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "meta": meta,
        "origin": origin,
        "destination": destination,
        "waypoints": waypoints,
        "stats": stats,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="opensky_to_flightjson.py",
        description=(
            "Fetch a real flight trajectory from the OpenSky REST API and emit a "
            "flight.json conforming to FLIGHT_SCHEMA.md (v1)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # By callsign + departure airport (recommended):\n"
            "  python3 opensky_to_flightjson.py --callsign DLH401 --date 2024-03-21 \\\n"
            "      --dep-icao KJFK --arr-icao EDDF --flight-number LH401 \\\n"
            "      --credentials credentials.json --out output/flight.json\n\n"
            "  # By transponder hex address (no airport needed):\n"
            "  python3 opensky_to_flightjson.py --icao24 3c6589 --date 2024-03-21 \\\n"
            "      --credentials credentials.json\n\n"
            "Note: the /tracks/all endpoint only serves the last 30 days of data."
        ),
    )
    parser.add_argument(
        "--callsign",
        help="ICAO callsign as broadcast, e.g. DLH401. Requires --dep-icao to resolve.",
    )
    parser.add_argument(
        "--icao24",
        help="Transponder hex address, e.g. 3c6589 (lowercase). Resolves directly.",
    )
    parser.add_argument(
        "--date",
        required=True,
        help="UTC date of departure, ISO YYYY-MM-DD.",
    )
    parser.add_argument(
        "--dep-icao",
        help="Departure airport ICAO (used to resolve callsign and fill origin).",
    )
    parser.add_argument(
        "--arr-icao",
        help="Arrival airport ICAO (used to fill destination).",
    )
    parser.add_argument(
        "--flight-number",
        help="IATA flight number for meta, e.g. LH401.",
    )
    parser.add_argument(
        "--credentials",
        help="Path to credentials.json ({clientId, clientSecret}). Omit for anonymous.",
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help=f"Output path for flight.json (default: {DEFAULT_OUT}).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    flight = build_flight(args)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(flight, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    s = flight["stats"]
    m = flight["meta"]
    print(f"Wrote {args.out}")
    print(f"  icao24        : {m['icao24']}")
    print(f"  callsign      : {m['callsign']}")
    print(f"  num_waypoints : {s['num_waypoints']}")
    print(f"  duration_s    : {s['duration_s']} ({fmt_duration(s['duration_s'])})")
    print(f"  distance_km   : {s['distance_km']}")
    print(f"  max_alt_m     : {s['max_alt_m']}")
    print(f"  max_speed_mps : {s['max_speed_mps']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
