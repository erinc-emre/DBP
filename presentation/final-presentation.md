---
theme: default
layout: cover
class: text-center
---

# Historical Flight Visualization in Blender

Turn a **real airline flight** into an animated fly-along on a textured 3D Earth

<div class="mt-10 opacity-80 text-lg">

External OpenSky preprocessor → `flight.json` → one-click Blender add-on

</div>

<div class="abs-br m-6 opacity-60 text-sm">DBP Course · Final Presentation</div>

<!--
Final presentation. Fill in your name/date. The project: a real historical commercial flight, visualized end to end.
-->

---

# The Idea

Take a **real historical airline flight** and replay it as a cinematic
fly-along on a photoreal 3D Earth.

<div class="grid grid-cols-2 gap-8 mt-6">

<div>

**Two clean halves**
- **Outside Blender** — a Python tool fetches the flight from the **OpenSky Network**, cleans it, and writes a small **`flight.json`**
- **Inside Blender** — a **one-click add-on** consumes that JSON and builds the whole scene

</div>

<div>

**Why split?**
- Heavy deps (HTTP, OAuth2) stay out of Blender
- The two sides meet at a **documented JSON contract** → they evolve independently
- Once fetched, a flight is **offline & reproducible**

</div>

</div>

<!--
Recap the concept and the architecture in one line: preprocessor + add-on, meeting at flight.json.
-->

---
layout: image
image: /hero_cruise.png
class: text-white
---

# Final Prototype

Chase camera over night-lit Europe — live HUD, route trail, atmosphere glow.

<!--
The money shot. DLH67K Frankfurt to Madrid at cruise. Point out: HUD (callsign/alt/speed/UTC/elapsed), the glowing route, the blue atmosphere limb, color grade + bloom.
-->

---

# What's in the Scene

<div class="grid grid-cols-3 gap-3 mt-4">
  <div><img src="/takeoff.png" class="rounded shadow"/><div class="text-center text-sm mt-1 opacity-80">Airport at departure</div></div>
  <div><img src="/turn.png" class="rounded shadow"/><div class="text-center text-sm mt-1 opacity-80">Banks into turns</div></div>
  <div><img src="/descent.png" class="rounded shadow"/><div class="text-center text-sm mt-1 opacity-80">Descent into arrival</div></div>
</div>

<div class="text-sm mt-4 opacity-85">

Procedural Earth (16K day / night / relief) · airports placed at both ends ·
sun synced to the flight's **real UTC time** · constant-speed aircraft with
pitch & bank · HUD · night fill light · atmosphere · color grade + bloom ·
**Render Video** button → MP4

</div>

<!--
Feature montage. Everything is a toggle in the sidebar. Sun position from real timestamps, not a spinning Earth.
-->

---

# Architecture

```mermaid {scale: 0.5}
flowchart LR
    A[Flight ID<br/>+ date] --> B[OpenSky<br/>Preprocessor]
    B --> C[(flight.json<br/>+ validator)]
    C --> D[Blender<br/>Add-on]
    D --> E[Scene → MP4<br/>route · aircraft · HUD]
```

<div class="text-sm mt-6 opacity-85">

The **`flight.json` contract** is the seam — a Markdown schema + a stdlib validator.
Pass the validator → Blender is happy, and the two halves evolve independently.
Fetch can even run **from the add-on UI** (it shells out to the preprocessor).

</div>

<!--
One diagram. Emphasize the JSON contract as the decoupling seam, and that fetch is now automatable from the UI. Preprocessor also ingests the aircraft + airport models on the Blender side.
-->

---

# Challenge: smooth flight from messy data

Real ADS-B tracks are **ugly**: wildly uneven sampling, multi-minute coverage
gaps, even frozen-then-jumping positions.

<div class="grid grid-cols-2 gap-6 mt-2 text-sm">

<div>

**Symptoms**
- Aircraft **surged and stalled** (time-based playback)
- A transatlantic gap of **2608 km** made the path dive **~160 km inside the Earth** (a straight chord through the sphere)

</div>

<div>

**Fixes**
- Resample to a uniform grid, then **constant arc-length** → steady on-screen speed
- Interpolate **along the sphere** (normalized lerp), radius-preserving smoothing
- Altitude referenced to the **local ground** (terrain KD-tree)

</div>

</div>

<div class="mt-3 text-sm">

**Result** — peak step / mean **17.6× → ~1.0×**, jerk **63% → 21%**, and the flight is **always above the surface**.

</div>

<!--
This is the most important implementation story. Naive time-parametrization fails on real data. The 2608km gap diving into the Earth is a great concrete example. Metrics show the improvement.
-->

---

# Challenge: getting the data out of OpenSky

<div class="grid grid-cols-2 gap-6 mt-2 text-sm">

<div>

**The API doesn't think in "flights"**
- No "LH401" key — it's keyed on the **transponder `icao24`**
- So: resolve **callsign → `icao24`** via the departures endpoint, *then* pull the track
- Auth had to move to **OAuth2** (client credentials)
- REST `/tracks` only serves the **last ~30 days**

</div>

<div>

**How we handled it**
- Callsign + departure ICAO **or** a direct `icao24`
- Fail **early & clearly** if the date is out of the 30-day window (before spending API credits)
- Speed is **derived** from waypoints (tracks carry no velocity)
- Vendored client kept **out of Blender**; the add-on auto-finds a Python with `requests`

</div>

</div>

<!--
Second deep-dive: the data-access reality. icao24 keying is the surprising bit. OAuth2 + 30-day window. Practical guards.
-->

---

# Roadmap

<div class="grid grid-cols-2 gap-8 mt-4">

<div>

## Implemented ✅
- OpenSky pipeline + JSON contract + validator
- One-click add-on (+ **fetch from the UI**)
- Constant-speed, surface-relative motion
- Chase camera (level horizon, terrain-safe)
- Pitch **&** bank into turns
- Airports at both ends
- HUD (callsign / alt / speed / UTC / elapsed)
- Night fill light · atmosphere · color grade + bloom
- Render-to-MP4 · tests · packaging · docs

</div>

<div>

## Future work 🔭
- **Weather layer** (ERA5 → texture overlay) — *descoped*
- **Historic flights > 30 days** — needs OpenSky **Trino** research access
- Richer cinematics (multi-cam, motion blur)
- Higher-res / UDIM Earth for close-ups

</div>

</div>

<!--
Be honest: most of the plan is done; weather was deliberately descoped to keep a solid flight visualization; historic access is an external dependency.
-->

---
layout: center
class: text-center
---

# Thank you

A real airline flight → a smooth, cinematic fly-along on a 3D Earth,
built by a **one-click Blender add-on**.

<div class="grid grid-cols-2 gap-8 mt-6 text-sm opacity-85">

<div>

**Try it**
- `./blender/build_addon.sh` → install the zip
- Open `flight_visualization.blend`
- **N ▸ Flight** → Fetch or Load & Build → **Render Video**

</div>

<div>

**Repo**
- Add-on: `blender/flight_viz_addon/`
- Preprocessor + tests: `preprocess/`
- Design notes: `DESIGN.md`

</div>

</div>

<div class="mt-8 text-center opacity-70">Questions?</div>

<!--
Wrap up. Offer a live demo (Fetch & Build), or play the rendered MP4.
-->
