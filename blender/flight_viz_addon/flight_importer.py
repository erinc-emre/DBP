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

import datetime
import json
import math

import bpy
import mathutils
from bpy.app.handlers import persistent  # noqa: F401  (used by @persistent below)

REAL_EARTH_R = 6_371_000.0  # meters


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
class Config:
    earth_object = "ProcEarth"
    aircraft_root = "B747_8F"  # root empty/object to animate (already in scene)
    aircraft_real_length_m = 76.3  # real Boeing 747-8F length
    aircraft_size_multiplier = 100.0  # draw the plane this many × its real size
    lon_offset_deg = (
        -177.19
    )  # texture longitude calibration (measured from ProcEarth earth_uv)
    # --- Vertical exaggeration (both 1.0 = true-to-scale) ---------------------
    # Keep these EQUAL for a physically consistent scene: real planes cruise just
    # above Everest, so if terrain is exaggerated more than altitude the route is
    # buried in the mountains (and vice-versa).
    altitude_exaggeration = 10.0  # multiplies real flight altitude (& cloud height)
    terrain_exaggeration = 1.0  # multiplies real elevation (geo-node displacement)
    terrain_base_amplitude = 0.00152  # geo-node amplitude for ×1 (real Everest relief)
    earth_geo_nodegroup = "ProcEarthGeo"
    cloud_object = "Clouds"  # cloud shell object (optional)
    cloud_altitude_m = (
        10000.0  # cloud-layer altitude in real meters (scaled by altitude_exaggeration)
    )
    # --------------------------------------------------------------------------
    route_bevel_factor = 0.08  # route thickness as a fraction of aircraft length
    forward_sign = -1.0  # +1 if model nose is +Y, -1 if -Y (B747 GLB nose is -Y)
    bank_gain = 4.0  # roll into turns: bank angle per unit heading-change (0 = none)
    max_bank_deg = 30.0  # clamp the banking to a realistic maximum
    smooth_window = 9  # moving-average window over waypoints (<=2 disables)
    smooth_passes = 3  # number of smoothing passes (more = smoother)
    sync_sun = True  # drive Sun_T3 from the flight's real UTC time (subsolar point)
    sun_object = "Sun_T3"
    make_chase_cam = True
    # chase camera offset from the aircraft, in aircraft lengths (side view frames
    # the plane better than looking straight down the route)
    chase_back_factor = 1.2
    chase_up_factor = 1.2
    chase_side_factor = 2.5
    chase_lens = 20.0  # chase-cam focal length in mm (lower = wider = zoomed out)
    make_hud = True  # on-screen HUD (callsign, altitude, speed, UTC, elapsed)
    hud_object = "FlightHUD"
    place_airports = True  # drop the airport model at the departure & arrival ends
    airport_model_path = "//assets/models/airport.glb"  # '//' = next to the .blend
    airport_target_size = 0.05  # longest dimension of the placed airport, scene units
    airports_collection = "FlightAirports"
    make_subject_light = True  # a fill light on the chase cam so the plane/airport
    subject_light_object = "SubjectFill"  # stay visible on the night side
    subject_light_energy = 0.35  # camera 'headlight' sun strength (W/m^2)
    make_atmosphere = True  # glowing atmosphere halo around the Earth limb
    atmosphere_object = "Atmosphere"
    atmosphere_height_frac = 0.02  # shell radius = R_base * (1 + this)
    atmosphere_color = (0.35, 0.55, 1.0)  # sky blue
    atmosphere_strength = 1.0  # emission strength at the limb
    # thin fresnel band: the low chase cam flies INSIDE the shell, so keep the glow
    # to the grazing limb only (higher would fog the whole sky blue)
    atmosphere_blend = 0.04
    make_grade = True  # view-transform look + a compositor bloom (glare)
    grade_look = "AgX - Medium High Contrast"
    bloom_threshold = 1.5  # only very bright pixels bloom (don't blow out the airport)
    overview_object = "Camera_T3"  # legacy overview camera — removed on build
    frame_start = None  # None -> use scene.frame_start
    base_frames = 96  # animation length (frames) at speed 1.0
    speed = 1.0  # flight animation speed (higher = faster = fewer frames)
    # Animation length: "SPEED" = base_frames/speed (every flight same length);
    # "DURATION" = scale to the real flight time (longer flights => longer clips).
    frame_mode = "SPEED"
    time_compression = 1800.0  # DURATION mode: real seconds shown per playback second


