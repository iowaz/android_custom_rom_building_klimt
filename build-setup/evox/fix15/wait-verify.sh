#!/bin/bash
set -euo pipefail
L=/mnt/wsl/evox/logs
while [ ! -f "$L/evox15.exit" ]; do sleep 20; done
[ "$(cat "$L/evox15.exit")" = 0 ] || { echo "BUILD FAILED"; exit 1; }
echo 'build exited 0; verifying image'
bash /mnt/c/XiaomiBuilds/build-setup/evox/verify-evox15.sh > /mnt/c/XiaomiBuilds/debug/noise15/verify15.log 2>&1
cd /mnt/wsl/evox/src
repo manifest -r -o /mnt/c/XiaomiBuilds/build-setup/evox/fix15/pinned.xml
echo 'image verified and source manifest saved'
