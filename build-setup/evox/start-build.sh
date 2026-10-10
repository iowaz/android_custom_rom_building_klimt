#!/bin/bash
# Start build.sh detached: start-build.sh <name> [targets...]
setsid nohup bash /mnt/c/XiaomiBuilds/build-setup/evox/build.sh "$@" >/dev/null 2>&1 < /dev/null &
sleep 10; ls -la /mnt/wsl/evox/src/out; head -3 /mnt/wsl/evox/logs/$1.log