# --------------------------------------------------------------------------- #
# Geo helpers
# --------------------------------------------------------------------------- #
def apply_terrain_exaggeration(cfg):
    """Set the geo-node displacement amplitude from cfg.terrain_exaggeration.

    amplitude = terrain_base_amplitude * terrain_exaggeration
    (base amplitude corresponds to real-Earth relief, i.e. ×1). Returns the
    amplitude applied, or None if the node group / node isn't found.
    """
    ng = bpy.data.node_groups.get(cfg.earth_geo_nodegroup)
    if ng is None:
        return None
    node = next(
        (n for n in ng.nodes if "height_amplitude" in (n.label or "")), None
    ) or ng.nodes.get("Math.001")
    if node is None:
        return None
    amp = cfg.terrain_base_amplitude * cfg.terrain_exaggeration
    node.inputs[1].default_value = amp
    return amp


def set_cloud_altitude(cfg, R_base):
    """Rescale the cloud shell to a realistic altitude (in scene units).

    radius = R_base + cloud_altitude_m * (R_base / 6371 km) * altitude_exaggeration
    so the clouds sit at their real height and track the same vertical
    exaggeration as the flight. Returns the target radius, or None if absent.
    """
    o = bpy.data.objects.get(cfg.cloud_object)
    if o is None:
        return None
    cur = max(o.dimensions) / 2.0
    if cur <= 0:
        return None
    # radius-relative: fraction of Earth radius, same convention as the flight
    target = R_base * (
        1.0 + (cfg.cloud_altitude_m / REAL_EARTH_R) * cfg.altitude_exaggeration
    )
    o.scale = tuple(s * (target / cur) for s in o.scale)
    return target


def set_aircraft_scale(cfg, R_base):
    """Scale the aircraft to  aircraft_size_multiplier × real  at Earth scale.

    length = aircraft_real_length_m * aircraft_size_multiplier * (R_base / 6371 km)
    Returns the target length (units), or None if the aircraft isn't found.
    """
    root = bpy.data.objects.get(cfg.aircraft_root)
    if root is None:
        return None
    cur = aircraft_length(cfg)
    if cur <= 0:
        return None
    target = (
        cfg.aircraft_real_length_m
        * cfg.aircraft_size_multiplier
        * (R_base / REAL_EARTH_R)
    )
    root.scale = tuple(s * (target / cur) for s in root.scale)
    bpy.context.view_layer.update()
    return target


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
            avg = acc / (2 * k + 1)
            # Keep the smoothed point on its own shell: averaging Cartesian
            # positions across a big coverage gap would otherwise sag the path
            # deep INSIDE the Earth. Smooth the direction, preserve the radius.
            r = cur[i].length
            avg_len = avg.length
            nxt[i] = avg * (r / avg_len) if avg_len > 1e-9 else cur[i]
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


def project_waypoint(wp, off, ground_r, alt_units_per_m, center):
    """Place a waypoint at `altitude` above the LOCAL ground beneath it:

        radius = ground_r(direction) + alt_m * alt_units_per_m

    `ground_r(dir)` is the displaced Earth's surface radius under that direction,
    so the flight is always referenced to the closest earth surface (it never
    dips into terrain, whatever the sea-level datum is). `alt_units_per_m` scales
    real metres to scene units, i.e. `R_base * exaggeration / R_earth`.
    """
    d = _unit_dir(wp["lat"], wp["lon"], off)
    radius = ground_r(d) + wp["alt_m"] * alt_units_per_m
    return center + radius * d


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
    obj = bpy.data.objects.get(name)
    if obj is None:
        return
    data = obj.data  # mesh/curve/camera/... referenced by the object
    bpy.data.objects.remove(obj, do_unlink=True)
    # Purge the now-orphaned datablock so repeated rebuilds don't pile up
    # ChaseCam.001, .002, FlightRoute.001, ... (which then collide on .new()).
    if data is not None and data.users == 0:
        col = {
            "Mesh": bpy.data.meshes,
            "Curve": bpy.data.curves,
            "TextCurve": bpy.data.curves,
            "Camera": bpy.data.cameras,
            "Light": bpy.data.lights,
        }.get(type(data).__name__)
        if col is not None:
            col.remove(data)


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
    # thin trail, sized relative to the aircraft so it reads as a line, not a tube
    cu.bevel_depth = aircraft_length(cfg) * cfg.route_bevel_factor
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
    a, b = pts[lo], pts[hi]
    # Interpolate ALONG THE SPHERE (normalized lerp), not as a straight chord:
    # big coverage gaps in the track would otherwise cut through the Earth.
    ra, rb = a.length, b.length
    if ra > 1e-9 and rb > 1e-9:
        d = a.normalized().lerp(b.normalized(), f)
        if d.length > 1e-9:
            return d.normalized() * (ra + (rb - ra) * f)
    return a.lerp(b, f)


