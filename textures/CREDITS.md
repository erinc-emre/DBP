# Texture Credits & Sources

## High-resolution Earth maps (8K)
- `earth_day_8k.jpg`  — Earth daymap (8192×4096)
- `earth_night_8k.jpg` — Earth nightmap / city lights (8192×4096)

**Source:** Solar System Scope — https://www.solarsystemscope.com/textures/
**License:** Creative Commons Attribution 4.0 International (CC BY 4.0).
Attribution required if the rendered output is published.

Re-download:
```
curl -L -o earth_day_8k.jpg   https://www.solarsystemscope.com/textures/download/8k_earth_daymap.jpg
curl -L -o earth_night_8k.jpg https://www.solarsystemscope.com/textures/download/8k_earth_nightmap.jpg
```

## Legacy low-res maps (still used for displacement / specular)
- `earthmap.jpg`, `earthbump.jpg`, `earthspec.jpg`, `earthlights.jpg` (1000×500 / 1024×512)
  — from earlier course homework assets.

## Blender wiring
`ProcEarthMat` image datablocks point at the files above:
- `earth_albedo` → `earth_day_8k.jpg`
- `earth_lights` → `earth_night_8k.jpg`
- `earth_spec`   → `earthspec.jpg`  (ocean mask; low-res is fine)
- `earth_bump`   → `earthbump.jpg`  (geo-node displacement; subtle)
