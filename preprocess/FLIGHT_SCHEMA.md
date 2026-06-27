# `flight.json` Schema (v1) — shared contract

This is the **single source of truth** for the JSON that the external preprocessor
produces and that the Blender add-on consumes. All producers (OpenSky preprocessor,
sample generator) and consumers (validator, Blender importer) MUST conform to this.

## Top-level object

```jsonc
{
  "schema_version": 1,

  "meta": {
    "flight_number": "LH401",        // IATA flight number (string, may be null)
    "callsign": "DLH401",            // ICAO callsign as broadcast (string, may be null)
    "icao24": "3c6589",              // transponder hex, lowercase (string, may be null)
    "date": "2024-03-21",            // UTC date of departure, ISO YYYY-MM-DD
    "source": "opensky-rest-tracks", // one of: "opensky-rest-tracks", "opensky-trino", "sample"
    "generated_at": "2024-03-22T10:00:00Z" // ISO 8601 UTC, when this file was produced
  },

  "origin": {                        // may be null if unknown
    "icao": "KJFK",                  // 4-letter ICAO (string|null)
    "iata": "JFK",                   // 3-letter IATA (string|null)
    "name": "John F. Kennedy International Airport", // string|null
    "lat": 40.6398,                  // WGS-84 decimal degrees (number|null if coords unresolved)
    "lon": -73.7789                  // (number|null if coords unresolved)
  },
  "destination": { /* same shape as origin */ },

  "waypoints": [                     // chronological, ascending t; >= 2 entries
    {
      "t": 1711008000,              // absolute Unix time (int seconds)
      "t_rel": 0.0,                 // seconds since first waypoint (float, t_rel[0] == 0.0)
      "lat": 40.6398,               // WGS-84 decimal degrees (float)
      "lon": -73.7789,
      "alt_m": 0.0,                 // altitude in METERS (float). Prefer geoaltitude;
                                    //   fall back to baro_altitude. 0.0 if on ground/unknown.
      "heading_deg": 45.0,          // true track, degrees clockwise from north [0,360) (float)
      "speed_mps": 0.0,             // ground speed in METERS/SECOND (float, >= 0)
      "on_ground": true             // bool
    }
    // ...
  ],

  "stats": {
    "num_waypoints": 350,           // int == len(waypoints)
    "duration_s": 28800,            // int, waypoints[-1].t - waypoints[0].t
    "distance_km": 6200.0,          // float, summed great-circle distance along path
    "max_alt_m": 11900.0,           // float, max altitude over the track
    "max_speed_mps": 255.0          // float, max ground speed over the track
  }
}
```

## Rules / invariants

1. **Units are SI**: meters, meters/second, Unix seconds. No knots, no feet. (OpenSky
   already returns m and m/s, so no conversion is needed from the API.)
2. `waypoints` is sorted ascending by `t`; `t_rel = t - waypoints[0].t`.
3. `heading_deg` is normalized to `[0, 360)`. If the API value is missing, derive it
   from the bearing to the next waypoint (great-circle initial bearing).
4. `speed_mps`: use the API value when present (Trino `velocity`); for REST tracks
   (which lack speed) derive it from consecutive waypoints:
   `speed = haversine_distance(prev, cur) / (t_cur - t_prev)`. First point copies the
   second point's speed (or 0 if on ground).
5. Null handling: a waypoint with null lat/lon from the API is dropped. Other nulls
   (alt/heading/speed) are filled per rules above; never leave them null in output.
6. The file MUST be valid JSON, UTF-8, pretty-printed with 2-space indent.
7. `origin`/`destination` may be `null` if not resolvable. They may also be an object
   whose `lat`/`lon` are `null` (airport known by ICAO but coordinates unavailable in
   the local table). The Blender importer must tolerate both cases (skip the marker
   when coordinates are missing).

## Notes for the Blender consumer (informational, not part of the file)

- Convert `(lat, lon, alt_m)` to a 3D point on a sphere of radius `R` (Blender units):
  `R_eff = R + alt_m * (R / 6_371_000) * ALT_EXAGGERATION`.
- `heading_deg` drives aircraft yaw; tangent of the path can refine pitch/bank.
