#!/bin/bash
# repo sync the Evo tree; log to /mnt/wsl/evox/logs/sync.log
cd /mnt/wsl/evox/src || exit 1
log=/mnt/wsl/evox/logs/sync${1:+-$1}.log
echo "=== $(date) sync start" > $log
repo sync -c --no-tags --no-clone-bundle -j8 >> $log 2>&1
rc=$?
echo "=== $(date) sync exit $rc" >> $log
exit $rc
