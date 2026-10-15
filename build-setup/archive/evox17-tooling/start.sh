#!/bin/bash
set -euo pipefail
test "$#" = 2 || { echo 'Usage: start.sh evox17-attemptNN /mnt/c/XiaomiBuilds/debug/evox17/BUILD_READY.json'; exit 2; }
B=/mnt/c/XiaomiBuilds/build-setup/evox/evox17
exec python3 -B "$B/launch.py" build "$1" "$2"
