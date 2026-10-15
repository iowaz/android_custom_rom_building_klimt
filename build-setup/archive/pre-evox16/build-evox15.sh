#!/bin/bash
# evox15: device health current/estimate correction plus reviewed experimental
# bounded HIS photo-transition fallback. Controlled test image only.
B=/mnt/c/XiaomiBuilds/build-setup/evox; L=/mnt/wsl/evox/logs
rm -f $L/evox15.exit $L/evox15.dstop
bash $B/dwatch.sh evox15 &
bash $B/build.sh evox15 updatepackage
wait
