#!/bin/bash
# evox11 (2026-10-10): thermal profiles + mpbe ioctl + charging fix; img zip only (updatepackage) under the D: watchdog, via build.sh/env.sh (ninja + warm ccache).
# Start detached: setsid nohup bash build-evox11.sh >/dev/null 2>&1 &
B=/mnt/c/XiaomiBuilds/build-setup/evox; L=/mnt/wsl/evox/logs
rm -f $L/evox11.exit $L/evox11.dstop
bash $B/dwatch.sh evox11 &
bash $B/build.sh evox11 updatepackage
wait
