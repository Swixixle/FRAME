#!/usr/bin/env bash
# Copy canonical script into FrameCapture.app Resources (run from repo after editing scripts/frame-capture.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/scripts/frame-capture.sh"
DST="$ROOT/apps/macos/FrameCapture.app/Contents/Resources/frame-capture.sh"
if [[ ! -f "$SRC" ]]; then
  echo "Missing $SRC" >&2
  exit 1
fi
mkdir -p "$(dirname "$DST")"
cp "$SRC" "$DST"
chmod +x "$DST"
echo "Updated: $DST"
