# Texture Credits & Sources

## Highest-res maps in use
- `earth_day_16k.jpg`   — daymap / albedo, **16384×8192** (downsampled from NASA
  Blue Marble Next Gen `world.topo.bathy.200412.3x21600x10800`, ~1.85 km/px source)
- `earth_night_13k.jpg` — nightmap / city lights, **13500×6750** (NASA Earth at Night
  `dnb_land_ocean_ice.2012.13500x6750`)
- `earth_clouds_8k.jpg` — cloud layer (8192×4096, Solar System Scope)
- `earth_spec_8k.tif`   — specular / ocean mask (8192×4096, Solar System Scope)
- `earth_normal_8k.tif` — tangent-space normal map (8192×4096, Solar System Scope)

**Sources:** NASA Visible Earth / Earth Observatory (public domain) for day & night;
Solar System Scope (CC BY 4.0) for clouds/specular/normal. Attribution required for
the SSS maps if the render is published.

All Earth texture nodes use **Cubic** interpolation for smoother close-ups.

## Legacy 8K day/night (superseded)
- `earth_day_8k.jpg`, `earth_night_8k.jpg` (8192×4096, Solar System Scope).

Re-download:
```
B=https://www.solarsystemscope.com/textures/download
curl -L -o earth_day_8k.jpg    $B/8k_earth_daymap.jpg
curl -L -o earth_night_8k.jpg  $B/8k_earth_nightmap.jpg
curl -L -o earth_clouds_8k.jpg $B/8k_earth_clouds.jpg
curl -L -o earth_spec_8k.tif   $B/8k_earth_specular_map.tif
curl -L -o earth_normal_8k.tif $B/8k_earth_normal_map.tif
```

## Elevation / displacement
- `earth_height_8k.png` — real land-elevation heightmap (oceans = 0/flat), 8192×4096,
  downsampled from NASA Blue Marble **GEBCO** topography (`gebco_08_rev_elev`,
  21600×10800). **Public domain** (NASA Earth Observatory / Visible Earth).
  Source: https://visibleearth.nasa.gov/ (image record 73934).
  Used by `ProcEarthGeo` for geometric displacement at amplitude ≈ 0.015
  (~4× real-Earth relief — visible mountains, flat oceans, clean limb from orbit).

## Legacy low-res maps (superseded)
- `earthmap.jpg`, `earthbump.jpg`, `earthspec.jpg`, `earthlights.jpg` (1000×500 / 1024×512)
  — from earlier course homework assets.

## Blender wiring
`ProcEarthMat` image datablocks:
- `earth_albedo` → `earth_day_8k.jpg`
- `earth_lights` → `earth_night_8k.jpg`
- `earth_spec`   → `earth_spec_8k.tif`
- `earth_normal` → `earth_normal_8k.tif` (Normal Map node, uv_map=`UVMap`, TANGENT → BSDF.Normal directly; do NOT route through the Bump node — EEVEE Next errors)
- `earth_bump`   → `earthbump.jpg` (geo-node displacement only)

`CloudMat` on the `Clouds` sphere (radius ≈ Earth×1.03): `earth_clouds_8k.jpg`
→ RGB-to-BW drives a Transparent↔white-Principled mix (render-method independent).

Geo-node `ProcEarthGeo`: UV sphere 256×128; stores a real `UVMap` (FLOAT2 corner)
so tangent-space normal mapping works.
