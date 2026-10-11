#!/bin/bash
# Install or update WeRead for Ports without removing the login profile.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORTS_DIR="${PORTS_DIR:-/storage/roms/ports}"
WEREAD_DIR="$PORTS_DIR/weread"
EXT_DIR="${WEREAD_EXT_DIR:-/storage/.config/weread-ext}"
BROWSER_DIR="${WEREAD_BROWSER_DIR:-$PORTS_DIR/browser}"

mkdir -p "$WEREAD_DIR" "$EXT_DIR" "$PORTS_DIR/media"
cp "$ROOT/ports/Weread.sh" "$PORTS_DIR/Weread.sh"
chmod 755 "$PORTS_DIR/Weread.sh"

for file in node.sh window_guard.py input_bridge.py weread.gptk; do
  cp "$ROOT/launcher/$file" "$WEREAD_DIR/$file"
done
chmod 755 "$WEREAD_DIR/node.sh" "$WEREAD_DIR/window_guard.py" "$WEREAD_DIR/input_bridge.py"
chmod 644 "$WEREAD_DIR/weread.gptk"

for file in content.js shell.css manifest.json background-v8.1.js telemetry-rules.json; do
  cp "$ROOT/extension/$file" "$EXT_DIR/$file"
done
chmod 644 "$EXT_DIR/content.js" "$EXT_DIR/shell.css" "$EXT_DIR/manifest.json" "$EXT_DIR/background-v8.1.js" "$EXT_DIR/telemetry-rules.json"

mkdir -p "$BROWSER_DIR"
cp "$ROOT/launcher/操作说明.txt" "$BROWSER_DIR/操作说明.txt"
cp "$ROOT/launcher/weread.gptk" "$BROWSER_DIR/weread.gptk"
chmod 644 "$BROWSER_DIR/操作说明.txt" "$BROWSER_DIR/weread.gptk"
cp "$ROOT/ports/media/Weread.png" "$PORTS_DIR/media/Weread.png"
chmod 644 "$PORTS_DIR/media/Weread.png"

python3 "$ROOT/ports/update_gamelist.py" \
  "$PORTS_DIR/gamelist.xml" \
  --fragment "$ROOT/ports/gamelist.fragment.xml"

echo "WeRead installed. The existing Chromium, gptokeyb, and login profile were preserved."
