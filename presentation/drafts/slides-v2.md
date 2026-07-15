# Historical Flight & Weather Visualization in Blender — Pitch Deck (v2)

Source canvas: `slides-v2.excalidraw` (each frame = one slide)

---

## Slide 1 — Title

**Historical Flight & Weather Visualization in Blender**
A data-driven cinematic Blender plugin

Course: *Developing Blender Plugins for Digital Art and Content Creation*

---

## Slide 2 — Motivation + Idea

**Motivation**
- Commercial flights are an everyday experience, yet the *route, weather, and atmosphere* of a specific flight are invisible to passengers afterward.
- Existing flight-tracking tools (Flightradar24, FlightAware) are 2D dashboards, not cinematic.
- I already built an Earth shader (HW5) and external-data pipelines (HW2/HW4/HW6); a flight visualization is a natural capstone.

**Idea**
A Blender add-on that takes a real historical commercial flight + historical weather data and produces a cinematic 3D scene:
- Procedural Earth + atmosphere
- Real waypoint-driven aircraft animation
- Composite weather visualization
- Chase camera + cinematic shots
- Final rendered video as the deliverable

> Not a simulator. A *data-driven visual story* of one specific flight.

---

## Slide 3 — Similar Existing Plugins / Tools / Literature

**Blender ecosystem**
- **BlenderGIS** — GIS / DEM / OSM imports (geography, no flights/weather)
- **Blosm (Blender-OSM)** — OSM, terrain, GPX import
- **BlenderNC** — NetCDF / GRIB / Zarr scientific viz (no aviation)
- **Tacview Flight Path Importer** — 3D paths, but from Tacview CSV (military/sim, not real commercial)
- **GPX-Importer** — generic GPS routes
- **Motion Path Pro** — path debugging utility
- **Maps Models Importer** — Google Earth scrapes (legally fragile)

**Outside Blender**
- Flightradar24 / FlightAware — 2D web maps
- CesiumJS / Google Earth Studio — globe viz, not Blender-native

**Gap I'm filling**
No Blender plugin combines *real historical commercial flight data* + *historical reanalysis weather* + *cinematic render workflow* in one tool.

---

## Slide 4 — Concrete Example & End-to-End Walkthrough

**Worked example: LH401, JFK → FRA, 2024-03-21**

1. *External Python preprocessor*
   - Pulls flight track from OpenSky Trino → `flight.json` (waypoints: lat, lon, alt, speed, heading, t)
   - Pulls ERA5 weather slice for the route bbox + time → `weather.png` composite (cloud cover + precip)
2. *Open Blender → "Flight Viz" sidebar panel*
   - **Load Data** → JSON + texture imported
   - **Generate Scene** → Earth + atmosphere + route curve + airport markers + animated aircraft + chase camera
3. *Adjust* — choose camera, lighting, weather opacity
4. *Render* → cinematic MP4

**Target groups**
- Aviation enthusiasts / hobbyists
- Educators (climate, geography, aviation)
- Documentary / travel-vlog creators retracing a trip
- Data journalists narrating a notable historical flight (diversion, storm rerouting, etc.)

---

## Slide 5 — Feasibility

**Why it is realistic for the course timebox**

| Feature                                 | Reuses prior assignment        |
|-----------------------------------------|--------------------------------|
| UI panel + operators                    | HW3 (UI), HW2 (operators)      |
| External data → animated geometry       | HW4 (audio→mesh)               |
| Earth, atmosphere, procedural materials | HW5 (Earth shader / geo nodes) |
| Optional live data link                 | HW6 (sockets)                  |

**De-risking choices**
- *Scientific NetCDF stays out of Blender* — handled in an external Python preprocessing step, Blender only consumes JSON + PNG
- *Bundle one sample flight* so the demo always works even without API credits
- *Aircraft model imported, not modeled from scratch*
- *Spherical lat/lon → 3D conversion* is a closed-form formula (no GIS dependency)

**Tech stack**: Blender 4.x add-on (`bpy`), external Python (`requests`, `xarray`, `numpy`, `Pillow`), data via OpenSky Trino + ERA5.

---

## Slide 6 — Roadmap & Milestones

**Three parts (not strict weeks)**

```
Part 1  Research & Feasibility       ──▶  M1: pipeline POC
Part 2  Core Functionality           ──▶  M2: working MVP demo
Part 3  Polish & Finalization        ──▶  M3: rendered final video
```

**M1 — Pipeline POC**
- OpenSky Trino access confirmed, demo flight chosen
- ERA5 sample fetched → composite texture rendered
- Aircraft model imported & scriptable

**M2 — Working MVP (main milestone)**
- Plugin UI live, loads JSON+PNG
- Earth + atmosphere + route + animated aircraft + chase cam
- One weather variable visible in scene

**M3 — Final video**
- Smooth motion + lighting + labels + multiple cameras
- Fallback sample data, render of the demo flight, written documentation

---

## Slide 7 — MVP vs Stretch Goals

**MVP (must work for grading)**
- Bundled sample flight (1 historical commercial flight)
- Procedural Earth + atmosphere
- Route curve + origin/destination markers
- Aircraft animated along waypoints with heading rotation
- Chase camera as default
- One weather layer (cloud cover) as a composite texture
- Final rendered video

**Stretch (if time allows)**
- Live OpenSky/Trino fetch from preprocessor (parameterized by flight number + date)
- Multi-variable weather: clouds + precipitation + storms + fog
- Day/night terminator transition along long flights
- Multiple cameras: route overview, cinematic, optional cabin window
- On-screen HUD labels (altitude, speed, ETA, timestamp)
- Seat-side recommendation (sun position vs cloud cover vs view direction)

---

## Slide 8 — Uncertainties & Open Decisions

**Flight data source**
- A. **OpenSky Trino** — rich historical, but auth + credits required *(preferred)*
- B. OpenSky REST `/tracks` — only last 30 days, marked experimental
- C. Pre-recorded static sample only — most reliable, least flexible

**Weather data source**
- A. **ERA5 NetCDF (Copernicus)** — global, hourly, since 1940, but heavy *(preferred)*
- B. Open-Meteo Historical API — JSON, simpler, fewer variables
- C. NOAA METAR — aviation-relevant but station-based, sparse

**Weather rendering technique**
- A. **2D composite texture wrapped on a cloud-shell sphere** *(preferred for clarity)*
- B. Local sky/atmosphere shader driven by sampled values along route
- C. Volumetric particles (most expensive, most cinematic)

**Earth detail**
- A. Pure procedural (HW5 reuse)
- B. NASA Blue Marble texture
- C. Hybrid: Blue Marble albedo + procedural atmosphere/clouds *(preferred)*

**Aircraft model**
- Free Sketchfab / BlenderKit asset vs custom low-poly — *to confirm with course instructor on licensing*

---

## Slide 9 — Thank You

**Questions / discussion**

References: README.md (full data sources & related plugins)
