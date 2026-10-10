#!/bin/bash
# WeRead for Ports - EmulationStation entry point.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "$HERE/weread/node.sh"