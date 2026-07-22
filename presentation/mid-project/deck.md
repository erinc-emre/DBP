---
theme: default
layout: cover
class: text-center
fonts:
  sans: Inter
---

# Historical Flight Visualization in Blender

Mid-project check-in

<div class="mt-10 opacity-70 text-base">Erinc Celikten · Practical Course: Developing Blender Plugins</div>

---

# Idea Recap

- A **real historical commercial flight**, visualized in Blender from real data
- OpenSky flight data → aircraft animated on a textured Earth
- **Cinematic and data-driven, not a simulator**
- Deliverable: a rendered video

---

# Current State of the Prototype

<div class="grid grid-cols-3 gap-2 mt-2">
  <img src="/render1.jpeg" class="rounded shadow"/>
  <img src="/render2.jpeg" class="rounded shadow"/>
  <img src="/render3.jpeg" class="rounded shadow"/>
</div>

<div class="text-sm mt-3">

- One-click add-on: OpenSky → `flight.json` → full scene
- Demo flight: **Lufthansa DLH67K, Frankfurt → Madrid** (425 waypoints)
- Earth: **16K day / 13.5K night** + real elevation, clouds, normal/specular
- Great-circle route · animated 747 · chase camera · UI scale & speed controls
- Sun synced to the flight's real UTC time (a night departure)

</div>

---

# Pipeline

```mermaid {scale: 0.6}
sequenceDiagram
    actor U as User
    participant P as Preprocessor
    participant O as OpenSky API
    participant B as Blender Add-on
    U->>P: flight number + date
    P->>O: authenticate + fetch track
    O-->>P: waypoints (lat, lon, alt, time)
    P-->>U: flight.json
    U->>B: Load & Build
    B-->>U: Earth + route + aircraft + sun + camera
    U->>B: Render
    B-->>U: flight video
```

<div class="text-sm mt-4 opacity-80">Heavy data stays outside Blender; the add-on only consumes a clean file.</div>

---

# Remaining to Implement

- **Aircraft motion** — path is smoothed, but turns still snap; add eased
  interpolation + gentle banking
- **Weather layer** — ERA5 reanalysis → composite texture, mapped onto a
  cloud/atmosphere shell
- Final render settings + the deliverable video
- Polish: lighting, camera movement, optional HUD labels

---

# Updated Roadmap

<div class="grid grid-cols-2 gap-8 mt-4">

<div>

## Done ✅
- Data pipeline
- Add-on + UI (scale & speed)
- 16K / 13.5K Earth + elevation + clouds
- Aircraft + route + chase cam
- Sun-time sync

</div>

<div>

## Until final 🔭
- Smooth aircraft motion (banking)
- Weather MVP + in-scene
- Final render
- Docs

</div>

</div>

---

# MVP vs Stretch

<div class="grid grid-cols-2 gap-8 mt-4">

<div>

## MVP
- Bundled real flight
- Earth + route + aircraft
- Chase camera
- One weather layer
- Rendered video

</div>

<div>

## Stretch
- Multi-variable weather
- HUD labels
- Multiple cameras
- Day/night terminator
- Seat-side recommendation

</div>

</div>

---

# Uncertainties / Open Decisions

- **Vertical exaggeration for the final render** — true-to-scale (plane invisible
  from orbit) vs exaggerated for visibility. Now a configurable knob
  (currently plane ×100, altitude ×10). How much for the deliverable?
- **Weather source** — ERA5 (rich, heavy) vs Open-Meteo (simple JSON) — leaning ERA5
- **Weather look** — 2D texture on a cloud shell vs volumetric vs sky shader —
  leaning texture shell

---
layout: center
class: text-center
---

# Thank you

<div class="mt-6 text-lg opacity-80">Questions &amp; feedback welcome</div>
