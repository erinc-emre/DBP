#!/usr/bin/env bash
# Assemble the final project video from Slidev title cards + the sample render.
#
#   ./presentation/final/build-video.sh
#   -> presentation/final/public/final-video.mp4  (1920x1080, 24 fps)
#
# Segments, in order:
#   1. Title card            (Slidev, 4s)
#   2. Plugin UI walkthrough  -> presentation/final/public/ui-walkthrough.mp4 if present,
#                                otherwise a placeholder card (6s)
#   3. "Sample output" card  (Slidev, 3s)
#   4. Sample render         (presentation/final/public/plugin_sample.mp4)
#   5. Thank-you card        (Slidev, 4s)
#
# Requirements: node deps installed (npm install), playwright-chromium
# (npm i -D playwright-chromium), and ffmpeg on PATH.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
pub="$here/public"
tmp="$(mktemp -d)"
pad="scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x0b1020,setsar=1,format=yuv420p"

echo "1/4  Exporting title cards from Slidev..."
( cd "$root" && npx slidev export presentation/final/video.md \
    --format png --output "$tmp/card" --scale 2 --dark >/dev/null )

card() { # png seconds out
  ffmpeg -y -loop 1 -framerate 24 -t "$2" -i "$1" -vf "$pad" \
    -c:v libx264 -r 24 -pix_fmt yuv420p -an "$3" >/dev/null 2>&1
}
clip() { # in out
  ffmpeg -y -i "$1" -vf "$pad" -r 24 -c:v libx264 -pix_fmt yuv420p -an "$2" >/dev/null 2>&1
}

echo "2/4  Building segments..."
card "$tmp/card/1.png" 4 "$tmp/s1.mp4"
if [ -f "$pub/ui-walkthrough.mp4" ]; then
  echo "     using your UI walkthrough: public/ui-walkthrough.mp4"
  clip "$pub/ui-walkthrough.mp4" "$tmp/s2.mp4"
else
  echo "     no public/ui-walkthrough.mp4 yet -> using placeholder card"
  card "$tmp/card/2.png" 6 "$tmp/s2.mp4"
fi
card "$tmp/card/3.png" 3 "$tmp/s3.mp4"
clip "$pub/plugin_sample.mp4" "$tmp/s4.mp4"
card "$tmp/card/4.png" 4 "$tmp/s5.mp4"

echo "3/4  Concatenating..."
: > "$tmp/list.txt"
for s in s1 s2 s3 s4 s5; do echo "file '$tmp/$s.mp4'" >> "$tmp/list.txt"; done
ffmpeg -y -f concat -safe 0 -i "$tmp/list.txt" -c copy "$pub/final-video.mp4" >/dev/null 2>&1

echo "4/4  Done -> $pub/final-video.mp4"
rm -rf "$tmp"
