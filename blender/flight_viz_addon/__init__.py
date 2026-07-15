"""Flight Visualizer — a minimal Blender add-on.

Loads a flight.json (produced by the external OpenSky preprocessor) and builds
a route + animated aircraft on an existing Earth, with an optional chase camera
and time-synced sun.

Scene requirements (created elsewhere, not by this add-on):
  * an Earth mesh named "ProcEarth"
  * an aircraft object named "B747_8F"
  * a sun lamp named "Sun_T3"  (only needed if "Sync sun" is on)

Install: zip this folder and use Blender > Preferences > Add-ons > Install,
or drop the folder in your add-ons directory and enable "Flight Visualizer".
"""

import datetime
import os
import subprocess
import tempfile

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import Operator, Panel, PropertyGroup

from . import flight_importer

bl_info = {
    "name": "Flight Visualizer",
    "author": "DBP course project",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar (N) > Flight",
    "description": "Import a flight.json and build a route + animated aircraft on the Earth.",
    "category": "Import-Export",
}


# --------------------------------------------------------------------------- #
# Settings (stored on the scene)
# --------------------------------------------------------------------------- #
class FlightVizProps(PropertyGroup):
    json_path: StringProperty(
        name="Flight JSON",
        description="Path to a flight.json produced by the preprocessor",
        subtype="FILE_PATH",
    )
    # --- Fetch (run the external preprocessor from the UI) --------------------
    fetch_callsign: StringProperty(
        name="Callsign",
        description="ICAO callsign, e.g. DLH67K (needs a departure ICAO to resolve)",
    )
    fetch_icao24: StringProperty(
        name="icao24",
        description="Transponder hex, e.g. 3c6487 (resolves directly; overrides callsign)",
    )
    fetch_dep_icao: StringProperty(
        name="Departure ICAO",
        description="Departure airport ICAO (e.g. EDDF) — required with a callsign",
    )
    fetch_arr_icao: StringProperty(
        name="Arrival ICAO",
        description="Arrival airport ICAO (optional, fills destination metadata)",
    )
    fetch_date: StringProperty(
        name="Date (UTC)",
        description="Departure date, YYYY-MM-DD (must be within ~30 days)",
    )
    credentials_path: StringProperty(
        name="Credentials",
        description="OpenSky credentials.json (blank = repo credentials.json)",
        subtype="FILE_PATH",
    )
    python_exe: StringProperty(
        name="Python",
        description="Python executable that has 'requests' installed (for the preprocessor)",
        default="python3",
    )
    sync_sun: BoolProperty(name="Sync sun to flight time", default=True)
    chase_cam: BoolProperty(name="Build chase camera", default=True)
    hud: BoolProperty(
        name="HUD overlay",
        default=True,
        description="On-screen readout: callsign, altitude, speed, UTC time, elapsed",
    )
    airports: BoolProperty(
        name="Place airports",
        default=True,
        description="Drop the airport model at the departure and arrival ends",
    )
    airport_path: StringProperty(
        name="Airport model",
        description="Path to the airport .glb ('//' = next to the .blend)",
        subtype="FILE_PATH",
        default="//airport.glb",
    )
    airport_size: FloatProperty(
        name="Airport size",
        default=0.05,
        min=0.005,
        soft_max=0.3,
        description="Longest dimension of the placed airport, in scene units",
    )
    night_light: BoolProperty(
        name="Night fill light",
        default=True,
        description="Chase-cam light so the plane/airport stay visible on the night side",
    )
    atmosphere: BoolProperty(
        name="Atmosphere glow",
        default=True,
        description="Glowing blue halo around the Earth's limb",
    )
    grade: BoolProperty(
        name="Color grade + bloom",
        default=True,
        description="Contrasty view look + a compositor bloom on the bright areas",
    )
    night_light_energy: FloatProperty(
        name="Night light power",
        default=0.35,
        min=0.0,
        soft_max=3.0,
        description="Strength of the chase-cam headlight sun (fill for the night side)",
    )
    # scale factors
    plane_scale: FloatProperty(
        name="Plane size (× real)", default=100.0, min=1.0, soft_max=500.0
    )
    altitude_exag: FloatProperty(
        name="Route altitude (× real)", default=10.0, min=0.1, soft_max=50.0
    )
    route_thickness: FloatProperty(
        name="Route line thickness",
        default=0.08,
        min=0.0,
        soft_max=1.0,
        description="Route tube thickness as a fraction of the aircraft length",
    )
    terrain_exag: FloatProperty(
        name="Earth relief (× real)",
        default=1.0,
        min=0.0,
        soft_max=20.0,
        description="Terrain/mountain height exaggeration",
    )
    length_mode: EnumProperty(
        name="Length",
        description="How the animation length is decided",
        items=[
            ("SPEED", "Fixed ÷ speed", "Same clip length for every flight"),
            ("DURATION", "Scale to duration", "Longer real flights => longer clips"),
        ],
        default="SPEED",
    )
    speed: FloatProperty(
        name="Flight speed",
        default=1.0,
        min=0.1,
        soft_max=10.0,
        description="Animation speed (higher = faster = fewer frames)",
    )
    time_compression: FloatProperty(
        name="Real sec / playback sec",
        default=1800.0,
        min=1.0,
        soft_max=7200.0,
        description=(
            "DURATION mode: real flight seconds shown per playback second "
            "(1800 = 30 min of flight per second)"
        ),
    )
    chase_lens: FloatProperty(
        name="Chase cam lens (mm)",
        default=20.0,
        min=5.0,
        soft_max=100.0,
        description="Chase camera focal length; lower = wider = zoomed out",
    )
    # --- Calibration (per Earth asset / aircraft model) -----------------------
    lon_offset: FloatProperty(
        name="Longitude offset (°)",
        default=-177.19,
        min=-360.0,
        max=360.0,
        description=(
            "Texture longitude calibration for the Earth. If the route lands on "
            "the wrong meridian, adjust this until it lines up (asset-specific)"
        ),
    )
    forward_axis: EnumProperty(
        name="Model nose axis",
        description="Which local axis the aircraft model's nose points along",
        items=[
            ("-Y", "-Y", "Nose points along -Y (Boeing 747-8F GLB)"),
            ("+Y", "+Y", "Nose points along +Y"),
        ],
        default="-Y",
    )
    # --- Render options -------------------------------------------------------
    render_dir: StringProperty(
        name="Render dir",
        description="Folder for rendered videos ('//' = next to the .blend file)",
        subtype="DIR_PATH",
        default="//renders",
    )
    render_resolution: EnumProperty(
        name="Resolution",
        description="Output video resolution",
        items=[
            ("540", "540p", "960 x 540"),
            ("720", "720p", "1280 x 720"),
            ("1080", "1080p", "1920 x 1080"),
        ],
        default="720",
    )


