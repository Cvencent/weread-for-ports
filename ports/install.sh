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

# Ship exactly what weread.zip ships, so an SSH install and a PortMaster install
# end up with the same tree and share one self-bootstrapping code path: the
# PortMaster metadata, the cover and the gamelist helper all live in weread/,
# where node.sh looks for them on first launch.
cp "$ROOT/ports/port.json" "$WEREAD_DIR/port.json"
cp "$ROOT/ports/media/Weread.png" "$WEREAD_DIR/Weread.png"
cp "$ROOT/ports/update_gamelist.py" "$WEREAD_DIR/update_gamelist.py"
cp "$ROOT/ports/gamelist.fragment.xml" "$WEREAD_DIR/gamelist.fragment.xml"

# Permissions in a few passes instead of a line per file.
find "$WEREAD_DIR" -type f -name '*.py' -exec chmod 755 {} +
chmod 755 "$WEREAD_DIR/node.sh" "$PORTS_DIR/Weread.sh"
find "$WEREAD_DIR" -maxdepth 1 -type f ! -name '*.py' ! -name node.sh \
  -exec chmod 644 {} +
find "$WEREAD_DIR/ext" -type f -exec chmod 644 {} +

# EmulationStation finds Weread.sh on its own; this only adds a curated
# Chinese-named entry with the icon, preserving everything else in the file.
# Set WEREAD_GAMELIST=0 to skip it here -- node.sh then registers the same
# entry from the copy inside weread/ on first launch.
if [ "${WEREAD_GAMELIST:-1}" = 1 ]; then
  python3 "$ROOT/ports/update_gamelist.py" \
    "$PORTS_DIR/gamelist.xml" \
    --fragment "$ROOT/ports/gamelist.fragment.xml"
fi

echo "WeRead installed -> $PORTS_DIR/Weread.sh (Chromium and login profile preserved)"
