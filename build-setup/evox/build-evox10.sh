#!/bin/bash
# evox10 (2026-10-10): img zip only (updatepackage) under the D: watchdog, via build.sh/env.sh (ninja + warm ccache).
# Start detached: setsid nohup bash build-evox10.sh >/dev/null 2>&1 &
B=/mnt/c/XiaomiBuilds/build-setup/evox; L=/mnt/wsl/evox/logs
rm -f $L/evox10.exit $L/evox10.dstop
bash $B/dwatch.sh evox10 &
bash $B/build.sh evox10 updatepackage
wait
