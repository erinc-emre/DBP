# Project Gaps & Open Work

Status tracker for **Historical Flight & Weather Visualization in Blender**.
Reflects the state after the data-pipeline + Blender importer milestone.

Legend: ✅ done · 🟡 partial · ❌ not started

---

## 1. Data pipeline (external preprocessing)

| Item | Status | Notes / gap |
|---|---|---|
| `flight.json` schema contract | ✅ | `preprocess/FLIGHT_SCHEMA.md` (v1, SI units) |
| Offline mode | ✅ | A saved real `flight.json` is self-contained (no synthetic sample data; offline = reuse a saved real flight) |
| Schema validator | ✅ | `validate_flight_json.py` |
| Airports | ✅ | No hardcoded coordinates: origin/destination positions derived dynamically from the track's first/last waypoints; ICAO from the API. `airports.py` removed. |
| OpenSky REST preprocessor | ✅ | `opensky_to_flightjson.py`; proven against the **live API** (real flight UAE44 EDDF→OJAI, 357 waypoints) |
| **OpenSky credentials** | ✅ | `credentials.json` present; OAuth2 token fetch verified |
| **Live REST fetch proven** | ✅ | departures→icao24 + `/tracks` fetch worked; output passed the validator + rendered in Blender. (Fair use: only 2 credit-calls used in testing) |
| Trino historical access | ❌ | No research-access application submitted; >30-day history impossible until then |
| `/tracks` 30-day limit handling | 🟡 | Documented + enforced; no automatic fallback strategy for older flights |
| Real demo flight chosen | ✅ | Canonical demo is a **real** saved flight: `preprocess/flight.json` (DLH67K, Frankfurt EDDF → Madrid LEMD, 425 waypoints). Synthetic sample data removed. |
| Speed for REST tracks | 🟡 | Derived from waypoints (tracks lack velocity) — approximate, not source-true |

## 2. Weather — DESCOPED

Weather visualization (ERA5/NetCDF → texture → overlay) is **out of scope** for this
project. The focus is a solid flight visualization. (Left here for the record.)

## 3. Blender visualization

| Item | Status | Notes / gap |
|---|---|---|
| Procedural Earth | ✅ | Reused from HW5 (`ProcEarth`) |
| Static Earth + moving sun (day/night) | ✅ | Geo-node frame-spin removed; sun animated 1→96 |
| Aircraft model imported + scaled | ✅ | Boeing 747-8F GLB, `Aircraft_B747` collection |
| Route curve + markers | ✅ | Great-circle curve, origin/dest emissive markers |
| Aircraft animation along path | ✅ | Path-tangent orientation, baked over frames |
| Chase camera | ✅ | Baked follow cam (`ChaseCam`); `Camera_T3` = overview. **Looks at the plane** with the **horizon leveled to the Earth** (up = radial): width axis parallel to the surface (no banking), pitch follows the aircraft |
| Chase cam clips underground at start/end | ✅ | Terrain-aware clamp: `build_terrain_lookup` indexes the displaced Earth mesh in a KD-tree; each chase-cam keyframe is kept ≥ `up_off` above the ground directly beneath it (and never below the aircraft). Verified above-surface at start/mid/end for altitude exaggeration ×10 **and** ×1 (stress). |
| **Longitude calibration robustness** | 🟡 | `LON_OFFSET=-177.19` hand-calibrated (measured from `earth_uv`) for this Earth texture; will break for a different Earth asset |
| **Altitude exaggeration** | 🟡 | now user-controllable (`altitude_exaggeration`); still a scene-unit offset above the model |
| **Altitude relative to Earth** | ✅ | `project_waypoint` places at `radius = R_base·(1 + alt_m/R_earth·k)` (radius-relative, `alt_frac_per_m = exaggeration/R_earth`); cloud shell uses the same form. Scale-independent, no absolute "next-to-model" offset, consistent with terrain. |
| Aircraft forward-axis assumption | 🟡 | Hard-assumes model nose = +Y (`forward_sign`); manual flip needed for other models |
| Banking / pitch on turns | ❌ | Only yaw+radial up; no roll into turns, no climb/descent pitch from vertrate |
| Motion smoothing | 🟡 | Linear interpolation between waypoints; no easing/curve smoothing |
| Labels / HUD (alt, speed, time, ETA) | ❌ | None |
| Multiple cameras / cinematic shots | 🟡 | Only overview + chase; no route-overview-orbit or cinematic moves |
| Atmosphere glow | ❌ | Not added |
| Lighting/color polish | ❌ | Default EEVEE look; no grading |