def resample_uniform(pts, trel, n, window, passes):
    """Resample a time-parametrised path to `n` evenly-time-spaced points, then
    smooth them.

    Real ADS-B tracks are sampled very unevenly (dense clusters + multi-minute
    gaps), so the piecewise-linear velocity jumps at every waypoint — the aircraft
    appears to surge and stall. Sampling on a uniform time grid and smoothing that
    grid removes those velocity discontinuities, giving even motion. Endpoints are
    preserved (smooth_points holds them fixed).
    """
    total = trel[-1]
    if n < 2 or total <= 0:
        return list(pts), list(trel)
    utrel = [total * j / (n - 1) for j in range(n)]
    upts = [position_at(pts, trel, t) for t in utrel]
    upts = smooth_points(upts, window, passes)
    return upts, utrel


def reparametrize_arc(pts, trel, n):
    """Resample a path to `n` points evenly spaced in ARC LENGTH (constant speed).

    Time-based playback surges and stalls wherever the raw track's speed varies or
    (worse) the reported position freezes then jumps. Driving the aircraft by
    distance instead makes it glide at a constant on-screen speed. Returns
    (apts, atime): the evenly-spaced positions and the real flight time at each,
    so the HUD/labels still show the true clock at every point.
    """
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + (pts[i] - pts[i - 1]).length)
    total_len = cum[-1]
    if n < 2 or total_len <= 0:
        return list(pts), list(trel)
    apts, atime = [], []
    j = 0
    for k in range(n):
        s = total_len * k / (n - 1)
        while j < len(cum) - 2 and cum[j + 1] < s:
            j += 1
        seg = cum[j + 1] - cum[j]
        f = (s - cum[j]) / seg if seg > 0 else 0.0
        apts.append(pts[j].lerp(pts[j + 1], f))
        atime.append(trel[j] + (trel[j + 1] - trel[j]) * f)
    return apts, atime


def _orient(fwd, radial, forward_sign, bank=0.0):
    """Orientation matrix: nose along `fwd` (so pitch follows the climb/descent),
    up = local radial, optionally rolled by `bank` radians about the nose to lean
    the aircraft into a turn."""
    fwd = fwd * forward_sign
    if fwd.length < 1e-6:
        fwd = mathutils.Vector((0, 1, 0))
    fwd.normalize()
    up = (radial - fwd * radial.dot(fwd)).normalized()
    if bank:
        up = (mathutils.Matrix.Rotation(bank, 4, fwd) @ up).normalized()
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
    frames = list(range(f0, f1 + 1))
    locs = [position_at(pts, trel, (f - f0) / nf * total) for f in frames]
    n = len(locs)
    max_bank = math.radians(cfg.max_bank_deg)
    for i, f in enumerate(frames):
        p = locs[i]
        nxt = locs[i + 1] if i + 1 < n else 2 * p - locs[i - 1]
        prv = locs[i - 1] if i > 0 else 2 * p - nxt
        radial = p.normalized()
        # signed heading change in the tangent plane -> bank into the turn
        a = prv - p
        b = nxt - p
        a = a - radial * a.dot(radial)
        b = b - radial * b.dot(radial)
        if a.length > 1e-9 and b.length > 1e-9:
            a.normalize()
            b.normalize()
            # angle from -a (incoming heading) to b (outgoing), signed about radial
            dpsi = math.atan2((-a).cross(b).dot(radial), (-a).dot(b))
        else:
            dpsi = 0.0
        bank = max(-max_bank, min(max_bank, -cfg.bank_gain * dpsi))
        ac.location = p
        ac.rotation_euler = _orient(nxt - p, radial, cfg.forward_sign, bank)
        ac.keyframe_insert("location", frame=f)
        ac.keyframe_insert("rotation_euler", frame=f)
    return ac


