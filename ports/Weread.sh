#!/bin/bash
# PORTMASTER: weread.zip, Weread.sh
# The WeRead port is one self-contained directory (weread/) next to this
# launcher, which is the layout every PortMaster port uses: PortMaster unpacks
# the zip into the ports folder and the frontend runs this script, so there is
# no install step and nothing to type on the device.

if [ -d "/opt/system/Tools/PortMaster/" ]; then
  controlfolder="/opt/system/Tools/PortMaster"
elif [ -d "/opt/tools/PortMaster/" ]; then
  controlfolder="/opt/tools/PortMaster"
elif [ -d "/roms/ports" ]; then
  controlfolder="/roms/ports/PortMaster"
elif [ -d "/roms2/ports" ]; then
  controlfolder="/roms2/ports/PortMaster"
else
  controlfolder="/storage/roms/ports/PortMaster"
fi

# control.txt probes for sudo and touches device globals; never let a nonzero
# status from that probe abort the launcher, so no `set -e` here.
[ -f "$controlfolder/control.txt" ] && source "$controlfolder/control.txt"
get_controls 2>/dev/null

HERE="$(cd "$(dirname "$0")" && pwd)"
exec "$HERE/weread/node.sh"
