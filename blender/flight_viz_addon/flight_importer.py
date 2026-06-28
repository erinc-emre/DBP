"""
flight_importer.py — load a flight.json (see preprocess/FLIGHT_SCHEMA.md) into Blender
and build a data-driven flight visualization on an existing Earth sphere.

It creates:
  * a great-circle route curve following the waypoints (altitude-exaggerated),
  * an animated aircraft (the root empty of an imported model) flying the path
    with path-tangent orientation (nose along travel, belly toward Earth),
  * a baked chase camera following the aircraft.

Designed to run inside Blender (Blender 4.x / 5.x, `bpy`). It is intentionally a
plain module of functions so it can later be wrapped by an add-on operator.

Assumptions / conventions
--------------------------
* The Earth is a sphere centred at the world origin; pass its object name.
* lat/lon -> sphere uses:  x=R*cos(lat)*cos(lon+LON_OFFSET),
                           y=R*cos(lat)*sin(lon+LON_OFFSET),
                           z=R*sin(lat)
  LON_OFFSET aligns the route with the Earth texture's longitude seam and must be
  calibrated once per Earth asset (──> for the bundled ProcEarth it is -168°).
* The aircraft model's local forward axis is +Y and up axis is +Z (true for the
  bundled Boeing 747-8F GLB whose root empty is "B747_8F"). Flip FORWARD_SIGN if
  a different model points the other way.
* Units in flight.json are SI (m, m/s, Unix s).
"""

import bpy
import json
import math
import mathutils

REAL_EARTH_R = 6_371_000.0  # meters


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
class Config:
    earth_object = "ProcEarth"
    aircraft_root = "B747_8F"  # root empty/object to animate (already in scene)
    lon_offset_deg = (
        -177.19
    )  # texture longitude calibration (measured from ProcEarth earth_uv)
    alt_target_frac = 0.06  # max altitude drawn as this fraction of Earth radius
    route_bevel = 0.03  # route tube thickness (Blender units)
    forward_sign = -1.0  # +1 if model nose is +Y, -1 if -Y (B747 GLB nose is -Y)
    smooth_window = 9  # moving-average window over waypoints (<=2 disables)
    smooth_passes = 3  # number of smoothing passes (more = smoother)
    sync_sun = True  # drive Sun_T3 from the flight's real UTC time (subsolar point)
    sun_object = "Sun_T3"
    make_chase_cam = True
    chase_back = 2.6  # chase camera distance behind (Blender units)
    chase_up = 1.1  # chase camera height above aircraft
    frame_camera = True  # aim the overview camera at the route after building
    camera_object = "Camera_T3"  # overview camera to frame
    overview_distance = 2.2  # overview camera distance = Earth radius * this
    frame_start = None  # None -> use scene.frame_start
    frame_end = None  # None -> use scene.frame_end


# --------------------------------------------------------------------------- #
# Geo helpers
# --------------------------------------------------------------------------- #
def earth_base_radius(earth_obj):
    """Representative (sea-level) radius of the displaced Earth = min vertex radius.

    Using the minimum (oceans sit at the base sphere) gives a stable reference for
    altitude scaling, independent of the tallest terrain bump.
    """
    dg = bpy.context.evaluated_depsgraph_get()
    me = earth_obj.evaluated_get(dg).to_mesh()
    c = earth_obj.matrix_world.translation
    rmin = min((earth_obj.matrix_world @ v.co - c).length for v in me.vertices)
    earth_obj.evaluated_get(dg).to_mesh_clear()
    return rmin


def smooth_points(pts, window, passes):
    """Moving-average smoothing of a list of 3D points to remove ADS-B jitter.

    Endpoints are held fixed so the path still starts/ends exactly at the
    airports. Near the ends the window shrinks symmetrically.
    """
    n = len(pts)
    if window < 3 or passes < 1 or n < 3:
        return list(pts)
    half = window // 2
    cur = list(pts)
    for _ in range(passes):
        nxt = list(cur)
        for i in range(1, n - 1):
            k = min(half, i, n - 1 - i)  # symmetric, shrinking near ends
            acc = mathutils.Vector((0.0, 0.0, 0.0))
            for j in range(i - k, i + k + 1):
                acc += cur[j]
            nxt[i] = acc / (2 * k + 1)
        cur = nxt
    return cur


def _unit_dir(lat, lon, off):
    latr = math.radians(lat)
    lonr = math.radians(lon + off)
    return mathutils.Vector(
        (
            math.cos(latr) * math.cos(lonr),
            math.cos(latr) * math.sin(lonr),
            math.sin(latr),
        )
    )


