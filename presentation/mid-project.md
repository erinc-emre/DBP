# Mid-Project Presentation — Speaker Notes

Source canvas: `mid-project.excalidraw` (each frame = one slide).
Target: **6–9 min talk + 4–7 min Q&A** (≤ 12–13 min total).

---

## 1 — Title
Historical Flight Visualization in Blender — mid-project check-in.

## 2 — Idea Recap (~1 min)
- A real historical commercial flight, visualized in Blender from real data.
- OpenSky flight data → aircraft animated on a textured Earth.
- Cinematic and data-driven, **not** a simulator. Deliverable: a rendered video.

## 3 — Current State of the Prototype (~2 min, show the renders)
- One-click add-on: OpenSky → `flight.json` → full scene.
- Demo flight: **Lufthansa DLH67K, Frankfurt → Madrid** (425 waypoints).
- Earth: **16K day / 13.5K night** + real elevation, clouds, normal/specular (Cubic filtering).
- Great-circle route, animated 747, chase camera.
- **UI controls:** plane / altitude / terrain scale + flight-speed selector.
- Sun synced to the flight's real UTC time (this flight is a night departure).
- *Renders on slide: overview · chase cam · day side.*

## 4 — Pipeline (Sequence) (~1 min)
- How the pieces talk: **User → Preprocessor → OpenSky API → Blender Add-on**.
- Fetch track → `flight.json` (offline-reusable) → Load & Build → scene → render → video.
- Heavy data stays outside Blender; the add-on only consumes a clean file.

## 5 — Remaining to Implement (~1.5 min)
- **Aircraft motion** — path is smoothed, but turns still snap; add eased interpolation + gentle banking.
- **Weather layer** — ERA5 reanalysis → composite texture (same external-preprocess
  pattern), mapped onto a cloud/atmosphere shell.
- Final render settings + the deliverable video.
- Polish: lighting, camera movement, optional HUD labels.

## 6 — Updated Roadmap (~1 min)
- **Done:** data pipeline, add-on + UI (scale & speed controls), 16K/13.5K Earth + elevation + clouds, aircraft + route + chase cam, sun-time sync.
- **Until final:** smooth aircraft motion (banking), weather MVP, weather in-scene, final render, docs.

## 7 — MVP vs Stretch (~1 min)
- **MVP:** bundled real flight, Earth + route + aircraft, chase cam, one weather layer, rendered video.
- **Stretch:** multi-variable weather, HUD labels, multiple cameras, day/night terminator, seat-side recommendation.

## 8 — Uncertainties / Open Decisions (~1 min — invite input)
- **Vertical exaggeration for the final render:** true-to-scale (plane invisible from
  orbit) vs exaggerated for visibility — now a configurable knob (currently plane ×100,
  altitude ×10). How much for the deliverable?
- Weather source: **ERA5** (rich, heavy) vs Open-Meteo (simple JSON) — leaning ERA5.
- Weather look: **2D texture on cloud shell** vs volumetric vs sky shader — leaning texture shell.

## 9 — Thank You / Q&A
