#!/bin/bash
# evox12 (2026-10-11): wakeup-source labels, power HAL + camera HAL rules, video calling off; img zip only (updatepackage) under the D: watchdog, via build.sh/env.sh (ninja + warm ccache).
# Start detached: setsid nohup bash build-evox12.sh >/dev/null 2>&1 &
B=/mnt/c/XiaomiBuilds/build-setup/evox; L=/mnt/wsl/evox/logs
rm -f $L/evox12.exit $L/evox12.dstop
bash $B/dwatch.sh evox12 &
bash $B/build.sh evox12 updatepackage
wait
