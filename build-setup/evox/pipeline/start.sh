#!/bin/bash
# Start one detached build attempt: bash start.sh 20261105-attempt01 <BUILD_READY.json> (evoxNN-attemptNN for history)
set -euo pipefail
test "$#" = 2 || { echo 'Usage: start.sh YYYYMMDD[.N]-attemptNN /mnt/d/android_rom_building/diagnostics/builds/YYYYMMDD[.N]/BUILD_READY.json'; exit 2; }
B=$(dirname "$(realpath "$0")")
export KLIMT_BUILD=${1%%-attempt*}
exec python3 -B "$B/launch.py" build "$1" "$2"
