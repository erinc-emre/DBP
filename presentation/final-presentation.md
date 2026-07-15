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

Take a **real airline flight** and replay it as a smooth fly-along on a 3D Earth.

<div class="grid grid-cols-2 gap-8 mt-6">

<div>

**Two parts**
- **Outside Blender** — a Python tool downloads the flight from the **OpenSky Network**, cleans it, and writes a small **`flight.json`**
- **Inside Blender** — a **one-click add-on** reads that file and builds the whole scene

</div>

<div>

**Why two parts?**
- Network and login code stay out of Blender
- The two parts meet at one simple file: **`flight.json`**
- Once downloaded, a flight works **offline**, every time

</div>

</div>

<!--
Recap the concept: a preprocessor and an add-on, meeting at flight.json.
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

Detailed Earth (day / night / mountains) · airports at both ends · the sun placed
by the flight's **real time of day** · the plane pitches and banks · on-screen
readout · night light · atmosphere and color polish · **one-click video export**

</div>

<!--
Feature montage. Everything is a toggle in the sidebar. The sun is placed by the real time of day, not a spinning Earth.
-->

---

# Architecture

```mermaid {scale: 0.42}
flowchart LR
    A[Callsign + Date] --> B[OpenSky Preprocessor]
    B --> C[flight.json]
    C --> D[Flight Visualizer add-on]
    E[Boeing 747-8F] --> D
    F[airport.glb] --> D
    D --> G[Earth + route + aircraft + airports + HUD]
    G --> H[Chase cam + sun + atmosphere + grade]
    H --> I[Rendered MP4]
```

<div class="text-sm mt-6 opacity-85">

Everything connects through one file: **`flight.json`**. A small checker makes
sure the file is valid before Blender uses it. You can also **fetch a flight
straight from the add-on** — it runs the Python tool for you.

</div>

<!--
Same diagram as the README. Everything meets at flight.json, which is validated before use. Fetch can run from the UI.
-->

---

# Challenge: smooth flight from messy data

The real flight data is **rough**: points arrive unevenly, with long gaps —
sometimes the position freezes, then jumps.

<div class="grid grid-cols-2 gap-6 mt-2 text-sm">

<div>

**What went wrong**
- The plane **sped up and stalled** as it played
- One ocean gap of **2608 km** made the path cut a straight line **through the Earth** — the plane flew underground

</div>

<div>

**How I fixed it**
- Move the plane by **equal distance each frame** → steady speed
- Follow the **curve of the Earth** between points, not a straight line
- Measure altitude from the **ground right below** the plane

</div>

</div>

<div class="mt-3 text-sm">

**Result** — the speed is even (jump-to-average ratio **17.6× → ~1.0×**) and the plane **always stays above the surface**.

</div>

<!--
Most important implementation story. Real data is rough; naive time playback fails. The 2608km gap flying underground is a concrete example. Plain-language fixes: equal distance per frame, follow the curve, altitude from the local ground.
-->

---

# Challenge: getting the data from OpenSky

<div class="grid grid-cols-2 gap-6 mt-2 text-sm">

<div>

**The tricky parts**
- You can't search by flight number like "LH401" — the data is keyed to the **aircraft's radio ID** (`icao24`)
- So I look up the aircraft first, then get its track
- Login uses a **token** (OAuth2)
- Only the **last ~30 days** of flights are available

</div>

<div>

**How I handled it**
- Enter a **callsign + departure airport**, or the aircraft ID directly
- If the date is too old, stop early with a **clear message**
- Speed isn't in the data, so I **compute it** from the points
- The download code stays **outside Blender**; the add-on finds the right Python automatically

</div>

</div>

<!--
Second deep-dive: data access. Can't search by flight number - keyed to aircraft radio ID. Token login, 30-day window. Practical guards in plain terms.
-->

---

# Roadmap

<div class="grid grid-cols-2 gap-8 mt-4">

<div>

## Done ✅
- Download flights from OpenSky, save as `flight.json`
- One-click add-on (+ **fetch from the UI**)
- Smooth, steady motion that stays above the ground
- Chase camera (level, never underground)
- Plane pitches and banks in turns
- Airports at both ends
- On-screen readout (callsign, altitude, speed, time)
- Night light · atmosphere · nicer colors
- Save to video · tests · easy install · docs

</div>

<div>

## Future work 🔭
- **Weather layer** (clouds, wind) — left out for now
- **Older flights (30+ days)** — needs special OpenSky access
- More camera angles and motion blur
- Sharper Earth textures for close-ups

</div>

</div>

<!--
Most of the plan is done. Weather was left out on purpose to keep a solid flight visualization. Older-than-30-days needs external OpenSky access.
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