def _config_from_props(props):
    """A per-run Config subclass so toggles don't mutate the importer defaults."""

    class Cfg(flight_importer.Config):
        pass

    Cfg.sync_sun = props.sync_sun
    Cfg.make_chase_cam = props.chase_cam
    Cfg.make_hud = props.hud
    Cfg.place_airports = props.airports
    Cfg.airport_model_path = props.airport_path
    Cfg.airport_target_size = props.airport_size
    Cfg.make_subject_light = props.night_light
    Cfg.subject_light_energy = props.night_light_energy
    Cfg.make_atmosphere = props.atmosphere
    Cfg.make_grade = props.grade
    Cfg.aircraft_size_multiplier = props.plane_scale
    Cfg.altitude_exaggeration = props.altitude_exag
    Cfg.route_bevel_factor = props.route_thickness
    Cfg.terrain_exaggeration = props.terrain_exag
    Cfg.speed = props.speed
    Cfg.frame_mode = props.length_mode
    Cfg.time_compression = props.time_compression
    Cfg.chase_lens = props.chase_lens
    Cfg.lon_offset_deg = props.lon_offset
    Cfg.forward_sign = 1.0 if props.forward_axis == "+Y" else -1.0
    return Cfg


# --------------------------------------------------------------------------- #
# Operators
# --------------------------------------------------------------------------- #
class FLIGHTVIZ_OT_fetch(Operator):
    bl_idname = "flightviz.fetch"
    bl_label = "Fetch & Build"
    bl_description = (
        "Run the external preprocessor to download the flight from OpenSky, then "
        "load & build it. Needs network, credentials, and a recent date (<= ~30 days). "
        "Uses OpenSky API credits."
    )

    def execute(self, context):
        props = context.scene.flightviz
        date = props.fetch_date.strip()
        callsign = props.fetch_callsign.strip()
        icao24 = props.fetch_icao24.strip()
        if not date:
            self.report({"ERROR"}, "Enter a date (YYYY-MM-DD).")
            return {"CANCELLED"}
        if not callsign and not icao24:
            self.report({"ERROR"}, "Enter a callsign (+ departure ICAO) or an icao24.")
            return {"CANCELLED"}
        if callsign and not icao24 and not props.fetch_dep_icao.strip():
            self.report({"ERROR"}, "A callsign needs a Departure ICAO to resolve.")
            return {"CANCELLED"}

        # Resolve the preprocessor + credentials paths (default to the repo layout).
        addon_dir = os.path.dirname(__file__)
        repo = os.path.normpath(os.path.join(addon_dir, "..", ".."))
        script = os.path.join(repo, "preprocess", "opensky_to_flightjson.py")
        creds = (
            bpy.path.abspath(props.credentials_path)
            if props.credentials_path
            else os.path.join(repo, "credentials.json")
        )
        if not os.path.isfile(script):
            self.report({"ERROR"}, f"Preprocessor not found: {script}")
            return {"CANCELLED"}

        out = (
            bpy.path.abspath("//fetched_flight.json")
            if bpy.data.filepath
            else os.path.join(tempfile.gettempdir(), "fetched_flight.json")
        )
        cmd = [props.python_exe, script, "--date", date, "--out", out]
        if icao24:
            cmd += ["--icao24", icao24]
        else:
            cmd += ["--callsign", callsign, "--dep-icao", props.fetch_dep_icao.strip()]
        if props.fetch_arr_icao.strip():
            cmd += ["--arr-icao", props.fetch_arr_icao.strip()]
        if os.path.isfile(creds):
            cmd += ["--credentials", creds]

        self.report({"INFO"}, "Fetching from OpenSky ...")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except FileNotFoundError:
            self.report(
                {"ERROR"},
                f"Python '{props.python_exe}' not found (set the Python field).",
            )
            return {"CANCELLED"}
        except subprocess.TimeoutExpired:
            self.report({"ERROR"}, "Fetch timed out.")
            return {"CANCELLED"}

        if proc.returncode != 0 or not os.path.isfile(out):
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()
            msg = tail[-1] if tail else "unknown error"
            self.report({"ERROR"}, f"Fetch failed: {msg}")
            return {"CANCELLED"}

        props.json_path = out
        self.report({"INFO"}, "Fetched flight.json — building ...")
        return bpy.ops.flightviz.build()


