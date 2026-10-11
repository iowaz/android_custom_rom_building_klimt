#!/bin/bash
# evox13 (2026-10-11): log-noise fixes (libui SMPTE 2094-50 check, citsensorservice, MiSys watermark dirs, camera/audio/GPS
# dontaudits, camera and TEE property labels, FeliCa check, USB product); img zip only (updatepackage) under the D: watchdog,
# via build.sh/env.sh (ninja + warm ccache). Start detached: setsid nohup bash build-evox13.sh >/dev/null 2>&1 &
B=/mnt/c/XiaomiBuilds/build-setup/evox; L=/mnt/wsl/evox/logs
rm -f $L/evox13.exit $L/evox13.dstop
bash $B/dwatch.sh evox13 &
bash $B/build.sh evox13 updatepackage
wait
