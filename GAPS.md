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
| `/tracks` 30-day limit handling | ✅ | `within_tracks_window()` fails early with a clear message before spending API credits; older flights need Trino (documented) |
| Real demo flight chosen | ✅ | Canonical demo is a **real** saved flight: `preprocess/flight.json` (DLH67K, Frankfurt EDDF → Madrid LEMD, 425 waypoints). Synthetic sample data removed. |
| Speed for REST tracks | ✅ (accepted) | REST tracks carry no velocity, so speed is derived from consecutive waypoints — the only option for this source; documented in DESIGN.md |

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
| Airport model at endpoints | ✅ | `assets/models/airport.glb` placed at departure & arrival (`place_airports`): seated on the terrain, up = radial, runway aligned to the flight direction; size/toggle/path in UI |
| Aircraft animation along path | ✅ | Path-tangent orientation, baked over frames |
| Chase camera (only camera) | ✅ | Baked follow cam (`ChaseCam`) is the **sole** camera. **Looks at the plane** with the **horizon leveled to the Earth** (up = radial): width axis parallel to the surface (no banking), pitch follows the aircraft |
| Chase cam clips underground at start/end | ✅ | Terrain-aware clamp: `build_terrain_lookup` indexes the displaced Earth mesh in a KD-tree; each chase-cam keyframe is kept ≥ `up_off` above the ground directly beneath it (and never below the aircraft). Verified above-surface at start/mid/end for altitude exaggeration ×10 **and** ×1 (stress). |
| **Longitude calibration robustness** | ✅ | Now a **UI setting** ("Longitude offset"); default -177.19 for this asset, adjustable for any other Earth texture without code edits |
| **Altitude exaggeration** | ✅ | Radius-relative (`radius = R_base·(1 + alt_m/R_earth·k)`) + user-controllable; no scene-unit offset |
| **Altitude relative to Earth** | ✅ | `project_waypoint` references altitude to the **local ground** (`radius = ground_r(dir) + alt_m·k`, via the terrain KD-tree), so air points are always above the closest surface — never inside terrain, whatever the sea-level datum. Sphere-preserving smoothing + normalized-lerp interpolation stop big coverage gaps from cutting a chord through the Earth. |
| Aircraft forward-axis assumption | ✅ | "Model nose axis" **UI enum** (+Y / -Y) → `forward_sign`; no code edit for other models |
| Banking / pitch on turns | ✅ | Nose follows the 3D path (pitch = climb/descent); `_orient` rolls the aircraft into turns by the tangent-plane heading change (`bank_gain`, clamped to `max_bank_deg`) |
| Motion smoothing | ✅ | Path resampled to a uniform time grid + smoothed (`resample_uniform`), then **reparametrised to constant arc-length** (`reparametrize_arc`) so the aircraft glides at a **steady speed** — no stalls/surges even where the raw track froze then jumped (min/max step ≈ mean). HUD keeps the true clock via `atime` |
| Labels / HUD (alt, speed, time, ETA) | ✅ | `FlightHUD` Font object parented to the chase cam (top-left overlay); a `frame_change_post` handler swaps per-frame text (callsign, altitude, speed km/h, UTC, elapsed/total) from values stored on the scene — works during renders too |
| Multiple cameras / cinematic shots | ✅ (by choice) | Deliberately **chase-cam only** — overview camera + orbit removed to keep it simple |
| Atmosphere glow | ✅ | `build_atmosphere`: a slightly larger sphere with fresnel-driven blue emission (transparent face-on) → glowing limb halo |
| Night-side subject visibility | ✅ | Chase-cam 'headlight' sun (`build_subject_light`) keeps the plane & airport lit on the night side (UI-tunable) |
| Lighting/color polish | ✅ | `apply_grade`: AgX "Medium High Contrast" view look + a compositor **Bloom** glare (Blender 5.x node-group compositor) on the bright areas |

## 4. Add-on / UX (Part 2 of the plan)

| Item | Status | Notes / gap |
|---|---|---|
| `flight_importer.py` engine | ✅ | Engine module inside the add-on package, tested live |
| **Add-on packaging** (`bl_info`, register) | ✅ | `blender/flight_viz_addon/` — installable add-on |
| Sidebar panel (N-panel) | ✅ | View3D > Sidebar > **Flight** |
| Operators (Load / Clear) | ✅ | `flightviz.build` + `flightviz.clear` (Load & Build / Clear) |
| In-UI flight fetch | ✅ | `flightviz.fetch`: enter callsign+dep-ICAO (or icao24) + date → runs the preprocessor as a subprocess → writes `flight.json` → builds. Keeps `requests`/OAuth2 out of Blender |
| File pickers / properties | ✅ | Scene `flightviz` props: JSON path + sync-sun / chase-cam / markers toggles |
| Scene reset / re-run safety | ✅ | `clear_scene()` + Clear operator; Build is idempotent; `_remove` purges orphaned datablocks (no `ChaseCam.001…` pile-up) |
| Chase-cam zoom (lens) control | ✅ | `chase_lens` UI slider (mm) → `Config.chase_lens`; default 20 mm |
| Add-on install packaging | ✅ | `blender/build_addon.sh` → `dist/flight_viz_addon.zip`; README Install & Run steps |
| Frame-range auto-setup | ✅ | Length modes: fixed (`base_frames/speed`) **or** scale-to-real-duration (`time_compression`) |

## 5. Rendering & final deliverable (Part 3)

| Item | Status | Notes / gap |
|---|---|---|
| Thumbnail test renders | ✅ | Overview + chase verified |
| Render Video button | ✅ | `flightviz.render`: pick camera + resolution (540/720/1080p), writes `flight_<cam>_<datetime>.mp4` (H.264) to `//renders`; handles Blender 5.x `media_type` |
| Final animation render settings | ✅ | Render Video button (camera/resolution/output) + EEVEE samples bumped for final; H.264 MP4 |
| Final rendered video | ✅ | 1080p/24fps chase deliverable rendered to `renders/` (git-ignored) |
| Render engine decision | ✅ | **EEVEE** chosen (fast iteration, good enough look); rationale in DESIGN.md |

## 6. Engineering / project hygiene

| Item | Status | Notes / gap |
|---|---|---|
| `requirements.txt` / env pinning | ✅ | `requirements.txt` pins `requests` + `pytest`; notes on the vendored OpenSky client |
| Automated tests | ✅ | `preprocess/tests/test_preprocess.py` — 8 pytest tests (pure helpers + validator) |
| opensky-api client install | ✅ | `requirements.txt` + defensive import; vendoring documented (README/DESIGN) |
| Git commit of new work | ✅ | All work committed on `main` (local only, never pushed); `flight_visualization.blend` tracked |
| `.blend` asset paths | ✅ | Texture paths made **relative** (`//textures/…`, tracked in-repo); aircraft embedded |
| Documentation of design decisions | ✅ | `DESIGN.md` — consolidated design-decisions doc |

---

## Highest-priority next steps (suggested order)

*(Weather is descoped — see §2. All former 🟡 partials are now complete.)*

Remaining ❌:

1. **Trino historical access** — external application; only needed for flights >30 days old.

Everything else (banking, HUD, airports, night light, atmosphere, color grade, constant-speed motion) is done. Optional next: render the final deliverable video; refine the final presentation deck in `presentation/final/slides.md`.