def project_waypoint(wp, off, base_radius, alt_unit_per_m, center):
    """Place a waypoint at  base_radius + alt*scale  along its direction.

    The Earth is a smooth sphere (surface detail comes from the normal map, not
    geometry), so a constant radius puts airports exactly on the surface and lifts
    the aircraft by an exaggerated-but-proportional altitude offset.
    """
    d = _unit_dir(wp["lat"], wp["lon"], off)
    return center + (base_radius + wp["alt_m"] * alt_unit_per_m) * d


def _emissive(name, rgb, strength):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = (*rgb, 1.0)
    e.inputs[1].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], out.inputs[0])
    return m


def _remove(name):
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #
def build_route(cfg, pts):
    _remove("FlightRoute")
    cu = bpy.data.curves.new("FlightRoute_c", "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p.x, p.y, p.z, 1.0)
    cu.bevel_depth = cfg.route_bevel
    cu.bevel_resolution = 2
    cu.materials.append(_emissive("FlightRoute_mat", (1.0, 0.85, 0.2), 4.0))
    obj = bpy.data.objects.new("FlightRoute", cu)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def position_at(pts, trel, tr):
    """3D position at relative time `tr` (linear interpolation between waypoints)."""
    if tr <= trel[0]:
        return pts[0]
    if tr >= trel[-1]:
        return pts[-1]
    lo, hi = 0, len(trel) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if trel[mid] <= tr:
            lo = mid
        else:
            hi = mid
    span = trel[hi] - trel[lo]
    f = (tr - trel[lo]) / span if span > 0 else 0.0
    return pts[lo].lerp(pts[hi], f)


def _orient(fwd, radial, forward_sign):
    fwd = fwd * forward_sign
    if fwd.length < 1e-6:
        fwd = mathutils.Vector((0, 1, 0))
    fwd.normalize()
    up = (radial - fwd * radial.dot(fwd)).normalized()
    right = fwd.cross(up)
    return mathutils.Matrix(
        ((right.x, fwd.x, up.x), (right.y, fwd.y, up.y), (right.z, fwd.z, up.z))
    ).to_euler()


def animate_aircraft(cfg, pts, trel, f0, f1):
    ac = bpy.data.objects[cfg.aircraft_root]
    if ac.animation_data:
        ac.animation_data_clear()
    ac.rotation_mode = "XYZ"
    total = trel[-1]
    nf = max(f1 - f0, 1)
    for f in range(f0, f1 + 1):
        tr = (f - f0) / nf * total
        p = position_at(pts, trel, tr)
        pn = position_at(pts, trel, min(tr + total * 0.01, total))
        ac.location = p
        ac.rotation_euler = _orient(pn - p, p.normalized(), cfg.forward_sign)
        ac.keyframe_insert("location", frame=f)
        ac.keyframe_insert("rotation_euler", frame=f)
    return ac


def build_chase_cam(cfg, pts, trel, f0, f1):
    _remove("ChaseCam")
    cdata = bpy.data.cameras.new("ChaseCam")
    cdata.lens = 35
    chase = bpy.data.objects.new("ChaseCam", cdata)
    bpy.context.scene.collection.objects.link(chase)
    chase.rotation_mode = "XYZ"
    total = trel[-1]
    nf = max(f1 - f0, 1)
    for f in range(f0, f1 + 1):
        tr = (f - f0) / nf * total
        p = position_at(pts, trel, tr)
        pn = position_at(pts, trel, min(tr + total * 0.01, total))
        fwd = pn - p
        fwd = fwd.normalized() if fwd.length > 1e-6 else mathutils.Vector((0, 1, 0))
        up = p.normalized()
        chase.location = p + up * cfg.chase_up - fwd * cfg.chase_back
        look = (p + fwd * 1.0) - chase.location
        chase.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
        chase.keyframe_insert("location", frame=f)
        chase.keyframe_insert("rotation_euler", frame=f)
    return chase


def frame_overview_camera(cfg, pts):
    """Aim the overview camera at the route's mid-direction, from outside the globe."""
    cam = bpy.data.objects.get(cfg.camera_object)
    if cam is None:
        return None
    earth = bpy.data.objects[cfg.earth_object]
    center = earth.matrix_world.translation.copy()
    radius = max(earth.dimensions) / 2.0
    mid = sum((p.normalized() for p in pts), mathutils.Vector()).normalized()
    if cam.animation_data:
        cam.animation_data_clear()
    cam.rotation_mode = "XYZ"
    cam.location = center + mid * (radius * cfg.overview_distance)
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def _subsolar_dir(t_unix, off):
    """Unit vector (in the scene's geo convention) pointing at the subsolar point
    for a given UTC Unix time: the spot on Earth where the Sun is overhead.

    lon_subsolar = (12 - UTC_hours) * 15  (ignores the equation of time, ~<=15 min)
    lat_subsolar = solar declination for the date.
    """
    import datetime

    dt = datetime.datetime.fromtimestamp(t_unix, tz=datetime.timezone.utc)
    hours = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    doy = dt.timetuple().tm_yday
    decl = 23.44 * math.sin(math.radians(360.0 / 365.0 * (doy - 81)))  # ~0 at equinox
    sub_lon = (12.0 - hours) * 15.0
    return _unit_dir(decl, sub_lon, off)


def clear_scene(cfg=Config):
    """Remove everything the importer generates and reset driven animations.

    Leaves the Earth and the aircraft object in place (only clears their
    animation), so a fresh Build can run cleanly.
    """
    for name in ("FlightRoute", "ChaseCam"):
        _remove(name)
    for obj_name in (cfg.aircraft_root, cfg.sun_object):
        o = bpy.data.objects.get(obj_name)
        if o and o.animation_data:
            o.animation_data_clear()


def animate_sun(cfg, wps, f0, f1):
    """Keyframe the Sun lamp so its direction tracks the real subsolar point over
    the flight's actual time span (Earth turns 15°/h, so a 2 h flight => ~30°).

    The Sun emits along its local -Z; we aim that toward the Earth centre from the
    subsolar side so the lit hemisphere matches the real date/time and geography.
    """
    sun = bpy.data.objects.get(cfg.sun_object)
    if sun is None:
        return None
    if sun.animation_data:
        sun.animation_data_clear()
    sun.rotation_mode = "XYZ"
    off = cfg.lon_offset_deg
    t0 = wps[0]["t"]
    dur = (wps[-1]["t"] - t0) or 1
    nf = max(f1 - f0, 1)
    for f in range(f0, f1 + 1):
        t = t0 + (f - f0) / nf * dur
        emit = -_subsolar_dir(t, off)  # rays travel from subsolar point toward centre
        sun.rotation_euler = emit.to_track_quat("-Z", "Y").to_euler()
        sun.keyframe_insert("rotation_euler", frame=f)
    if sun.animation_data and sun.animation_data.action:
        for fc in _action_fcurves(sun.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    return sun


def _action_fcurves(action):
    """Yield fcurves from legacy or layered (4.4+/5.x) actions."""
    if hasattr(action, "fcurves") and len(action.fcurves):
        yield from action.fcurves
        return
    try:
        for layer in action.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    yield from cb.fcurves
    except Exception:
        return


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def import_flight(json_path, cfg=Config):
    """Build the full visualization from a flight.json file. Returns a summary dict."""
    data = json.load(open(json_path))
    wps = data["waypoints"]
    if len(wps) < 2:
        raise ValueError("flight.json needs at least 2 waypoints")

    scn = bpy.context.scene
    f0 = cfg.frame_start if cfg.frame_start is not None else scn.frame_start
    f1 = cfg.frame_end if cfg.frame_end is not None else scn.frame_end

    earth = bpy.data.objects[cfg.earth_object]
    center = earth.matrix_world.translation.copy()
    R_base = earth_base_radius(earth)
    max_alt = max(w["alt_m"] for w in wps) or 1.0
    # Max cruise altitude is drawn as alt_target_frac of the (base) radius above
    # the surface; offset is linear in altitude.
    alt_unit_per_m = (cfg.alt_target_frac * R_base) / max_alt

    off = cfg.lon_offset_deg
    pts = [project_waypoint(w, off, R_base, alt_unit_per_m, center) for w in wps]
    trel = [w["t_rel"] for w in wps]

    # Smooth out raw ADS-B jitter so the route line and the aircraft motion
    # read as a clean flight path rather than a noisy GPS trace.
    pts = smooth_points(pts, cfg.smooth_window, cfg.smooth_passes)

    # (data["origin"]/["destination"] are metadata only — not drawn in the scene.)
    build_route(cfg, pts)
    animate_aircraft(cfg, pts, trel, f0, f1)
    if cfg.sync_sun:
        animate_sun(cfg, wps, f0, f1)
    if cfg.make_chase_cam:
        build_chase_cam(cfg, pts, trel, f0, f1)
    if cfg.frame_camera:
        frame_overview_camera(cfg, pts)

    scn.frame_set(f0)
    return {
        "waypoints": len(pts),
        "earth_base_radius": round(R_base, 3),
        "max_alt_offset": round(alt_unit_per_m * max_alt, 3),
        "frames": [f0, f1],
        "callsign": data.get("meta", {}).get("callsign"),
    }


if __name__ == "__main__":
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    # Offline demo = a saved real flight (preprocess/flight.json), produced by the
    # preprocessor from an OpenSky request and reused without hitting the API.
    default = os.path.join(here, "..", "..", "preprocess", "flight.json")
    print(import_flight(os.path.normpath(default)))
