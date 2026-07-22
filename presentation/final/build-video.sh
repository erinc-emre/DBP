#!/usr/bin/env bash
# Assemble the final project video from Slidev title cards + the sample render.
#
#   ./presentation/final/build-video.sh
#   -> presentation/final/public/final-video.mp4  (1920x1080, 24 fps)
#
# Segments, in order:
#   1. Title card            (Slidev, 4s)
#   2. Architecture card     (Slidev, 7s)
#   3. Plugin UI walkthrough  -> presentation/final/public/ui-walkthrough.mp4 if present,
#                                otherwise a placeholder card (6s)
#   4. "Sample output" card  (Slidev, 3s)
#   5. Sample render         (presentation/final/public/plugin_sample.mp4)
#   6. Thank-you card        (Slidev, 4s)
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

# Every segment gets 1080p/24fps H.264 video + AAC stereo audio (silent where there
# is none), so the concat below preserves the walkthrough's narration cleanly.
anull="anullsrc=channel_layout=stereo:sample_rate=48000"

card() { # png seconds out  (still image + silent audio)
  ffmpeg -y -loop 1 -framerate 24 -t "$2" -i "$1" -f lavfi -t "$2" -i "$anull" \
    -vf "$pad" -c:v libx264 -r 24 -pix_fmt yuv420p -c:a aac -ar 48000 -ac 2 \
    -shortest "$3" >/dev/null 2>&1
}
clip() { # in out  (keep real audio if present, else add silent)
  if ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0 "$1" | grep -q audio; then
    ffmpeg -y -i "$1" -vf "$pad" -r 24 -c:v libx264 -pix_fmt yuv420p \
      -c:a aac -ar 48000 -ac 2 "$2" >/dev/null 2>&1
  else
    ffmpeg -y -i "$1" -f lavfi -i "$anull" -vf "$pad" -r 24 -c:v libx264 -pix_fmt yuv420p \
      -c:a aac -ar 48000 -ac 2 -map 0:v -map 1:a -shortest "$2" >/dev/null 2>&1
  fi
}

echo "2/4  Building segments..."
card "$tmp/card/1.png" 4 "$tmp/s1.mp4"   # title
card "$tmp/card/2.png" 7 "$tmp/s2.mp4"   # architecture
if [ -f "$pub/ui-walkthrough.mp4" ]; then
  echo "     using your UI walkthrough: public/ui-walkthrough.mp4"
  clip "$pub/ui-walkthrough.mp4" "$tmp/s3.mp4"
else
  echo "     no public/ui-walkthrough.mp4 yet -> using placeholder card"
  card "$tmp/card/3.png" 6 "$tmp/s3.mp4"
fi
card "$tmp/card/4.png" 3 "$tmp/s4.mp4"   # sample caption
clip "$pub/plugin_sample.mp4" "$tmp/s5.mp4"
card "$tmp/card/5.png" 4 "$tmp/s6.mp4"   # thanks

echo "3/4  Concatenating..."
: > "$tmp/list.txt"
for s in s1 s2 s3 s4 s5 s6; do echo "file '$tmp/$s.mp4'" >> "$tmp/list.txt"; done
ffmpeg -y -f concat -safe 0 -i "$tmp/list.txt" -c copy "$pub/final-video.mp4" >/dev/null 2>&1

echo "4/4  Done -> $pub/final-video.mp4"
rm -rf "$tmp"
