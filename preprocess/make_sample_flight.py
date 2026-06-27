#!/usr/bin/env python3
"""Generate a realistic SAMPLE flight trajectory (LH401, JFK -> FRA, 2024-03-21).

Produces `sample_flight.json` conforming to FLIGHT_SCHEMA.md (v1). Pure offline,
great-circle route, smooth altitude/speed profiles. Units are SI throughout.
"""

import json
import math
import os
from datetime import datetime, timezone

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EARTH_R = 6_371_000.0  # mean Earth radius, meters

ORIGIN = {
    "icao": "KJFK",
    "iata": "JFK",
    "name": "John F. Kennedy International Airport",
    "lat": 40.6398,
    "lon": -73.7789,
}
DESTINATION = {
    "icao": "EDDF",
    "iata": "FRA",
    "name": "Frankfurt am Main Airport",
    "lat": 50.0333,
    "lon": 8.5706,
}

NUM_WAYPOINTS = 380  # in the 300-450 range
DURATION_S = 27000  # 7h30m
CRUISE_ALT_M = 11300.0  # ~FL370
CRUISE_SPEED_MPS = 250.0  # ~900 km/h ground speed
CLIMB_FRAC = 20.0 / 450.0  # ~20 min of a 450-min flight spent climbing
DESCENT_FRAC = 25.0 / 450.0  # ~25 min spent descending

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "sample_flight.json")


# ---------------------------------------------------------------------------
# Pure geo helpers
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


def slerp_great_circle(lat1, lon1, lat2, lon2, fractions):
    """Spherical interpolation (slerp) of unit vectors along the great circle.

    `fractions` is an array in [0,1]. Returns (lats, lons) in degrees.
    """
    p1, l1 = math.radians(lat1), math.radians(lon1)
    p2, l2 = math.radians(lat2), math.radians(lon2)

    # unit vectors on the sphere
    v1 = np.array(
        [math.cos(p1) * math.cos(l1), math.cos(p1) * math.sin(l1), math.sin(p1)]
    )
    v2 = np.array(
        [math.cos(p2) * math.cos(l2), math.cos(p2) * math.sin(l2), math.sin(p2)]
    )

    dot = float(np.clip(np.dot(v1, v2), -1.0, 1.0))
    omega = math.acos(dot)  # angular distance between endpoints

    fr = np.asarray(fractions, dtype=float)
    if omega < 1e-12:
        # coincident endpoints: degenerate, just repeat
        lats = np.full_like(fr, lat1)
        lons = np.full_like(fr, lon1)
        return lats, lons

    sin_omega = math.sin(omega)
    a = np.sin((1.0 - fr) * omega) / sin_omega
    b = np.sin(fr * omega) / sin_omega
    # shape (N, 3)
    pts = np.outer(a, v1) + np.outer(b, v2)
    norms = np.linalg.norm(pts, axis=1, keepdims=True)
    pts = pts / norms

    lats = np.degrees(np.arcsin(np.clip(pts[:, 2], -1.0, 1.0)))
    lons = np.degrees(np.arctan2(pts[:, 1], pts[:, 0]))
    return lats, lons


# ---------------------------------------------------------------------------
# Profile helpers
# ---------------------------------------------------------------------------
def smoothstep(x):
    """Classic smoothstep on [0,1] -> [0,1]."""
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def altitude_profile(frac):
    """Altitude in meters as a function of normalized flight progress [0,1].

    Smooth climb over first CLIMB_FRAC, constant cruise, smooth descent over
    last DESCENT_FRAC. Ground (0) at both ends.
    """
    f = np.asarray(frac, dtype=float)
    alt = np.full_like(f, CRUISE_ALT_M)

    # climb
    climb_mask = f < CLIMB_FRAC
    alt[climb_mask] = CRUISE_ALT_M * smoothstep(f[climb_mask] / CLIMB_FRAC)

    # descent
    desc_start = 1.0 - DESCENT_FRAC
    desc_mask = f > desc_start
    desc_x = (f[desc_mask] - desc_start) / DESCENT_FRAC
    alt[desc_mask] = CRUISE_ALT_M * (1.0 - smoothstep(desc_x))

    # hard-pin the very ends to 0
    alt[0] = 0.0
    alt[-1] = 0.0
    return alt


