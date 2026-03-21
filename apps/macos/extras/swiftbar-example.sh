#!/usr/bin/env bash
#
# SwiftBar / xbar example — shows an "F" in the menu bar and runs Frame capture.
#
# Install:
#   1. Install SwiftBar (https://github.com/swiftbar/SwiftBar).
#   2. Copy this file to your SwiftBar plugin folder, e.g.:
#        ~/Library/Application Support/SwiftBar/Plugins/frame.5s.sh
#   3. Edit FRAME_SCRIPT below to the absolute path of scripts/frame-capture.sh
#   4. chmod +x this file
#
# The "5s" in the filename is a refresh interval; use "1h" if you only want manual clicks.

FRAME_SCRIPT="${FRAME_SCRIPT:-$HOME/src/FRAME/scripts/frame-capture.sh}"

echo "F"
echo "---"
echo "Capture with Frame | bash=$FRAME_SCRIPT terminal=false refresh=false"
echo "Refresh menu | refresh=true"
