"""
flight_importer.py — load a flight.json (see preprocess/FLIGHT_SCHEMA.md) into Blender
and build a data-driven flight visualization on an existing Earth sphere.

It creates:
  * a great-circle route curve following the waypoints (altitude-exaggerated),
  * origin / destination emissive markers,
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
    lon_offset_deg = -168.0  # texture longitude calibration
    alt_target_frac = 0.06  # max altitude drawn as this fraction of Earth radius
    route_bevel = 0.03  # route tube thickness (Blender units)
    forward_sign = -1.0  # +1 if model nose is +Y, -1 if -Y (B747 GLB nose is -Y)
    smooth_window = 9  # moving-average window over waypoints (<=2 disables)
    smooth_passes = 3  # number of smoothing passes (more = smoother)
    make_chase_cam = True
    chase_back = 2.6  # chase camera distance behind (Blender units)
    chase_up = 1.1  # chase camera height above aircraft
    frame_start = None  # None -> use scene.frame_start
    frame_end = None  # None -> use scene.frame_end


# --------------------------------------------------------------------------- #
# Geo helpers
# --------------------------------------------------------------------------- #
def earth_radius(cfg):
    return max(bpy.data.objects[cfg.earth_object].dimensions) / 2.0


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


def make_to_xyz(cfg, R, alt_exag):
    off = cfg.lon_offset_deg

    def to_xyz(lat, lon, alt_m):
        latr = math.radians(lat)
        lonr = math.radians(lon + off)
        rr = R + alt_m * (R / REAL_EARTH_R) * alt_exag
        return mathutils.Vector(
            (
                rr * math.cos(latr) * math.cos(lonr),
                rr * math.cos(latr) * math.sin(lonr),
                rr * math.sin(latr),
            )
        )

    return to_xyz


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


def build_markers(cfg, to_xyz, origin, destination):
    out = {}
    # Always clear previous markers first, so re-importing a different flight
    # never leaves a stale marker from the prior route.
    _remove("Marker_Origin")
    _remove("Marker_Dest")
    for key, info, rgb in (
        ("Marker_Origin", origin, (1.0, 0.05, 0.05)),
        ("Marker_Dest", destination, (0.1, 0.3, 1.0)),
    ):
        if not info or info.get("lat") is None:
            continue
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.45, location=to_xyz(info["lat"], info["lon"], 0.0)
        )
        o = bpy.context.active_object
        o.name = key
        o.data.materials.append(_emissive(key + "_mat", rgb, 8.0))
        out[key] = o
    return out


def _path_sampler(pts, trel):
    total = trel[-1]

    def pos_at(tr):
        if tr <= trel[0]:
            return pts[0]
        if tr >= total:
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

    return pos_at, total


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
    pos_at, total = _path_sampler(pts, trel)
    nf = max(f1 - f0, 1)
    for f in range(f0, f1 + 1):
        tr = (f - f0) / nf * total
        p = pos_at(tr)
        pn = pos_at(min(tr + total * 0.01, total))
        ac.location = p
        ac.rotation_euler = _orient(pn - p, p.normalized(), cfg.forward_sign)
        ac.keyframe_insert("location", frame=f)
        ac.keyframe_insert("rotation_euler", frame=f)
    return ac, pos_at, total


def build_chase_cam(cfg, pos_at, total, f0, f1):
    _remove("ChaseCam")
    cdata = bpy.data.cameras.new("ChaseCam")
    cdata.lens = 35
    chase = bpy.data.objects.new("ChaseCam", cdata)
    bpy.context.scene.collection.objects.link(chase)
    chase.rotation_mode = "XYZ"
    nf = max(f1 - f0, 1)
    for f in range(f0, f1 + 1):
        tr = (f - f0) / nf * total
        p = pos_at(tr)
        pn = pos_at(min(tr + total * 0.01, total))
        fwd = pn - p
        fwd = fwd.normalized() if fwd.length > 1e-6 else mathutils.Vector((0, 1, 0))
        up = p.normalized()
        chase.location = p + up * cfg.chase_up - fwd * cfg.chase_back
        look = (p + fwd * 1.0) - chase.location
        chase.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
        chase.keyframe_insert("location", frame=f)
        chase.keyframe_insert("rotation_euler", frame=f)
    return chase


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

    R = earth_radius(cfg)
    max_alt = max(w["alt_m"] for w in wps) or 1.0
    alt_exag = (cfg.alt_target_frac * R) / (max_alt * (R / REAL_EARTH_R))
    to_xyz = make_to_xyz(cfg, R, alt_exag)

    pts = [to_xyz(w["lat"], w["lon"], w["alt_m"]) for w in wps]
    trel = [w["t_rel"] for w in wps]

    # Smooth out raw ADS-B jitter so the route line and the aircraft motion
    # read as a clean flight path rather than a noisy GPS trace.
    pts = smooth_points(pts, cfg.smooth_window, cfg.smooth_passes)

    build_route(cfg, pts)
    build_markers(cfg, to_xyz, data.get("origin"), data.get("destination"))
    ac, pos_at, total = animate_aircraft(cfg, pts, trel, f0, f1)
    if cfg.make_chase_cam:
        build_chase_cam(cfg, pos_at, total, f0, f1)

    scn.frame_set(f0)
    return {
        "waypoints": len(pts),
        "earth_radius": round(R, 3),
        "alt_exaggeration": round(alt_exag, 2),
        "frames": [f0, f1],
        "callsign": data.get("meta", {}).get("callsign"),
    }


if __name__ == "__main__":
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    # Canonical demo = a REAL flight (preprocess/flight.json). The synthetic
    # sample_flight.json remains as an offline fallback if flight.json is absent.
    pre = os.path.join(here, "..", "preprocess")
    real = os.path.join(pre, "flight.json")
    default = real if os.path.isfile(real) else os.path.join(pre, "sample_flight.json")
    print(import_flight(os.path.normpath(default)))
