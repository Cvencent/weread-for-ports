#!/bin/bash
# Remove the EmulationStation entry and installed WeRead files.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORTS_DIR="${PORTS_DIR:-/storage/roms/ports}"
EXT_DIR="${WEREAD_EXT_DIR:-/storage/.config/weread-ext}"
BROWSER_DIR="${WEREAD_BROWSER_DIR:-$PORTS_DIR/browser}"
python3 "$ROOT/ports/update_gamelist.py" "$PORTS_DIR/gamelist.xml" --remove
rm -f "$PORTS_DIR/Weread.sh" "$PORTS_DIR/media/Weread.png"
rm -rf "$PORTS_DIR/weread" "$EXT_DIR"
# Drop the helper files install.sh placed in the browser directory, but keep
# Chromium, the NSS libraries and the extracted browser itself.
rm -f "$BROWSER_DIR/cdp.py" "$BROWSER_DIR/weread.gptk" "$BROWSER_DIR/操作说明.txt"
echo "WeRead files removed. Login profile and extracted browser files were preserved."
