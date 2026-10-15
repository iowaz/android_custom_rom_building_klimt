#!/bin/bash
# evox14: stock camera direct-I/O label, append, camera/composer properties,
# citsensorservice startup permissions and MiSys blackbox read. Image ZIP only.
B=/mnt/c/XiaomiBuilds/build-setup/evox; L=/mnt/wsl/evox/logs
rm -f $L/evox14.exit $L/evox14.dstop
bash $B/dwatch.sh evox14 &
bash $B/build.sh evox14 updatepackage
wait
