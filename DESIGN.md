# Design Notes — Historical Flight Visualization in Blender

A consolidated record of the key design decisions. Guiding principle: a **solid,
simple, readable** tool — clarity and reliability over flashiness.

## Architecture: two clean halves

```
OpenSky REST ──► preprocess/opensky_to_flightjson.py ──► flight.json ──► Blender add-on ──► scene + render
                 (fetch, clean, resample, derive)         (contract)      (visualize only)
```

- **Outside Blender** (`preprocess/`): all network I/O, OAuth2, and data wrangling.
  Blender's bundled Python is awkward for `requests`/OAuth2, so this stays external.
- **Inside Blender** (`blender/flight_viz_addon/`): *only* consumes `flight.json`
  and builds/animates the scene. No network, no credentials.
- The two sides meet at a **documented JSON contract** (`preprocess/FLIGHT_SCHEMA.md`),
  enforced by a stdlib-only validator (`validate_flight_json.py`). If the JSON passes
  the validator, Blender is happy — the halves can evolve independently.

## Data pipeline decisions

- **Keyed on `icao24`, not flight number.** OpenSky has no flight-number primary key,
  so a callsign is resolved to a transponder address via the departures endpoint first.
- **OAuth2** for auth (the API moved off basic auth).
- **REST `/tracks` only serves ~30 days.** We fail early with a clear message
  (`within_tracks_window`) rather than emit a confusing empty result. Older flights
  would need Trino research access (out of scope).
- **Speed is derived** from consecutive waypoints (REST tracks carry no velocity).
  Approximate but the only option for this source; documented as such.
- **SI units all the way** (metres, seconds, m/s) — no unit juggling in Blender.

## Geo / coordinate decisions

- **Longitude calibration.** The Earth texture's zero meridian doesn't line up with
  longitude 0; the offset was measured directly from the model's UV data
  (`LON_OFFSET ≈ -177.19°`). It's now a **UI setting** so a different Earth asset can
  be recalibrated without code changes.
- **Radius-relative altitude.** Waypoints sit at `radius = R_base·(1 + alt_m/R_earth·k)`
  — altitude as a fraction of Earth radius, not an absolute offset stacked next to the
  model. Scale-independent and consistent with terrain/clouds by construction.
- **Vertical exaggeration** (`altitude_exaggeration`, `terrain_exaggeration`) is
  configurable; keeping them consistent avoids the route burying itself in mountains.
- **Jitter smoothing.** Raw ADS-B points are noisy, so the path is moving-average
  smoothed before the aircraft follows it.

## Camera design

- **Chase camera** trails the aircraft and **looks at it**, but its "up" is the Earth
  radial — so the **width axis stays parallel to the surface** (level horizon, no
  banking); only pitch follows the plane. Lens (zoom) is a UI setting.
- **Terrain-aware clamp** keeps the chase cam from clipping underground at takeoff/
  landing (a KD-tree over the displaced Earth gives the local ground height).
- **Overview camera** frames the whole route from orbit; an optional **cinematic orbit**
  sweeps a slow arc around the route centre.

## Animation & timing

- **Frame ↔ real time** is a single linear mapping shared by the aircraft, chase cam,
  and sun, so they never drift.
- **Length modes:** *fixed* (`base_frames / speed`, every flight the same length) or
  *scale-to-duration* (`real_seconds / time_compression · fps`, so long flights play
  longer).
- **Sun** is positioned from the flight's real UTC timestamps (subsolar point), so the
  day/night terminator matches the actual date/time — the Earth itself doesn't spin.

## Rendering

- **EEVEE** is the chosen engine: fast enough for iteration and quick sample videos;
  Cycles was not worth the render-time cost for this project's look.
- **Render Video button** bakes an MP4 (`flight_<camera>_<datetime>.mp4`) with a chosen
  camera + resolution into `//renders` (git-ignored).

## Portability & hygiene

- `.blend` texture paths are **relative** (`//textures/...`); textures are tracked in
  the repo, so the scene opens anywhere.
- The aircraft model is embedded in the `.blend` (not a linked library).
- `requirements.txt` pins the preprocessor deps; `preprocess/tests/` has a pytest suite
  for the pure helpers + validator.
- Secrets (`credentials.json`) and rendered output are git-ignored.

## Non-goals (descoped)

- **Weather visualization** (ERA5/NetCDF → texture overlay) — dropped to keep the
  project focused on a solid flight visualization.
