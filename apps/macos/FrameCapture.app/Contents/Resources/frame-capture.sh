#!/usr/bin/env bash
#
# Frame Capture — select a screen region, analyze + route + sign via Frame API, copy receipt URL.
# Requires: bash, curl, screencapture, osascript (macOS). No Node/Python.
#
# Environment (optional):
#   FRAME_API_BASE   — default https://frame-2yxu.onrender.com
#   FRAME_OPEN_BROWSER — set to 1 to open the receipt URL in the default browser after copy
#   FRAME_CAPTURE_PATH — override output PNG path (default /tmp/frame_capture.png)

set -uo pipefail

FRAME_API_BASE="${FRAME_API_BASE:-https://frame-2yxu.onrender.com}"
FRAME_API_BASE="${FRAME_API_BASE%/}"
CAPTURE_PATH="${FRAME_CAPTURE_PATH:-/tmp/frame_capture.png}"
OPEN_BROWSER="${FRAME_OPEN_BROWSER:-0}"

notify() {
  local title="${1:-Frame}"
  local message="${2:-}"
  local subtitle="${3:-}"
  if [[ -n "$subtitle" ]]; then
    osascript -e "display notification \"$(escape_osascript "$message")\" subtitle \"$(escape_osascript "$subtitle")\" with title \"$(escape_osascript "$title")\"" 2>/dev/null || true
  else
    osascript -e "display notification \"$(escape_osascript "$message")\" with title \"$(escape_osascript "$title")\"" 2>/dev/null || true
  fi
}

escape_osascript() {
  printf '%s' "$1" | sed "s/\\\\/\\\\\\\\/g; s/\"/\\\\\"/g"
}

truncate_for_notify() {
  printf '%s' "$1" | tr '\n' ' ' | head -c 200
}

extract_json_string() {
  local key="$1"
  local json="$2"
  local out
  if out=$(printf '%s' "$json" | plutil -extract "$key" raw -n - 2>/dev/null); then
    printf '%s' "$out"
    return 0
  fi
  printf '%s' "$json" | sed -n "s/.*\"${key}\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -1
}

# --- capture (native crosshair); exit 1 if user cancels
if ! screencapture -i "$CAPTURE_PATH"; then
  exit 0
fi

if [[ ! -s "$CAPTURE_PATH" ]]; then
  notify "Frame" "Capture failed — empty file." ""
  exit 1
fi

VERIFY_URL="${FRAME_API_BASE}/v1/analyze-and-verify"
TMP_OUT="$(mktemp -t frame_verify)"
cleanup() {
  rm -f "$TMP_OUT"
}
trap cleanup EXIT

HTTP_CODE=$(curl -sS -o "$TMP_OUT" -w "%{http_code}" \
  -F "file=@${CAPTURE_PATH};type=image/png;filename=frame_capture.png" \
  "$VERIFY_URL") || true

if [[ "$HTTP_CODE" != "200" ]]; then
  ERR_BODY="$(head -c 800 "$TMP_OUT" 2>/dev/null || true)"
  notify "Frame" "Analyze-and-verify failed (HTTP $HTTP_CODE)." "$(truncate_for_notify "$ERR_BODY")"
  exit 1
fi

JSON="$(cat "$TMP_OUT")"
RECEIPT_URL="$(extract_json_string "receiptUrl" "$JSON")"
if [[ -z "$RECEIPT_URL" ]]; then
  RID="$(extract_json_string "receiptId" "$JSON")"
  if [[ -n "$RID" ]]; then
    RECEIPT_URL="${FRAME_API_BASE}/receipt/${RID}"
  fi
fi

if [[ -z "$RECEIPT_URL" ]]; then
  notify "Frame" "No receipt URL in API response." "Check API / signing configuration."
  exit 1
fi

printf '%s' "$RECEIPT_URL" | pbcopy

notify "Frame" "Frame receipt ready — link copied to clipboard" ""

if [[ "$OPEN_BROWSER" == "1" || "$OPEN_BROWSER" == "true" || "$OPEN_BROWSER" == "yes" ]]; then
  open "$RECEIPT_URL" 2>/dev/null || true
fi

exit 0
