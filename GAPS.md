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

## 2. Weather (entire branch untouched)

| Item | Status | Notes / gap |
|---|---|---|
| ERA5 / NetCDF acquisition | ❌ | No Copernicus account, no download script |
| NetCDF → composite texture | ❌ | No `weather.png` producer (`xarray`/`numpy`/`Pillow`) |
| Weather schema / contract | ❌ | Not defined (only flight schema exists) |
| Weather rendering in Blender | ❌ | No cloud shell, atmosphere driver, or overlay implemented |
| Weather-along-route sampling | ❌ | No mapping of weather values to waypoints |

## 3. Blender visualization

| Item | Status | Notes / gap |
|---|---|---|
| Procedural Earth | ✅ | Reused from HW5 (`ProcEarth`) |
| Static Earth + moving sun (day/night) | ✅ | Geo-node frame-spin removed; sun animated 1→96 |
| Aircraft model imported + scaled | ✅ | Boeing 747-8F GLB, `Aircraft_B747` collection |
| Route curve + markers | ✅ | Great-circle curve, origin/dest emissive markers |
| Aircraft animation along path | ✅ | Path-tangent orientation, baked over frames |
| Chase camera | ✅ | Baked follow cam (`ChaseCam`); `Camera_T3` = overview |
| **Longitude calibration robustness** | 🟡 | `LON_OFFSET=-168` hand-calibrated for this Earth texture; will break for a different Earth asset |
| **Altitude exaggeration** | 🟡 | ×33.8 is a fixed heuristic; not user-controllable |
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
| `flight_importer.py` engine | ✅ | Callable module, tested live |
| **Add-on packaging** (`bl_info`, register) | ❌ | Not an installable add-on yet |
| Sidebar panel (N-panel) | ❌ | No UI |
| Operators (Load Data / Generate / Reset) | ❌ | None; everything is script-invoked |
| File pickers / properties | ❌ | Paths + params are hard-coded constants |
| Scene reset / re-run safety | 🟡 | Importer removes its own objects, but no full "reset scene" operator |
| Frame-range auto-setup | 🟡 | Uses existing 1–96; no derive-from-flight-duration option |

## 5. Rendering & final deliverable (Part 3)

| Item | Status | Notes / gap |
|---|---|---|
| Thumbnail test renders | ✅ | Overview + chase verified |
| Final animation render settings | ❌ | No resolution/samples/output config for the deliverable |
| Final rendered video | ❌ | Not produced |
| Render engine decision | 🟡 | EEVEE in use; Cycles vs EEVEE not decided for final quality |

## 6. Engineering / project hygiene

| Item | Status | Notes / gap |
|---|---|---|
| `requirements.txt` / env pinning | ❌ | Deps (`requests`, `numpy`, future `xarray`/`Pillow`) not pinned in a file |
| Automated tests | 🟡 | Manual checks only; no `pytest` suite or CI |
| opensky-api client install | 🟡 | Used via `sys.path` injection, not `pip install -e` |
| Git commit of new work | ❌ | `preprocess/`, `blender/`, updated `Untitled.blend` untracked/uncommitted |
| `.blend` asset paths | 🟡 | Aircraft GLB imported into session; relies on local absolute paths |
| Documentation of design decisions | 🟡 | README + preprocess/README exist; no consolidated design doc |

---

## Highest-priority next steps (suggested order)

1. ~~Register OpenSky OAuth2 client and prove the preprocessor live~~ ✅ done.
2. **Package the add-on** (`bl_info`, panel, Load/Generate/Reset operators) wrapping `flight_importer.py` — the biggest functional gap for Part 2.
3. **Weather MVP**: ERA5 cloud-cover slice → `weather.png` → simple cloud-shell sphere in Blender.
4. **Final render**: configure output + produce the deliverable video.
5. Robustness: expose `LON_OFFSET`, altitude exaggeration, and model forward-axis as user settings; add turn banking; expand `airports.py` to full OurAirports.
6. **Pick the final showcase flight** (recent, ≤30 days, good ADS-B coverage, clean route) and bundle its `flight.json`.
