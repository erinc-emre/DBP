#!/usr/bin/env bash
# Build an installable Blender add-on zip for the Flight Visualizer.
#
#   ./blender/build_addon.sh   ->   dist/flight_viz_addon.zip
#
# Install in Blender (4.2+):
#   Edit > Preferences > Add-ons > (top-right v) Install from Disk...
#   pick dist/flight_viz_addon.zip, then enable "Flight Visualizer".
#   (In 4.2+ you can also just drag the zip into the Blender window.)
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/.." && pwd)"
out="$root/dist"

mkdir -p "$out"
rm -f "$out/flight_viz_addon.zip"

# Zip the folder itself so it extracts to flight_viz_addon/ (required layout),
# excluding byte-compiled caches.
( cd "$here" && zip -r -q "$out/flight_viz_addon.zip" flight_viz_addon \
    -x '*/__pycache__/*' '*.pyc' '*/.DS_Store' )

echo "Wrote $out/flight_viz_addon.zip"
