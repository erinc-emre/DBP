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

import os

import bpy
from bpy.props import BoolProperty, FloatProperty, PointerProperty, StringProperty
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
    sync_sun: BoolProperty(name="Sync sun to flight time", default=True)
    chase_cam: BoolProperty(name="Build chase camera", default=True)
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
    speed: FloatProperty(
        name="Flight speed",
        default=1.0,
        min=0.1,
        soft_max=10.0,
        description="Animation speed (higher = faster = fewer frames)",
    )


def _config_from_props(props):
    """A per-run Config subclass so toggles don't mutate the importer defaults."""

    class Cfg(flight_importer.Config):
        pass

    Cfg.sync_sun = props.sync_sun
    Cfg.make_chase_cam = props.chase_cam
    Cfg.aircraft_size_multiplier = props.plane_scale
    Cfg.altitude_exaggeration = props.altitude_exag
    Cfg.route_bevel_factor = props.route_thickness
    Cfg.terrain_exaggeration = props.terrain_exag
    Cfg.speed = props.speed
    return Cfg


# --------------------------------------------------------------------------- #
# Operators
# --------------------------------------------------------------------------- #
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

        layout.prop(props, "json_path")

        col = layout.box().column(align=True)
        col.label(text="Scale")
        col.prop(props, "plane_scale")
        col.prop(props, "altitude_exag")
        col.prop(props, "route_thickness")
        col.prop(props, "terrain_exag")

        col = layout.box().column(align=True)
        col.label(text="Animation")
        col.prop(props, "speed")
        col.prop(props, "sync_sun")
        col.prop(props, "chase_cam")

        layout.operator("flightviz.build", icon="PLAY")
        layout.operator("flightviz.clear", icon="TRASH")


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
_classes = (
    FlightVizProps,
    FLIGHTVIZ_OT_build,
    FLIGHTVIZ_OT_clear,
    VIEW3D_PT_flightviz,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.flightviz = PointerProperty(type=FlightVizProps)


def unregister():
    del bpy.types.Scene.flightviz
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