def aircraft_length(cfg):
    """Longest world-space dimension of the aircraft (across all child meshes)."""
    root = bpy.data.objects[cfg.aircraft_root]
    dg = bpy.context.evaluated_depsgraph_get()
    coords = []

    def walk(ob):
        if ob.type == "MESH":
            oe = ob.evaluated_get(dg)
            for v in oe.bound_box:
                coords.append(ob.matrix_world @ mathutils.Vector(v))
        for c in ob.children:
            walk(c)

    walk(root)
    if not coords:
        return 1.0
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    return max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))


def build_terrain_lookup(cfg, center):
    """Return  direction -> local surface radius  of the displaced Earth.

    Evaluates the geometry-node-displaced Earth mesh once and indexes its
    vertices by outward direction in a KD-tree, so callers can ask "how high is
    the ground beneath this point?" cheaply. Falls back to a flat 0 if the Earth
    isn't found.
    """
    earth = bpy.data.objects.get(cfg.earth_object)
    if earth is None:
        return lambda d: 0.0
    dg = bpy.context.evaluated_depsgraph_get()
    ev = earth.evaluated_get(dg)
    me = ev.to_mesh()
    mw = earth.matrix_world
    kd = mathutils.kdtree.KDTree(len(me.vertices))
    radii = []
    for i, v in enumerate(me.vertices):
        w = mw @ v.co - center
        r = w.length
        kd.insert(w / r if r > 1e-9 else mathutils.Vector((0, 0, 1)), i)
        radii.append(r)
    kd.balance()
    ev.to_mesh_clear()

    def query(direction):
        _co, idx, _dist = kd.find(direction.normalized())
        return radii[idx]

    return query


def build_chase_cam(cfg, pts, trel, f0, f1, center):
    _remove("ChaseCam")
    cdata = bpy.data.cameras.new("ChaseCam")
    cdata.lens = cfg.chase_lens
    L = aircraft_length(cfg)
    back = L * cfg.chase_back_factor
    up_off = L * cfg.chase_up_factor
    side = L * cfg.chase_side_factor
    cdata.clip_start = max(L * 0.02, 1e-6)  # tiny aircraft -> small near clip
    chase = bpy.data.objects.new("ChaseCam", cdata)
    bpy.context.scene.collection.objects.link(chase)
    chase.rotation_mode = "XYZ"
    ground_r = build_terrain_lookup(cfg, center)  # local terrain height lookup
    total = trel[-1]
    nf = max(f1 - f0, 1)
    for f in range(f0, f1 + 1):
        tr = (f - f0) / nf * total
        p = position_at(pts, trel, tr)
        pn = position_at(pts, trel, min(tr + total * 0.01, total))
        fwd = pn - p
        fwd = fwd.normalized() if fwd.length > 1e-6 else mathutils.Vector((0, 1, 0))
        up = (p - center).normalized()
        right = fwd.cross(up).normalized()
        loc = p + right * side + up * up_off - fwd * back
        # Keep the chase cam above the ground at takeoff/landing: there the plane is
        # near 0 altitude and `fwd` tilts radially (climb/descent), so the -fwd*back
        # term pulls the camera inward, below the surface. Clamp it to sit at least
        # `up_off` above the terrain directly beneath it (and never below the
        # aircraft), so it never clips underground for any exaggeration setting.
        rel = loc - center
        r_min = max((p - center).length, ground_r(rel) + up_off)
        if rel.length < r_min:
            loc = center + rel.normalized() * r_min
        chase.location = loc
        # Aim the camera AT the aircraft (so the plane stays framed) while keeping the
        # horizon LEVEL to the Earth: up = local radial, so the camera's width axis
        # (local X) stays parallel to the surface (no banking/roll) and the camera
        # only pitches up/down to follow the plane.
        up_r = (loc - center).normalized()  # Earth radial at the camera = "up"
        look = (p - chase.location).normalized()  # look straight at the aircraft
        right_c = look.cross(up_r)  # perpendicular to radial => width stays level
        if right_c.length > 1e-6:
            right_c.normalize()
            up_c = right_c.cross(look)  # re-orthogonalized camera up
            zc = -look  # camera looks down its local -Z
            rot = mathutils.Matrix(
                (
                    (right_c.x, up_c.x, zc.x),
                    (right_c.y, up_c.y, zc.y),
                    (right_c.z, up_c.z, zc.z),
                )
            )
            chase.rotation_euler = rot.to_euler()
        else:  # looking (near) straight along the radial: roll is undefined
            chase.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
        chase.keyframe_insert("location", frame=f)
        chase.keyframe_insert("rotation_euler", frame=f)
    return chase