class FLIGHTVIZ_OT_build(Operator):
    bl_idname = "flightviz.build"
    bl_label = "Load & Build"
    bl_description = "Load the flight.json and build the route + animated aircraft"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.flightviz
        path = bpy.path.abspath(props.json_path) if props.json_path else ""
        if not path or not os.path.isfile(path):
            self.report({"ERROR"}, "Set a valid Flight JSON file path.")
            return {"CANCELLED"}

        cfg = _config_from_props(props)
        for required in (cfg.earth_object, cfg.aircraft_root):
            if required not in bpy.data.objects:
                self.report({"ERROR"}, f"Scene is missing object '{required}'.")
                return {"CANCELLED"}

        try:
            res = flight_importer.import_flight(path, cfg)
        except Exception as exc:  # keep the UI friendly
            self.report({"ERROR"}, f"Build failed: {exc}")
            return {"CANCELLED"}

        self.report(
            {"INFO"},
            f"Built {res.get('callsign') or 'flight'}: {res['waypoints']} waypoints",
        )
        return {"FINISHED"}


class FLIGHTVIZ_OT_clear(Operator):
    bl_idname = "flightviz.clear"
    bl_label = "Clear"
    bl_description = "Remove the generated route and chase camera"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        flight_importer.clear_scene()
        self.report({"INFO"}, "Cleared flight visualization")
        return {"FINISHED"}


def _set_video_output(render, filepath):
    """Configure the render for an H.264 MP4 at `filepath` (Blender 4.2 - 5.x)."""
    imgs = render.image_settings
    if hasattr(imgs, "media_type"):  # Blender 5.x splits image vs. video
        imgs.media_type = "VIDEO"
    imgs.file_format = "FFMPEG"
    render.ffmpeg.format = "MPEG4"
    render.ffmpeg.codec = "H264"
    render.ffmpeg.constant_rate_factor = "MEDIUM"
    render.filepath = filepath


