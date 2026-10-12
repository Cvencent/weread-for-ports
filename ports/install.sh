#!/bin/bash
# WeRead for Ports — install by dropping ONE self-contained directory into the
# Ports library, the same way every other port is laid out: a weread/ folder
# plus a Weread.sh launcher that EmulationStation discovers on its own.
#
# The Chromium binary belongs to the Browser port and the login profile belongs
# to the user; this script borrows both and never ships or replaces them.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORTS_DIR="${PORTS_DIR:-/storage/roms/ports}"
WEREAD_DIR="$PORTS_DIR/weread"
BROWSER_DIR="${WEREAD_BROWSER_DIR:-$PORTS_DIR/browser}"

# WeRead renders inside the Browser port's Chromium; refuse to install without it.
if [ ! -x "$BROWSER_DIR/chromium/chrome" ]; then
  echo "❌ Chromium not found at $BROWSER_DIR/chromium/chrome" >&2
  echo "   Install the Browser port first, then run install.sh again." >&2
  exit 1
fi

# One directory holds everything: launcher, helpers and the unpacked extension.
# Replacing it on update is a single directory swap and never touches the login
# profile (which lives in ~/.config, outside this tree).
rm -rf "$WEREAD_DIR"
mkdir -p "$WEREAD_DIR/ext" "$PORTS_DIR/media"

for file in node.sh window_guard.py input_bridge.py cdp.py weread.gptk 操作说明.txt; do
  cp "$ROOT/launcher/$file" "$WEREAD_DIR/$file"
done
for file in content.js shell.css manifest.json background-v8.1.js telemetry-rules.json; do
  cp "$ROOT/extension/$file" "$WEREAD_DIR/ext/$file"
done
cp "$ROOT/ports/Weread.sh" "$PORTS_DIR/Weread.sh"
cp "$ROOT/ports/media/Weread.png" "$PORTS_DIR/media/Weread.png"

# Permissions in two passes instead of a line per file.
find "$WEREAD_DIR" -type f -name '*.py' -exec chmod 755 {} +
chmod 755 "$WEREAD_DIR/node.sh" "$PORTS_DIR/Weread.sh"
chmod 644 "$WEREAD_DIR/weread.gptk" "$WEREAD_DIR/操作说明.txt"
find "$WEREAD_DIR/ext" -type f -exec chmod 644 {} +

# EmulationStation finds Weread.sh on its own; this only adds a curated
# Chinese-named entry with the icon, preserving everything else in the file.
# Set WEREAD_GAMELIST=0 for a pure drop-in with no gamelist edit at all.
if [ "${WEREAD_GAMELIST:-1}" = 1 ]; then
  python3 "$ROOT/ports/update_gamelist.py" \
    "$PORTS_DIR/gamelist.xml" \
    --fragment "$ROOT/ports/gamelist.fragment.xml"
fi

echo "WeRead installed -> $PORTS_DIR/Weread.sh (Chromium and login profile preserved)"
