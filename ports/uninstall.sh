#!/bin/bash
# Remove the EmulationStation entry and the self-contained WeRead directory.
# The Browser port's Chromium and the user's login profile are left untouched.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORTS_DIR="${PORTS_DIR:-/storage/roms/ports}"
WEREAD_DIR="$PORTS_DIR/weread"
BROWSER_DIR="${WEREAD_BROWSER_DIR:-$PORTS_DIR/browser}"

# Drop the curated entry only if this install was the one that added it.
if [ "${WEREAD_GAMELIST:-1}" = 1 ]; then
  python3 "$ROOT/ports/update_gamelist.py" "$PORTS_DIR/gamelist.xml" --remove || true
fi

rm -f "$PORTS_DIR/Weread.sh" "$PORTS_DIR/media/Weread.png"
rm -rf "$WEREAD_DIR"

# One-time cleanup of the old scattered layout (pre-v11): the extension used to
# live under ~/.config and the helpers were dropped into the shared Browser
# directory. Remove only those exact files; Chromium and NSS stay put.
rm -rf "${WEREAD_EXT_DIR:-/storage/.config/weread-ext}"
rm -f "$BROWSER_DIR/cdp.py" "$BROWSER_DIR/weread.gptk" "$BROWSER_DIR/操作说明.txt"

echo "WeRead removed. Chromium, NSS and the login profile were preserved."