def _sample_scalar(times, vals, tr):
    """Linear interpolation of a scalar field sampled at `times` (like position_at)."""
    if tr <= times[0]:
        return vals[0]
    if tr >= times[-1]:
        return vals[-1]
    lo, hi = 0, len(times) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if times[mid] <= tr:
            lo = mid
        else:
            hi = mid
    span = times[hi] - times[lo]
    f = (tr - times[lo]) / span if span > 0 else 0.0
    return vals[lo] + (vals[hi] - vals[lo]) * f


def _mmss(seconds):
    s = max(0, int(round(seconds)))
    return f"{s // 60:02d}:{s % 60:02d}"


def build_hud(cfg, wps, atime, f0, f1, camera, callsign):
    """Create a screen-space HUD (a Font object parented to the camera) and store
    the per-frame text on the scene. A frame-change handler swaps the text as the
    animation plays (works during animation renders too).
    """
    _remove(cfg.hud_object)
    cur = bpy.data.curves.new(cfg.hud_object, type="FONT")
    cur.size = 0.00085
    cur.align_x = "LEFT"
    cur.align_y = "TOP"
    obj = bpy.data.objects.new(cfg.hud_object, cur)
    bpy.context.scene.collection.objects.link(obj)
    # Parent to the camera and sit just in front of it (beyond the near clip, but
    # closer than the aircraft) so it reads as a fixed top-left on-screen overlay.
    obj.parent = camera
    obj.location = (-0.0110, 0.0064, -0.013)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.hide_render = False
    mat = _emissive(
        cfg.hud_object + "_mat", (1.0, 1.0, 1.0), 1.6
    )  # unlit, always legible
    cur.materials.append(mat)

    # `atime` gives the real flight time at each arc-length sample; the aircraft
    # moves by frame fraction along those samples, so map frame -> atime -> the true
    # clock, then sample alt/speed on the waypoints' OWN times (wtrel).
    wtrel = [w["t_rel"] for w in wps]
    alt = [w["alt_m"] for w in wps]
    spd = [w.get("speed_mps", 0.0) or 0.0 for w in wps]
    t0 = wps[0]["t"]
    total = wtrel[-1]
    na = len(atime)
    nf = max(f1 - f0, 1)
    frames = {}
    for f in range(f0, f1 + 1):
        fi = (f - f0) / nf * (na - 1)  # arc-sample index for this frame
        i0 = int(fi)
        i1 = min(i0 + 1, na - 1)
        tr = atime[i0] + (atime[i1] - atime[i0]) * (fi - i0)
        a = _sample_scalar(wtrel, alt, tr)
        kmh = _sample_scalar(wtrel, spd, tr) * 3.6
        utc = datetime.datetime.fromtimestamp(t0 + tr, tz=datetime.timezone.utc)
        frames[str(f)] = (
            f"{callsign}\n"
            f"ALT {a:6.0f} m\n"
            f"SPD {kmh:5.0f} km/h\n"
            f"UTC {utc:%H:%M:%S}\n"
            f"T+  {_mmss(tr)} / {_mmss(total)}"
        )
    bpy.context.scene["flightviz_hud"] = json.dumps(frames)
    obj.data.body = frames.get(str(f0), "")
    return obj


@persistent
def hud_frame_handler(scene, depsgraph=None):
    """Swap the HUD text to match the current frame (registered as frame_change_post)."""
    data = scene.get("flightviz_hud")
    if not data:
        return
    obj = bpy.data.objects.get(Config.hud_object)
    if obj is None or obj.type != "FONT":
        return
    try:
        frames = json.loads(data)
    except (TypeError, ValueError):
        return
    obj.data.body = frames.get(str(scene.frame_current), obj.data.body)


