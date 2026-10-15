#!/bin/bash
set -euo pipefail
test "$#" = 2 || { echo 'Usage: start-precheck.sh evox16-precheckNN /mnt/c/XiaomiBuilds/debug/evox16/PRECHECK_READY.json'; exit 2; }
B=/mnt/c/XiaomiBuilds/build-setup/evox/evox16
exec python3 -B "$B/launch.py" precheck "$1" "$2"
