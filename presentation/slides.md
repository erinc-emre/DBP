---
theme: seriph
title: Historical Flight Visualization in Blender
info: Final project presentation — a data-driven Blender add-on
class: text-center
transition: slide-left
mdc: true
---

# Historical Flight Visualization in Blender

A one-click Blender add-on that turns a **real historical flight** into a
cinematic fly-along on a textured 3D Earth

<div class="pt-8 opacity-80">
Course: <em>Developing Blender Plugins for Digital Art and Content Creation</em><br>
&lt;Your Name&gt; · Final Presentation
</div>

<!--
Speaker note: from a flight number + date to a rendered video, entirely inside Blender.
-->

---
layout: image-right
image: ./assets/hero.png
---

# Idea recap

**Take one real commercial flight → tell its visual story.**

- External Python **preprocessor** pulls the real track from **OpenSky** and
  writes a clean `flight.json`.
- A Blender **add-on** consumes that JSON and builds the whole scene in one click:
  Earth, route, animated aircraft, sun, chase camera — then renders an MP4.
- **Offline by design:** once fetched, a flight replays with no network or keys.

<br>

> Not a simulator — a **data-driven visual story** of one specific flight.

Demo flight: **Lufthansa DLH67K, Frankfurt → Madrid.**

---
layout: image
image: ./assets/final_look.png
backgroundSize: contain
---

# Final prototype

<div class="abs-bl m-6 p-3 bg-black/50 rounded text-sm">
Chase cam over the night side · HUD (callsign / alt / speed / UTC / elapsed) ·
atmosphere limb · color grade + bloom
</div>

---

# Final prototype — what shipped

<div grid="~ cols-2 gap-6">
<div>

**Scene & data**
- Real OpenSky track → validated `flight.json`
- Procedural Earth (16K day / night / normal / spec), real terrain, clouds
- Sun synced to the flight's **real UTC** time
- **Airport model** placed at both ends

**Camera & motion**
- Chase cam: looks at the plane, **level horizon**, terrain-aware (never underground)
- **Constant-speed** glide; **banks into turns**
- On-screen **HUD**

</div>
<div>

**Look & UX**
- Night **fill light**, **atmosphere glow**, AgX **grade + bloom**
- Sidebar panel: fetch, scale, animation, calibration, render
- **Fetch & Build** from the UI; **Render Video** button

<img src="./assets/night.png" class="rounded mt-2 w-full"/>

</div>
</div>

---

# Architecture — two clean halves

```mermaid {scale: 0.8}
flowchart LR
  O[OpenSky REST] --> P[Preprocessor<br/>fetch · clean · derive]
  P --> J[flight.json<br/>documented contract]
  J --> A[Blender add-on<br/>visualise only]
  M[Boeing 747-8F] --> A
  G[airport.glb] --> A
  A --> R[Rendered MP4]
```

- **Outside Blender:** all network / OAuth2 / data wrangling (`requests`, OpenSky client).
- **Inside Blender:** only consumes `flight.json` — no network, no credentials.
- They meet at a **documented JSON schema** enforced by a stdlib validator, so the
  two halves evolve independently.

---

# Challenge 1 — smooth, faithful motion from messy data

**The problem.** Real ADS-B tracks are sampled *very* unevenly — one fetched
flight had **34 gaps up to ~7 min**, and even **frozen-then-jumping** positions.
Naive time-based playback **surged and stalled**, and a big gap's straight-line
interpolation cut a **chord ~160 km through the Earth**.

<div grid="~ cols-2 gap-4" class="mt-4">
<div>

**The fix**
- Resample to a uniform time grid, then to **constant arc-length** → steady glide
- Interpolate **along the sphere** (normalized lerp), not a chord
- Smoothing **preserves each point's radius** (no sag inside the Earth)
- Altitude referenced to the **local terrain** beneath each point

</div>
<div>

**Result (per-frame step)**

| metric | before | after |
|---|--:|--:|
| peak / mean | 17.6× | **1.0×** |
| frame jerk | 63% | **21%→0** |
| below surface | yes | **never** |

</div>
</div>

---

# Challenge 2 — getting the data & automating it

**OpenSky has no "flight number" key.** The API is keyed on the aircraft
transponder **`icao24`**, not "LH67K".

- Resolve **callsign → `icao24`** via the departures endpoint, then fetch the track.
- Auth moved to **OAuth2**; REST tracks only cover the **last ~30 days** (guarded early).

**Automated from the UI.** A **Fetch from OpenSky** panel runs the preprocessor as a
**subprocess** — keeping `requests` / OAuth2 *out* of Blender — then builds the scene.

- Gotcha solved: Blender's GUI has a minimal `PATH`, so the default `python3` lacked
  `requests` → the add-on now **auto-discovers** a Python that has it.

<br>

> Enter a callsign + date → **Fetch & Build** → a rendered flight, no command line.

---

# Roadmap — implemented vs. future work

<div grid="~ cols-2 gap-6">
<div>

## ✅ Implemented
- OpenSky preprocessor + JSON schema + validator + tests
- Add-on: panel, operators, packaging, **in-UI fetch**
- Procedural Earth, real terrain, clouds, time-synced sun
- Constant-speed motion, **banking**, path always above terrain
- Chase camera (level, terrain-aware, zoom)
- **HUD**, airports at both ends
- Night fill light, **atmosphere glow**, **color grade + bloom**
- Render-to-MP4 button

</div>
<div>

## 🔭 Future work
- **Weather layer** (ERA5 → composite texture / cloud shell) — descoped
- **Historic flights > 30 days** — OpenSky **Trino** research access
- Richer cinematics (multi-camera, orbit reveals)
- Auto-fill HUD/airport metadata from flight meta
- Source-true speed (REST tracks lack velocity)

</div>
</div>

---
layout: center
class: text-center
---

# Thank you

A real flight → a cinematic render, one click inside Blender.

<div class="opacity-80 pt-4">
Demo video: <code>renders/flight_chase_*.mp4</code> · Code & docs: <code>README.md</code>, <code>DESIGN.md</code>
</div>

<div class="pt-6 text-sm opacity-70">Questions &amp; discussion</div>