def speed_profile(frac):
    """Ground speed in m/s as a function of normalized progress [0,1].

    ~0 at the ends, smooth ramp to cruise, smooth ramp down. Slightly wider
    accel windows than altitude so it feels like a realistic takeoff/landing.
    """
    f = np.asarray(frac, dtype=float)
    spd = np.full_like(f, CRUISE_SPEED_MPS)

    accel_frac = CLIMB_FRAC * 1.1
    decel_frac = DESCENT_FRAC * 1.1

    accel_mask = f < accel_frac
    spd[accel_mask] = CRUISE_SPEED_MPS * smoothstep(f[accel_mask] / accel_frac)

    decel_start = 1.0 - decel_frac
    decel_mask = f > decel_start
    decel_x = (f[decel_mask] - decel_start) / decel_frac
    spd[decel_mask] = CRUISE_SPEED_MPS * (1.0 - smoothstep(decel_x))

    spd[0] = 0.0
    spd[-1] = 0.0
    return np.maximum(spd, 0.0)


# ---------------------------------------------------------------------------
# Build the flight
# ---------------------------------------------------------------------------
def build_flight():
    n = NUM_WAYPOINTS

    # Normalized progress with finer spacing near the ends (climb/descent),
    # coarser at cruise. We warp an even grid using a symmetric ease.
    u = np.linspace(0.0, 1.0, n)
    # blend even spacing with a smoothstep-warped one to densify the ends
    warp = 0.35
    frac = (1.0 - warp) * u + warp * smoothstep(u)
    # ensure exact endpoints & monotonic
    frac[0] = 0.0
    frac[-1] = 1.0

    # Positions along the great circle
    lats, lons = slerp_great_circle(
        ORIGIN["lat"],
        ORIGIN["lon"],
        DESTINATION["lat"],
        DESTINATION["lon"],
        frac,
    )
    # pin endpoints exactly to airport coords
    lats[0], lons[0] = ORIGIN["lat"], ORIGIN["lon"]
    lats[-1], lons[-1] = DESTINATION["lat"], DESTINATION["lon"]

    # Times: distribute proportionally to progress (so denser ends => finer dt).
    t0_dt = datetime(2024, 3, 21, 1, 0, 0, tzinfo=timezone.utc)
    t0 = int(t0_dt.timestamp())
    t_rel = frac * DURATION_S
    t_rel = t_rel - t_rel[0]  # guarantee t_rel[0] == 0.0
    t_abs = (t0 + np.round(t_rel)).astype(np.int64)

    # Make absolute times strictly ascending (rounding could tie at the ends).
    for i in range(1, n):
        if t_abs[i] <= t_abs[i - 1]:
            t_abs[i] = t_abs[i - 1] + 1
    t_rel = (t_abs - t_abs[0]).astype(float)

    alts = altitude_profile(frac)
    speeds = speed_profile(frac)

    # Headings: great-circle initial bearing to the next point; last copies prev.
    headings = np.zeros(n)
    for i in range(n - 1):
        headings[i] = initial_bearing(lats[i], lons[i], lats[i + 1], lons[i + 1])
    headings[-1] = headings[-2] if n >= 2 else 0.0
    headings = np.mod(headings, 360.0)

    waypoints = []
    for i in range(n):
        on_ground = bool(i == 0 or i == n - 1)
        waypoints.append(
            {
                "t": int(t_abs[i]),
                "t_rel": float(t_rel[i]),
                "lat": float(lats[i]),
                "lon": float(lons[i]),
                "alt_m": float(alts[i]),
                "heading_deg": float(headings[i]),
                "speed_mps": float(speeds[i]),
                "on_ground": on_ground,
            }
        )

    # Stats
    distance_m = 0.0
    for i in range(1, n):
        distance_m += haversine(lats[i - 1], lons[i - 1], lats[i], lons[i])

    stats = {
        "num_waypoints": int(n),
        "duration_s": int(t_abs[-1] - t_abs[0]),
        "distance_km": round(distance_m / 1000.0, 3),
        "max_alt_m": float(np.max(alts)),
        "max_speed_mps": float(np.max(speeds)),
    }

    meta = {
        "flight_number": "LH401",
        "callsign": "DLH401",
        "icao24": "3c6589",
        "date": "2024-03-21",
        "source": "sample",
        "generated_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    }

    return {
        "schema_version": 1,
        "meta": meta,
        "origin": dict(ORIGIN),
        "destination": dict(DESTINATION),
        "waypoints": waypoints,
        "stats": stats,
    }


def main():
    flight = build_flight()
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(flight, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    s = flight["stats"]
    print(f"Wrote {OUT_PATH}")
    print(f"  num_waypoints : {s['num_waypoints']}")
    print(f"  duration_s    : {s['duration_s']}")
    print(f"  distance_km   : {s['distance_km']}")
    print(f"  max_alt_m     : {s['max_alt_m']}")
    print(f"  max_speed_mps : {s['max_speed_mps']}")


if __name__ == "__main__":
    main()
