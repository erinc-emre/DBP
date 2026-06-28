#!/usr/bin/env python3
"""Standalone validator for `flight.json` files (FLIGHT_SCHEMA.md, v1).

Stdlib only. Usable two ways:

    # as a CLI
    python3 validate_flight_json.py <path-to-flight.json>

    # as a library
    from validate_flight_json import validate
    errors = validate(data)   # -> list[str]; empty list means valid

The validator is intentionally strict: it reports *all* problems it finds rather
than bailing on the first one, so a single run gives an actionable list.
"""

import json
import math
import re
import sys

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
SCHEMA_VERSION = 1
VALID_SOURCES = {"opensky-rest-tracks", "opensky-trino"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Tolerances from the schema rules.
T_REL_ZERO_TOL = 1e-6  # t_rel[0] must equal 0.0 within this
T_REL_MATCH_TOL = 1.0  # abs(t_rel[i] - (t[i]-t[0])) must be < this
STATS_FLOAT_TOL = 1e-3  # stats.max_* vs computed max

# Required per-waypoint numeric fields and their acceptable types.
_WP_NUMERIC_FIELDS = ("t", "t_rel", "lat", "lon", "alt_m", "heading_deg", "speed_mps")


# --------------------------------------------------------------------------- #
# Small type helpers (note: bool is a subclass of int in Python, so we must
# explicitly reject bool where a real number/int is expected, and vice-versa).
# --------------------------------------------------------------------------- #
def _is_real_number(x):
    """True for int/float (NOT bool) and finite (not NaN/inf)."""
    if isinstance(x, bool):
        return False
    if not isinstance(x, (int, float)):
        return False
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _is_int(x):
    """True for a real integer value (NOT bool)."""
    return isinstance(x, int) and not isinstance(x, bool)


def _is_bool(x):
    return isinstance(x, bool)


def _is_str(x):
    return isinstance(x, str)


def _is_str_or_none(x):
    return x is None or isinstance(x, str)


# --------------------------------------------------------------------------- #
# Section validators
# --------------------------------------------------------------------------- #
def _validate_meta(meta, errors):
    if not isinstance(meta, dict):
        errors.append("meta: must be an object")
        return

    # nullable strings
    for key in ("flight_number", "callsign", "icao24"):
        if key not in meta:
            errors.append(f"meta.{key}: missing")
        elif not _is_str_or_none(meta[key]):
            errors.append(f"meta.{key}: must be a string or null")

    # date
    if "date" not in meta:
        errors.append("meta.date: missing")
    elif not _is_str(meta["date"]):
        errors.append("meta.date: must be a string")
    elif not DATE_RE.match(meta["date"]):
        errors.append(f"meta.date: must match YYYY-MM-DD (got {meta['date']!r})")

    # source
    if "source" not in meta:
        errors.append("meta.source: missing")
    elif meta["source"] not in VALID_SOURCES:
        errors.append(
            f"meta.source: must be one of {sorted(VALID_SOURCES)} "
            f"(got {meta['source']!r})"
        )

    # generated_at
    if "generated_at" not in meta:
        errors.append("meta.generated_at: missing")
    elif not _is_str(meta["generated_at"]):
        errors.append("meta.generated_at: must be a string")


def _validate_airport(obj, label, errors):
    """origin/destination may be null or an object with icao,iata,name,lat,lon."""
    if obj is None:
        return  # null is allowed
    if not isinstance(obj, dict):
        errors.append(f"{label}: must be null or an object")
        return

    for key in ("icao", "iata", "name"):
        if key not in obj:
            errors.append(f"{label}.{key}: missing")
        elif not _is_str_or_none(obj[key]):
            errors.append(f"{label}.{key}: must be a string or null")

    # lat/lon may be null when the airport is known by ICAO but its coordinates
    # could not be resolved (e.g. not in the local airports table). When present
    # as numbers they must be in range. A null-coords airport simply gets no marker.
    if "lat" not in obj:
        errors.append(f"{label}.lat: missing")
    elif obj["lat"] is not None:
        if not _is_real_number(obj["lat"]):
            errors.append(f"{label}.lat: must be a number or null")
        elif not (-90.0 <= float(obj["lat"]) <= 90.0):
            errors.append(f"{label}.lat: out of range [-90,90] (got {obj['lat']})")

    if "lon" not in obj:
        errors.append(f"{label}.lon: missing")
    elif obj["lon"] is not None:
        if not _is_real_number(obj["lon"]):
            errors.append(f"{label}.lon: must be a number or null")
        elif not (-180.0 <= float(obj["lon"]) <= 180.0):
            errors.append(f"{label}.lon: out of range [-180,180] (got {obj['lon']})")


def _validate_one_waypoint(wp, i, errors):
    """Validate a single waypoint object's shape and field ranges."""
    if not isinstance(wp, dict):
        errors.append(f"waypoints[{i}]: must be an object")
        return

    # presence + type for numeric fields
    for key in _WP_NUMERIC_FIELDS:
        if key not in wp:
            errors.append(f"waypoints[{i}].{key}: missing")
            continue
        val = wp[key]
        if val is None:
            errors.append(f"waypoints[{i}].{key}: must not be null")
            continue
        if key == "t":
            if not _is_int(val):
                errors.append(f"waypoints[{i}].t: must be an int")
        else:
            if not _is_real_number(val):
                errors.append(f"waypoints[{i}].{key}: must be a number")

    # on_ground must be bool
    if "on_ground" not in wp:
        errors.append(f"waypoints[{i}].on_ground: missing")
    elif not _is_bool(wp["on_ground"]):
        errors.append(f"waypoints[{i}].on_ground: must be a bool")

    # range checks (only when the values are usable numbers)
    if _is_real_number(wp.get("lat")) and not (-90.0 <= float(wp["lat"]) <= 90.0):
        errors.append(f"waypoints[{i}].lat: out of range [-90,90] (got {wp['lat']})")
    if _is_real_number(wp.get("lon")) and not (-180.0 <= float(wp["lon"]) <= 180.0):
        errors.append(f"waypoints[{i}].lon: out of range [-180,180] (got {wp['lon']})")
    if _is_real_number(wp.get("heading_deg")) and not (
        0.0 <= float(wp["heading_deg"]) < 360.0
    ):
        errors.append(
            f"waypoints[{i}].heading_deg: out of range [0,360) (got {wp['heading_deg']})"
        )
    if _is_real_number(wp.get("speed_mps")) and float(wp["speed_mps"]) < 0.0:
        errors.append(f"waypoints[{i}].speed_mps: must be >= 0 (got {wp['speed_mps']})")


def _validate_waypoints(waypoints, errors):
    """Validate the waypoints list; returns the list (or None if unusable)."""
    if not isinstance(waypoints, list):
        errors.append("waypoints: must be a list")
        return None
    if len(waypoints) < 2:
        errors.append(f"waypoints: must have >= 2 entries (got {len(waypoints)})")

    for i, wp in enumerate(waypoints):
        _validate_one_waypoint(wp, i, errors)

    # Cross-waypoint checks need clean t / t_rel values; gather them safely.
    if len(waypoints) < 2:
        return waypoints

    ts = []
    t_rels = []
    ok_for_cross_checks = True
    for wp in waypoints:
        if (
            not isinstance(wp, dict)
            or not _is_int(wp.get("t"))
            or not _is_real_number(wp.get("t_rel"))
        ):
            ok_for_cross_checks = False
            break
        ts.append(int(wp["t"]))
        t_rels.append(float(wp["t_rel"]))

    if not ok_for_cross_checks:
        errors.append(
            "waypoints: cannot run ordering/t_rel checks because some t/t_rel "
            "values are missing or the wrong type"
        )
        return waypoints

    # non-decreasing by t
    for i in range(1, len(ts)):
        if ts[i] < ts[i - 1]:
            errors.append(
                f"waypoints[{i}].t: not sorted ascending "
                f"(t={ts[i]} < previous t={ts[i - 1]})"
            )

    # t_rel[0] == 0.0
    if abs(t_rels[0] - 0.0) > T_REL_ZERO_TOL:
        errors.append(f"waypoints[0].t_rel: must be 0.0 (got {t_rels[0]})")

    # t_rel[i] ~= t[i] - t[0]
    t0 = ts[0]
    for i in range(len(ts)):
        expected = ts[i] - t0
        if abs(t_rels[i] - expected) >= T_REL_MATCH_TOL:
            errors.append(
                f"waypoints[{i}].t_rel: {t_rels[i]} does not match t[i]-t[0]="
                f"{expected} (tol {T_REL_MATCH_TOL})"
            )

    return waypoints


def _validate_stats(stats, waypoints, errors):
    if not isinstance(stats, dict):
        errors.append("stats: must be an object")
        return

    # numeric presence/type
    if "num_waypoints" not in stats:
        errors.append("stats.num_waypoints: missing")
    elif not _is_int(stats["num_waypoints"]):
        errors.append("stats.num_waypoints: must be an int")

    if "duration_s" not in stats:
        errors.append("stats.duration_s: missing")
    elif not _is_real_number(stats["duration_s"]):
        errors.append("stats.duration_s: must be a number")

    for key in ("distance_km", "max_alt_m", "max_speed_mps"):
        if key not in stats:
            errors.append(f"stats.{key}: missing")
        elif not _is_real_number(stats[key]):
            errors.append(f"stats.{key}: must be a number")

    # The following consistency checks need a usable waypoints list.
    if not isinstance(waypoints, list) or len(waypoints) == 0:
        return

    # num_waypoints == len(waypoints)
    if _is_int(stats.get("num_waypoints")) and stats["num_waypoints"] != len(waypoints):
        errors.append(
            f"stats.num_waypoints: {stats['num_waypoints']} != len(waypoints)="
            f"{len(waypoints)}"
        )

    # duration_s == t[-1] - t[0]
    first_t = waypoints[0].get("t") if isinstance(waypoints[0], dict) else None
    last_t = waypoints[-1].get("t") if isinstance(waypoints[-1], dict) else None
    duration = stats.get("duration_s")
    if (
        _is_int(first_t)
        and _is_int(last_t)
        and isinstance(first_t, int)
        and isinstance(last_t, int)
        and _is_real_number(duration)
        and isinstance(duration, (int, float))
    ):
        expected_dur = last_t - first_t
        if float(duration) != float(expected_dur):
            errors.append(f"stats.duration_s: {duration} != t[-1]-t[0]={expected_dur}")

    # max_alt_m / max_speed_mps sanity vs the actual track maxima
    alts = [
        float(wp["alt_m"])
        for wp in waypoints
        if isinstance(wp, dict) and _is_real_number(wp.get("alt_m"))
    ]
    speeds = [
        float(wp["speed_mps"])
        for wp in waypoints
        if isinstance(wp, dict) and _is_real_number(wp.get("speed_mps"))
    ]
    if alts and _is_real_number(stats.get("max_alt_m")):
        if abs(float(stats["max_alt_m"]) - max(alts)) > STATS_FLOAT_TOL:
            errors.append(
                f"stats.max_alt_m: {stats['max_alt_m']} != max(alt_m)={max(alts)} "
                f"(tol {STATS_FLOAT_TOL})"
            )
    if speeds and _is_real_number(stats.get("max_speed_mps")):
        if abs(float(stats["max_speed_mps"]) - max(speeds)) > STATS_FLOAT_TOL:
            errors.append(
                f"stats.max_speed_mps: {stats['max_speed_mps']} != "
                f"max(speed_mps)={max(speeds)} (tol {STATS_FLOAT_TOL})"
            )


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def validate(data):
    """Validate a parsed flight.json object against FLIGHT_SCHEMA.md (v1).

    Returns a list of human-readable error strings. An empty list means the
    document is valid.
    """
    errors = []

    if not isinstance(data, dict):
        return ["root: must be a JSON object"]

    # ---- top-level keys present ----
    for key in (
        "schema_version",
        "meta",
        "origin",
        "destination",
        "waypoints",
        "stats",
    ):
        if key not in data:
            errors.append(f"top-level key {key!r}: missing")

    # ---- schema_version ----
    if "schema_version" in data and data["schema_version"] != SCHEMA_VERSION:
        errors.append(
            f"schema_version: must == {SCHEMA_VERSION} (got {data['schema_version']!r})"
        )

    # ---- meta ----
    if "meta" in data:
        _validate_meta(data["meta"], errors)

    # ---- origin / destination ----
    if "origin" in data:
        _validate_airport(data["origin"], "origin", errors)
    if "destination" in data:
        _validate_airport(data["destination"], "destination", errors)

    # ---- waypoints ----
    waypoints = None
    if "waypoints" in data:
        waypoints = _validate_waypoints(data["waypoints"], errors)

    # ---- stats ----
    if "stats" in data:
        _validate_stats(data["stats"], waypoints, errors)

    return errors


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _main(argv):
    if len(argv) != 2:
        print("usage: python3 validate_flight_json.py <path-to-flight.json>")
        return 2

    path = argv[1]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        print(f"FAIL: file not found: {path}")
        return 1
    except json.JSONDecodeError as exc:
        print(f"FAIL: not valid JSON: {exc}")
        return 1
    except OSError as exc:
        print(f"FAIL: could not read {path}: {exc}")
        return 1

    errors = validate(data)
    if not errors:
        nwp = len(data["waypoints"]) if isinstance(data.get("waypoints"), list) else "?"
        print(f"PASS: {path} conforms to flight.json schema v1 ({nwp} waypoints)")
        return 0

    print(f"FAIL: {path} has {len(errors)} problem(s):")
    for err in errors:
        print(f"  - {err}")
    return 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