def _clear_airports(cfg):
    coll = bpy.data.collections.get(cfg.airports_collection)
    if coll is None:
        return
    for o in list(coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(coll)


def place_airports(cfg, pts, center):
    """Import the airport model and drop a copy at the departure and arrival ends,
    each seated on the surface, up = Earth radial, runway aligned to the flight
    direction (takeoff/landing heading)."""
    import os

    _clear_airports(cfg)
    path = bpy.path.abspath(cfg.airport_model_path)
    if not cfg.place_airports or not os.path.isfile(path):
        return None
    coll = bpy.data.collections.new(cfg.airports_collection)
    bpy.context.scene.collection.children.link(coll)
    ground_r = build_terrain_lookup(cfg, center)
    _place_one(
        cfg, coll, path, pts[0], pts[1] - pts[0], center, ground_r, "AirportDepart"
    )
    _place_one(
        cfg, coll, path, pts[-1], pts[-1] - pts[-2], center, ground_r, "AirportArrive"
    )
    return coll


def _place_one(cfg, coll, path, at_point, fwd_vec, center, ground_r, name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    imported = [o for o in bpy.data.objects if o not in before]
    if not imported:
        return None
    # world bbox of the freshly-imported model (sits at the origin)
    mn = mathutils.Vector((1e18, 1e18, 1e18))
    mx = -mn
    for o in imported:
        if o.type != "MESH":
            continue
        for c in o.bound_box:
            w = o.matrix_world @ mathutils.Vector(c)
            for i in range(3):
                mn[i] = min(mn[i], w[i])
                mx[i] = max(mx[i], w[i])
    dims = mx - mn
    scale = cfg.airport_target_size / (max(dims.x, dims.y, dims.z) or 1.0)

    root = bpy.data.objects.new(name, None)  # empty parent for the whole model
    coll.objects.link(root)
    root.rotation_mode = "XYZ"
    for o in imported:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
        if o.parent is None:
            o.parent = root
    root.scale = (scale, scale, scale)

    # orientation: model +Z -> Earth radial (up), model +Y (runway) -> flight tangent
    up_r = (at_point - center).normalized()
    fwd = fwd_vec - fwd_vec.dot(up_r) * up_r
    fwd = fwd.normalized() if fwd.length > 1e-6 else up_r.orthogonal().normalized()
    right = fwd.cross(up_r).normalized()
    root.rotation_euler = mathutils.Matrix(
        (
            (right.x, fwd.x, up_r.x),
            (right.y, fwd.y, up_r.y),
            (right.z, fwd.z, up_r.z),
        )
    ).to_euler()
    # seat the model's base on the local ground surface
    root.location = center + up_r * (ground_r(up_r) - mn.z * scale)
    return root


def apply_grade(cfg):
    """Light color grade: a contrasty view look + a compositor bloom (glare) so the
    night city lights and the atmosphere limb bloom softly."""
    scn = bpy.context.scene
    if not cfg.make_grade:
        return None
    try:
        scn.view_settings.look = cfg.grade_look
    except (TypeError, AttributeError):
        pass
    # Bloom via a compositor Glare node. Blender 5.x stores the compositor as a
    # node group (scene.compositing_node_group) with a Group Output and a
    # socket-based Glare; older versions use scene.node_tree + a Composite node.
    try:
        _build_bloom(scn, cfg)
    except Exception:
        pass  # bloom is optional; the view look above is the main grade
    return None


def _set_socket(node, name, value):
    sock = node.inputs.get(name)
    if sock is not None:
        try:
            sock.default_value = value
        except (TypeError, ValueError):
            pass


def _build_bloom(scn, cfg):
    if hasattr(scn, "compositing_node_group"):  # Blender 5.x node-group compositor
        ng = bpy.data.node_groups.new("FlightCompositor", "CompositorNodeTree")
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        rl = ng.nodes.new("CompositorNodeRLayers")
        glare = ng.nodes.new("CompositorNodeGlare")
        glare.name = "FlightGlare"
        go = ng.nodes.new("NodeGroupOutput")
        ng.links.new(rl.outputs["Image"], glare.inputs["Image"])
        ng.links.new(glare.outputs["Image"], go.inputs[0])
        _set_socket(glare, "Type", "Bloom")  # 5.x menu-socket label
        _set_socket(glare, "Threshold", cfg.bloom_threshold)
        _set_socket(glare, "Size", 0.7)
        scn.compositing_node_group = ng
    else:  # legacy compositor
        scn.use_nodes = True
        nt = scn.node_tree
        rl = next((n for n in nt.nodes if n.type == "R_LAYERS"), None) or nt.nodes.new(
            "CompositorNodeRLayers"
        )
        comp = next(
            (n for n in nt.nodes if n.type == "COMPOSITE"), None
        ) or nt.nodes.new("CompositorNodeComposite")
        glare = nt.nodes.new("CompositorNodeGlare")
        glare.name = "FlightGlare"
        glare.glare_type = "BLOOM"
        glare.threshold = cfg.bloom_threshold
        nt.links.new(rl.outputs["Image"], glare.inputs["Image"])
        nt.links.new(glare.outputs["Image"], comp.inputs["Image"])


def build_atmosphere(cfg, R_base, center):
    """A slightly larger sphere around the Earth that glows blue at the limb
    (fresnel-driven emission, transparent face-on) — a cheap atmosphere halo."""
    _remove(cfg.atmosphere_object)
    if not cfg.make_atmosphere:
        return None
    r = R_base * (1.0 + cfg.atmosphere_height_frac)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=r, location=center)
    obj = bpy.context.active_object
    obj.name = cfg.atmosphere_object
    for poly in obj.data.polygons:
        poly.use_smooth = True

    mat = bpy.data.materials.get(
        cfg.atmosphere_object + "_mat"
    ) or bpy.data.materials.new(cfg.atmosphere_object + "_mat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    trans = nt.nodes.new("ShaderNodeBsdfTransparent")
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs[0].default_value = (*cfg.atmosphere_color, 1.0)
    emit.inputs[1].default_value = cfg.atmosphere_strength
    lw = nt.nodes.new("ShaderNodeLayerWeight")  # Fresnel output is high at the limb
    lw.inputs[0].default_value = cfg.atmosphere_blend
    nt.links.new(lw.outputs[0], mix.inputs[0])  # fresnel -> mix factor
    nt.links.new(trans.outputs[0], mix.inputs[1])  # face-on -> transparent
    nt.links.new(emit.outputs[0], mix.inputs[2])  # grazing (limb) -> emission
    nt.links.new(mix.outputs[0], out.inputs[0])
    obj.data.materials.clear()
    obj.data.materials.append(mat)

    # EEVEE transparency (attr names differ across 4.x / EEVEE-Next)
    for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
        try:
            setattr(mat, attr, val)
        except (AttributeError, TypeError):
            pass
    mat.use_backface_culling = False
    obj.hide_select = True
    return obj


def build_subject_light(cfg, camera):
    """A soft 'headlight' sun parented to the chase cam so the aircraft (and the
    airport at takeoff/landing) stay visible on the night side. A sun (no distance
    falloff) lights the subject and the ground evenly — a point light blows out the
    near ground because it's much closer than the plane.
    """
    _remove(cfg.subject_light_object)
    if not cfg.make_subject_light or camera is None:
        return None
    ld = bpy.data.lights.new(cfg.subject_light_object, type="SUN")
    ld.energy = cfg.subject_light_energy
    ld.angle = math.radians(5.0)  # soft-ish shadows
    obj = bpy.data.objects.new(cfg.subject_light_object, ld)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = camera  # rides with the camera; sun -Z aligns with the view
    obj.rotation_euler = (0.0, 0.0, 0.0)
    return obj


def _subsolar_dir(t_unix, off):
    """Unit vector (in the scene's geo convention) pointing at the subsolar point
    for a given UTC Unix time: the spot on Earth where the Sun is overhead.

    lon_subsolar = (12 - UTC_hours) * 15  (ignores the equation of time, ~<=15 min)
    lat_subsolar = solar declination for the date.
    """

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
    for name in (
        "FlightRoute",
        "ChaseCam",
        cfg.hud_object,
        cfg.subject_light_object,
        cfg.atmosphere_object,
        cfg.overview_object,
    ):
        _remove(name)
    _clear_airports(cfg)
    bpy.context.scene.pop("flightviz_hud", None)
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
    # Animation length: either a fixed clip divided by speed, or scaled to the
    # real flight duration (so a 10 h flight plays longer than a 30 min hop).
    if cfg.frame_mode == "DURATION":
        real_dur = wps[-1]["t_rel"] - wps[0]["t_rel"]  # seconds of real flight
        playback_s = real_dur / max(cfg.time_compression, 1e-3)
        total_frames = max(2, round(playback_s * scn.render.fps))
    else:  # "SPEED"
        total_frames = max(2, round(cfg.base_frames / max(cfg.speed, 1e-3)))
    f1 = f0 + total_frames - 1
    scn.frame_end = f1

    # Apply the configured terrain exaggeration before measuring the Earth.
    apply_terrain_exaggeration(cfg)

    earth = bpy.data.objects[cfg.earth_object]
    center = earth.matrix_world.translation.copy()
    R_base = earth_base_radius(earth)
    set_aircraft_scale(cfg, R_base)  # size the plane before route/chase measure it
    set_cloud_altitude(cfg, R_base)  # keep the cloud shell at a realistic height
    # Altitude is radius-relative: a fraction of the Earth radius per real meter.
    # (altitude_exaggeration = 1.0 keeps it realistic; raise it only to exaggerate.)
    alt_frac_per_m = cfg.altitude_exaggeration / REAL_EARTH_R
    alt_units_per_m = R_base * alt_frac_per_m  # real metres -> scene units

    # Reference every waypoint to the LOCAL ground beneath it (closest earth
    # surface), so the flight never dips into terrain regardless of the datum.
    ground_r = build_terrain_lookup(cfg, center)

    off = cfg.lon_offset_deg
    pts = [project_waypoint(w, off, ground_r, alt_units_per_m, center) for w in wps]
    trel = [w["t_rel"] for w in wps]

    # Smooth out raw ADS-B jitter so the route line and the aircraft motion
    # read as a clean flight path rather than a noisy GPS trace.
    pts = smooth_points(pts, cfg.smooth_window, cfg.smooth_passes)

    # The raw track is sampled very unevenly (dense clusters + multi-minute gaps),
    # which makes the time-parametrised motion surge and stall. Resample onto a
    # uniform time grid and smooth it over ~2x the per-frame time step, so the
    # motion the viewer sees (frame to frame) is even rather than lurching.
    total_rel = trel[-1]
    grid_dt = 5.0  # seconds between uniform samples
    n_uniform = min(6000, max(len(pts), int(total_rel / grid_dt) + 1))
    frame_dt = total_rel / max(f1 - f0, 1)  # real seconds per animation frame
    win = max(cfg.smooth_window, int(round(2.0 * frame_dt / grid_dt)) | 1)
    pts, trel = resample_uniform(pts, trel, n_uniform, win, cfg.smooth_passes)

    # Drive the aircraft by DISTANCE, not time: reparametrise to constant arc-length
    # so it glides at a steady on-screen speed and never stalls/surges (robust even
    # if the raw track froze then jumped). `atime` keeps the real clock per sample
    # for the HUD; `trel` becomes a plain sample index (linear -> constant speed).
    pts, atime = reparametrize_arc(pts, trel, len(pts))
    trel = list(range(len(pts)))

    build_atmosphere(cfg, R_base, center)  # glowing limb halo around the Earth
    apply_grade(cfg)  # view look + bloom
    # (data["origin"]/["destination"] are metadata only — not drawn in the scene.)
    place_airports(cfg, pts, center)  # airport model at the departure & arrival ends
    build_route(cfg, pts)
    animate_aircraft(cfg, pts, trel, f0, f1)
    if cfg.sync_sun:
        animate_sun(cfg, wps, f0, f1)
    _remove(cfg.overview_object)  # drop the legacy overview camera; chase cam only
    callsign = data.get("meta", {}).get("callsign") or "FLIGHT"
    if cfg.make_chase_cam:
        chase = build_chase_cam(cfg, pts, trel, f0, f1, center)
        scn.camera = chase  # make the chase cam the active/rendered camera
        build_subject_light(cfg, chase)  # keep the plane/airport lit at night
        if cfg.make_hud:
            build_hud(cfg, wps, atime, f0, f1, chase, callsign)
    else:
        _remove(cfg.hud_object)  # no camera -> no HUD
        scn.pop("flightviz_hud", None)

    scn.frame_set(f0)
    max_alt = max(w["alt_m"] for w in wps)
    return {
        "waypoints": len(pts),
        "earth_base_radius": round(R_base, 3),
        "max_alt_offset": round(R_base * alt_frac_per_m * max_alt, 5),
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
