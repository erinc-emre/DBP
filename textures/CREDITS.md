# Texture Credits & Sources

## High-resolution Earth maps (8K, all 8192×4096)
- `earth_day_8k.jpg`    — daymap (albedo)
- `earth_night_8k.jpg`  — nightmap / city lights
- `earth_clouds_8k.jpg` — cloud layer
- `earth_spec_8k.tif`   — specular / ocean mask (roughness)
- `earth_normal_8k.tif` — tangent-space normal map (fine surface detail)

**Source:** Solar System Scope — https://www.solarsystemscope.com/textures/
**License:** Creative Commons Attribution 4.0 International (CC BY 4.0).
Attribution required if the rendered output is published.

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
