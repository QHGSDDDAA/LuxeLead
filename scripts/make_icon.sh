#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# make_icon.sh — Generate a macOS .icns file from a 1024×1024 PNG image.
#
# Usage:
#   bash scripts/make_icon.sh input_1024.png [output.icns]
#
# If output is omitted, writes to "luxelead.icns" in the project root.
#
# Requirements:
#   - macOS (uses sips and iconutil which are built-in)
#   - Input PNG must be exactly 1024×1024 pixels
# ---------------------------------------------------------------------------
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 input_1024.png [output.icns]"
  exit 1
fi

INPUT="$1"
OUTPUT="${2:-luxelead.icns}"

if [ ! -f "$INPUT" ]; then
  echo "ERROR: Input file not found: $INPUT"
  exit 1
fi

# Verify dimensions
DIMS=$(sips -g pixelWidth -g pixelHeight "$INPUT" 2>/dev/null | grep -E "pixel(Width|Height)" | awk '{print $2}')
W=$(echo "$DIMS" | head -1)
H=$(echo "$DIMS" | tail -1)
if [ "$W" != "1024" ] || [ "$H" != "1024" ]; then
  echo "ERROR: Input must be 1024×1024, got ${W}×${H}"
  exit 1
fi

echo "Generating .icns from $INPUT ..."

# Create temporary iconset directory
ICONSET_DIR=$(mktemp -d)
trap 'rm -rf "$ICONSET_DIR"' EXIT

# macOS .icns requires these sizes: 16, 32, 64, 128, 256, 512, 1024
# Each size has a 1x and (for large sizes) 2x variant.
for SIZE in 16 32 64 128 256 512 1024; do
  SIZEDIR="$ICONSET_DIR/icon_${SIZE}x${SIZE}"
  mkdir -p "$SIZEDIR"

  # Standard resolution
  if [ "$SIZE" -le 512 ]; then
    sips -z $SIZE $SIZE "$INPUT" --out "$ICONSET_DIR/icon_${SIZE}x${SIZE}.png" &>/dev/null
  fi

  # @2x (HiDPI) — size/2 is the logical size, so we use full res for @2x
  HALF=$((SIZE / 2))
  if [ "$HALF" -ge 16 ] && [ "$SIZE" -le 512 ]; then
    sips -z $SIZE $SIZE "$INPUT" --out "$ICONSET_DIR/icon_${HALF}x${HALF}@2x.png" &>/dev/null
  fi
done

# For the 1024×1024 → 512@2x special case
sips -z 1024 1024 "$INPUT" --out "$ICONSET_DIR/icon_512x512@2x.png" &>/dev/null
# Also the 1024x1024 itself
sips -z 1024 1024 "$INPUT" --out "$ICONSET_DIR/icon_1024x1024.png" &>/dev/null

# Now create the iconset folder that iconutil expects
ICONSET_DIR2=$(mktemp -d)
trap 'rm -rf "$ICONSET_DIR" "$ICONSET_DIR2"' EXIT

ls "$ICONSET_DIR"/*.png | while read -r png; do
  BASENAME=$(basename "$png")
  # iconutil expects files named like: icon_16x16.png, icon_16x16@2x.png, etc.
  cp "$png" "$ICONSET_DIR2/$BASENAME"
done

# If we have icon_1024x1024.png, iconutil might not understand it.
# Let's create a proper .iconset directory structure.
ICONSET_DIR3=$(mktemp -d)
trap 'rm -rf "$ICONSET_DIR" "$ICONSET_DIR2" "$ICONSET_DIR3"' EXIT

# Proper file names for iconutil
for SIZE in 16 32 64 128 256 512; do
  HALF=$((SIZE / 2))
  # @2x comes from the original SIZE source
  if [ -f "$ICONSET_DIR/icon_${SIZE}x${SIZE}.png" ]; then
    cp "$ICONSET_DIR/icon_${SIZE}x${SIZE}.png" "$ICONSET_DIR3/icon_${HALF}x${HALF}@2x.png" 2>/dev/null || true
  fi
done

# Simpler approach: use the standard Apple sizes
rm -rf "$ICONSET_DIR3"
mkdir -p "$ICONSET_DIR3"

# Generate standard sizes
for SIZE in 16 32 128 256 512; do
  sips -z $SIZE $SIZE "$INPUT" --out "$ICONSET_DIR3/icon_${SIZE}x${SIZE}.png" &>/dev/null
  # @2x versions (double the pixel count)
  DSIZE=$((SIZE * 2))
  sips -z $DSIZE $DSIZE "$INPUT" --out "$ICONSET_DIR3/icon_${SIZE}x${SIZE}@2x.png" &>/dev/null
done

# iconutil expects a .iconset folder
ICONSET_FINAL="${ICONSET_DIR3}.iconset"
mv "$ICONSET_DIR3" "$ICONSET_FINAL"

# Generate .icns
iconutil -c icns -o "$OUTPUT" "$ICONSET_FINAL"

echo "Done: $OUTPUT"
ls -lh "$OUTPUT"
