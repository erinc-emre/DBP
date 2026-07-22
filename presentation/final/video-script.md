# Video Recording Script — Flight Visualizer (2–3 min)

A light screengrab of the plugin workflow, ending with a sample rendered output.
No fancy editing — just clear on-screen steps plus short text overlays.

**Setup before recording**
- Blender open with `flight_visualization.blend`, add-on enabled, **N-panel → Flight** tab visible.
- 3D viewport in **Material Preview** (or Rendered) so the Earth looks good live.
- Have `renders/plugin_sample.mp4` ready to cut to at the end.
- Record at 1080p; hide unrelated editors for a clean frame.

---

## Shot list (target ≈ 2:30)

| # | Time | On screen | What you do | Text overlay |
|---|------|-----------|-------------|--------------|
| 1 | 0:00–0:12 | Title over the Earth in the viewport | Slowly orbit the Earth once | **Flight Visualizer** — replay a real airline flight on a 3D Earth · *Erinc Celikten* |
| 2 | 0:12–0:25 | Preferences ▸ Add-ons, "Flight Visualizer" ticked | Show it's installed/enabled | *Install: drag the zip into Blender ▸ enable* |
| 3 | 0:25–0:35 | N-panel → **Flight** tab | Hover the panel top to bottom | *Everything lives in one sidebar panel* |
| 4 | 0:35–0:55 | **Fetch from OpenSky** box | Type a callsign + departure ICAO (or an icao24) + date; click **Fetch & Build** | *Enter a flight → Fetch & Build* · *(downloads the real track from OpenSky)* |
| 5 | 0:55–1:10 | Scene builds: Earth, route, plane, airports | Let it finish; orbit to show the route arc + airports | *Route, aircraft, airports & sun — built in one click* |
| 6 | 1:10–1:25 | Press **Spacebar** to play; chase cam view | Play a few seconds of the animation | *Chase camera follows the flight — HUD shows alt / speed / UTC* |
| 7 | 1:25–1:45 | Panel sliders (Scale / Animation) | Change chase-cam lens or altitude, click **Load & Build** again | *Tweak & rebuild: scale, speed, camera, atmosphere…* |
| 8 | 1:45–1:55 | **Render (chase cam)** box | Pick 1080p, click **Render Video** | *One button → MP4 in the render folder* |
| 9 | 1:55–2:30 | Full-screen **`renders/plugin_sample.mp4`** | Cut to the pre-rendered clip, play it through | *Sample rendered output — DLH67K, Frankfurt → Madrid* |

---

## Overlay text bank (copy/paste)

- Flight Visualizer — replay a real airline flight on a 3D Earth
- Enter a flight → Fetch & Build
- Downloads the real track from the OpenSky Network
- Built in one click: Earth · route · aircraft · airports · sun · camera
- Chase camera + live HUD (callsign · altitude · speed · UTC · elapsed)
- Fully configurable: scale, speed, lens, night light, atmosphere, color grade
- One button → 1080p MP4
- Sample output: DLH67K · Frankfurt (EDDF) → Madrid (LEMD)

## Tips
- If a live Fetch is risky (network/credits), pre-fetch before recording and in shot 4
  just set **Flight JSON = preprocess/flight.json** and click **Load & Build** instead.
- Keep each step on screen ~2 s longer than feels natural — viewers read overlays slowly.
- A simple screen recorder (QuickTime / OBS) is enough; trim dead time only.