## 4. Add-on / UX (Part 2 of the plan)

| Item | Status | Notes / gap |
|---|---|---|
| `flight_importer.py` engine | ✅ | Engine module inside the add-on package, tested live |
| **Add-on packaging** (`bl_info`, register) | ✅ | `blender/flight_viz_addon/` — installable add-on |
| Sidebar panel (N-panel) | ✅ | View3D > Sidebar > **Flight** |
| Operators (Load / Clear) | ✅ | `flightviz.build` + `flightviz.clear` (Load & Build / Clear) |
| File pickers / properties | ✅ | Scene `flightviz` props: JSON path + sync-sun / chase-cam / markers toggles |
| Scene reset / re-run safety | ✅ | `clear_scene()` + Clear operator; Build is idempotent; `_remove` purges orphaned datablocks (no `ChaseCam.001…` pile-up) |
| Chase-cam zoom (lens) control | ✅ | `chase_lens` UI slider (mm) → `Config.chase_lens`; default 20 mm |
| Add-on install packaging | ✅ | `blender/build_addon.sh` → `dist/flight_viz_addon.zip`; README Install & Run steps |
| Frame-range auto-setup | 🟡 | Length set by the **speed** control (`base_frames/speed`); no derive-from-real-duration option |

## 5. Rendering & final deliverable (Part 3)

| Item | Status | Notes / gap |
|---|---|---|
| Thumbnail test renders | ✅ | Overview + chase verified |
| Render Video button | ✅ | `flightviz.render`: pick camera + resolution (540/720/1080p), writes `flight_<cam>_<datetime>.mp4` (H.264) to `//renders`; handles Blender 5.x `media_type` |
| Final animation render settings | 🟡 | Button covers camera/resolution/output; final samples/grade for the deliverable not locked |
| Final rendered video | 🟡 | Sample MP4s produced via the button; final polished deliverable not yet made |
| Render engine decision | 🟡 | EEVEE in use; Cycles vs EEVEE not decided for final quality |

## 6. Engineering / project hygiene

| Item | Status | Notes / gap |
|---|---|---|
| `requirements.txt` / env pinning | ❌ | Deps (`requests`, `numpy`, future `xarray`/`Pillow`) not pinned in a file |
| Automated tests | 🟡 | Manual checks only; no `pytest` suite or CI |
| opensky-api client install | 🟡 | Used via `sys.path` injection, not `pip install -e` |
| Git commit of new work | ✅ | All work committed on `main` (local only, never pushed); `flight_visualization.blend` tracked |
| `.blend` asset paths | 🟡 | Aircraft GLB imported into session; relies on local absolute paths |
| Documentation of design decisions | 🟡 | README + preprocess/README exist; no consolidated design doc |

---

## Highest-priority next steps (suggested order)

*(Weather is descoped — see §2.)*

1. **Cinematic polish**: turn banking + climb/descent pitch, lighting/color grade, atmosphere glow.
2. **HUD / labels**: altitude, speed, time, ETA overlay.
3. **Final render**: lock samples/engine/grade and produce the polished deliverable video (Render Video button already handles camera/resolution/output).
4. **Robustness**: expose `LON_OFFSET` + model forward-axis as user settings; optional derive-frame-range-from-real-duration.
5. **Hygiene**: `requirements.txt` pinning; consolidated design doc.
