#!/usr/bin/env bash
# Make web-ready hero video assets with ffmpeg.
#   make_video_assets.sh INPUT_VIDEO OUTPUT_DIR [--seconds N] [--height H] [--loop-fade]
# Produces OUTPUT_DIR/hero.mp4, hero.webm, hero-poster.jpg (no audio, fast start).
set -euo pipefail

IN="${1:-}"; OUT="${2:-}"; shift 2 || true
SECONDS_MAX=10; HEIGHT=1080; LOOPFADE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --seconds) SECONDS_MAX="$2"; shift 2;;
    --height)  HEIGHT="$2"; shift 2;;
    --loop-fade) LOOPFADE=1; shift;;
    *) echo "Unknown option: $1" >&2; exit 2;;
  esac
done
if [ -z "$IN" ] || [ -z "$OUT" ]; then
  sed -n '2,4p' "$0" | sed 's/^# \{0,1\}//'; exit 2
fi
command -v ffmpeg >/dev/null || { echo "ffmpeg is not installed. Install it (https://ffmpeg.org/download.html) and run again." >&2; exit 1; }
[ -f "$IN" ] || { echo "Input not found: $IN" >&2; exit 1; }
mkdir -p "$OUT"

SCALE="scale=-2:'min($HEIGHT,ih)':flags=lanczos,fps=24,format=yuv420p"
if [ "$LOOPFADE" = 1 ]; then
  F=1   # seconds of cross-fade
  D="$SECONDS_MAX"
  FILTER="[0:v]trim=start=0:end=${D},setpts=PTS-STARTPTS,split[a][b];[a]trim=start=${F}:end=${D},setpts=PTS-STARTPTS[main];[b]trim=start=0:end=${F},setpts=PTS-STARTPTS[head];[main][head]xfade=transition=fade:duration=${F}:offset=$((D-2*F)),${SCALE}[v]"
  VF=(-filter_complex "$FILTER" -map "[v]")
else
  VF=(-t "$SECONDS_MAX" -vf "$SCALE")
fi

echo "Encoding mp4..."
ffmpeg -v error -y -i "$IN" "${VF[@]}" -an -c:v libx264 -profile:v high -preset veryfast -crf 26 -movflags +faststart "$OUT/hero.mp4"
echo "Encoding webm..."
ffmpeg -v error -y -i "$IN" "${VF[@]}" -an -c:v libvpx-vp9 -b:v 0 -crf 34 -deadline good -cpu-used 4 -row-mt 1 "$OUT/hero.webm"
echo "Extracting poster..."
ffmpeg -v error -y -ss 1 -i "$OUT/hero.mp4" -frames:v 1 -q:v 3 "$OUT/hero-poster.jpg"

echo
ls -l "$OUT"/hero.mp4 "$OUT"/hero.webm "$OUT"/hero-poster.jpg | awk '{printf "  %-28s %8.1f KB\n", $NF, $5/1024}'
SIZE=$(wc -c < "$OUT/hero.mp4")
if [ "$SIZE" -gt 4194304 ]; then
  echo "hero.mp4 is over 4 MB. Try --height 720, --seconds 8, or a higher CRF." >&2
fi
echo "Next: convert hero-poster.jpg to WebP/AVIF for production, then record sources and licences in assets/README.md."
