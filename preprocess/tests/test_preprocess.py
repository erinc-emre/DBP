"""Tests for the external preprocessor's pure helpers and the JSON validator.

Run from anywhere:  pytest preprocess/tests
These are stdlib/pure-function tests — no network, no Blender, no OpenSky client.
"""

import json
import os
import sys
import time

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PREPROCESS = os.path.dirname(HERE)
if PREPROCESS not in sys.path:
    sys.path.insert(0, PREPROCESS)

import opensky_to_flightjson as otf  # noqa: E402
import validate_flight_json as vfj  # noqa: E402

DAY = 86400


# --- pure geo/time helpers -------------------------------------------------
def test_within_tracks_window_recent_vs_old():
    now = time.time()
    assert otf.within_tracks_window(now - 2 * DAY, now) is True
    assert otf.within_tracks_window(now - 40 * DAY, now) is False


def test_within_tracks_window_boundary():
    now = time.time()
    # exactly at the window edge counts as inside
    assert otf.within_tracks_window(now - otf.TRACKS_WINDOW_DAYS * DAY, now) is True


def test_haversine_known_distance():
    # Frankfurt (EDDF) -> Madrid (LEMD) is ~1420 km
    km = otf.haversine(50.03, 8.57, 40.47, -3.56) / 1000.0
    assert 1380 < km < 1460


def test_haversine_zero():
    assert otf.haversine(10.0, 20.0, 10.0, 20.0) == pytest.approx(0.0, abs=1e-6)


def test_initial_bearing_cardinal():
    # due north ~ 0deg, due east ~ 90deg
    assert otf.initial_bearing(0.0, 0.0, 1.0, 0.0) == pytest.approx(0.0, abs=1.0)
    assert otf.initial_bearing(0.0, 0.0, 0.0, 1.0) == pytest.approx(90.0, abs=1.0)


# --- JSON schema validator -------------------------------------------------
def test_validator_accepts_real_flight():
    with open(os.path.join(PREPROCESS, "flight.json")) as fh:
        data = json.load(fh)
    errors = vfj.validate(data)
    assert errors == [], f"expected valid, got: {errors}"


def test_validator_rejects_garbage():
    assert vfj.validate({"nonsense": True})  # non-empty error list
    assert vfj.validate([])  # wrong root type


def test_validator_rejects_too_few_waypoints():
    data = {
        "meta": {"schema_version": 1, "source": "opensky-rest-tracks"},
        "waypoints": [{"t": 0, "t_rel": 0.0, "lat": 0.0, "lon": 0.0, "alt_m": 0.0}],
    }
    assert vfj.validate(data)  # needs >= 2 waypoints
