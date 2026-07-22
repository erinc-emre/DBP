#!/usr/bin/env bash
# Assemble the final project video from Slidev title cards + the sample render,
# with a background music track laid over the whole thing.
#
#   ./presentation/final/build-video.sh
#   -> presentation/final/public/final-video.mp4  (1920x1080, 24 fps)
#
# Segments, in order:
#   1. Title card            (Slidev, 4s)
#   2. Architecture card     (Slidev, 7s)
#   3. Plugin UI walkthrough  -> presentation/final/public/ui-walkthrough.mp4 if present,
#                                otherwise a placeholder card (6s)  [audio dropped]
#   4. "Sample output" card  (Slidev, 3s)
#   5. Sample render         (presentation/final/public/plugin_sample.mp4)
#   6. Thank-you card        (Slidev, 4s)
#
# Audio: the segments are silent; the MUSIC track below is looped to cover the
# whole video and faded out at the end. Set MUSIC="" to keep it silent.
#
# Requirements: node deps installed (npm install), playwright-chromium
# (npm i -D playwright-chromium), and ffmpeg on PATH.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
pub="$here/public"
tmp="$(mktemp -d)"
pad="scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x0b1020,setsar=1,format=yuv420p"
MUSIC="$pub/lorenzobuczek-first-flight-226814.mp3"

echo "1/4  Exporting title cards from Slidev..."
( cd "$root" && npx slidev export presentation/final/video.md \
    --format png --output "$tmp/card" --scale 2 --dark >/dev/null )

# Segments are VIDEO-ONLY (audio is replaced by the music track at the end).
card() { # png seconds out
  ffmpeg -y -loop 1 -framerate 24 -t "$2" -i "$1" -vf "$pad" \
    -c:v libx264 -r 24 -pix_fmt yuv420p -an "$3" >/dev/null 2>&1
}
clip() { # in out  (video only, drops any source audio)
  ffmpeg -y -i "$1" -vf "$pad" -r 24 -c:v libx264 -pix_fmt yuv420p -an "$2" >/dev/null 2>&1
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
ffmpeg -y -f concat -safe 0 -i "$tmp/list.txt" -c copy "$tmp/video.mp4" >/dev/null 2>&1

if [ -n "$MUSIC" ] && [ -f "$MUSIC" ]; then
  echo "4/4  Adding music: $(basename "$MUSIC") (looped, fade out)"
  dur="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$tmp/video.mp4")"
  fade_st="$(awk "BEGIN{d=$dur-3; if(d<0)d=0; print d}")"
  ffmpeg -y -i "$tmp/video.mp4" -stream_loop -1 -i "$MUSIC" \
    -filter:a "afade=t=in:st=0:d=1,afade=t=out:st=${fade_st}:d=3" \
    -map 0:v -map 1:a -c:v copy -c:a aac -ar 48000 -ac 2 -shortest \
    "$pub/final-video.mp4" >/dev/null 2>&1
else
  echo "4/4  No music file -> silent video"
  cp "$tmp/video.mp4" "$pub/final-video.mp4"
fi

echo "Done -> $pub/final-video.mp4"
rm -rf "$tmp"