class FLIGHTVIZ_OT_render(Operator):
    bl_idname = "flightviz.render"
    bl_label = "Render Video"
    bl_description = (
        "Render the chase-cam animation at the selected resolution to an MP4 in "
        "the render directory, named with the current date and time"
    )

    _RES = {"540": (960, 540), "720": (1280, 720), "1080": (1920, 1080)}

    def execute(self, context):
        props = context.scene.flightviz
        scn = context.scene

        cam = bpy.data.objects.get("ChaseCam")
        if cam is None:
            self.report({"ERROR"}, "ChaseCam not found - build the flight first.")
            return {"CANCELLED"}
        scn.camera = cam

        # resolve/create the output directory ('//' resolves next to the .blend)
        out_dir = bpy.path.abspath(props.render_dir) if props.render_dir else ""
        if not out_dir:
            out_dir = bpy.path.abspath("//renders")
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as exc:
            self.report({"ERROR"}, f"Cannot create render dir: {exc}")
            return {"CANCELLED"}

        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        fname = f"flight_chase_{stamp}.mp4"
        filepath = os.path.join(out_dir, fname)

        r = scn.render
        r.resolution_x, r.resolution_y = self._RES[props.render_resolution]
        r.resolution_percentage = 100
        r.fps = 24
        scn.frame_step = 1  # render every frame (guard against a stale step)
        _set_video_output(r, filepath)

        self.report({"INFO"}, f"Rendering {fname} ...")
        try:
            bpy.ops.render.render(animation=True)
        except Exception as exc:
            self.report({"ERROR"}, f"Render failed: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Saved video: {filepath}")
        return {"FINISHED"}


# --------------------------------------------------------------------------- #
# Panel
# --------------------------------------------------------------------------- #
class VIEW3D_PT_flightviz(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Flight"
    bl_label = "Flight Visualizer"

    def draw(self, context):
        layout = self.layout
        props = context.scene.flightviz

        col = layout.box().column(align=True)
        col.label(text="Fetch from OpenSky")
        col.prop(props, "fetch_callsign")
        col.prop(props, "fetch_dep_icao")
        col.prop(props, "fetch_icao24")
        col.prop(props, "fetch_arr_icao")
        col.prop(props, "fetch_date")
        col.prop(props, "credentials_path")
        col.prop(props, "python_exe")
        col.operator("flightviz.fetch", icon="URL")

        layout.prop(props, "json_path")

        col = layout.box().column(align=True)
        col.label(text="Scale")
        col.prop(props, "plane_scale")
        col.prop(props, "altitude_exag")
        col.prop(props, "route_thickness")
        col.prop(props, "terrain_exag")
        col.prop(props, "airports")
        col.prop(props, "airport_size")
        col.prop(props, "airport_path")

        col = layout.box().column(align=True)
        col.label(text="Animation")
        col.prop(props, "length_mode")
        if props.length_mode == "DURATION":
            col.prop(props, "time_compression")
        else:
            col.prop(props, "speed")
        col.prop(props, "sync_sun")
        col.prop(props, "chase_cam")
        col.prop(props, "chase_lens")
        col.prop(props, "hud")
        col.prop(props, "night_light")
        col.prop(props, "night_light_energy")
        col.prop(props, "atmosphere")
        col.prop(props, "grade")

        col = layout.box().column(align=True)
        col.label(text="Calibration")
        col.prop(props, "lon_offset")
        col.prop(props, "forward_axis")

        layout.operator("flightviz.build", icon="PLAY")
        layout.operator("flightviz.clear", icon="TRASH")

        col = layout.box().column(align=True)
        col.label(text="Render (chase cam)")
        col.prop(props, "render_resolution")
        col.prop(props, "render_dir")
        col.operator("flightviz.render", icon="RENDER_ANIMATION")


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
_classes = (
    FlightVizProps,
    FLIGHTVIZ_OT_fetch,
    FLIGHTVIZ_OT_build,
    FLIGHTVIZ_OT_clear,
    FLIGHTVIZ_OT_render,
    VIEW3D_PT_flightviz,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.flightviz = PointerProperty(type=FlightVizProps)
    # keep the HUD text in sync with the current frame (incl. during renders)
    h = flight_importer.hud_frame_handler
    if h not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(h)


def unregister():
    h = flight_importer.hud_frame_handler
    if h in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(h)
    del bpy.types.Scene.flightviz
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
