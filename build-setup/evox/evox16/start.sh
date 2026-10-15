#!/bin/bash
set -euo pipefail
test "$#" = 2 || { echo 'Usage: start.sh evox16-attemptNN /mnt/c/XiaomiBuilds/debug/evox16/BUILD_READY.json'; exit 2; }
B=/mnt/c/XiaomiBuilds/build-setup/evox/evox16
exec python3 -B "$B/launch.py" build "$1" "$2"
