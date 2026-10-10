#!/bin/bash
# Remove the EmulationStation entry and installed WeRead files.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORTS_DIR="${PORTS_DIR:-/storage/roms/ports}"
python3 "$ROOT/ports/update_gamelist.py" "$PORTS_DIR/gamelist.xml" --remove
rm -f "$PORTS_DIR/Weread.sh" "$PORTS_DIR/media/Weread.png"
rm -rf "$PORTS_DIR/weread"
echo "WeRead files removed. Login profile and extracted browser files were preserved."