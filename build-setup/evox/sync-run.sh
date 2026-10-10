#!/bin/bash
# Detached upstream sync: sync-run.sh <tag>  -> /mnt/wsl/evox/logs/sync-<tag>.log and sync-<tag>.exit
L=/mnt/wsl/evox/logs
rm -f $L/sync-$1.exit
setsid nohup bash -c "bash /mnt/c/XiaomiBuilds/build-setup/evox/sync.sh $1; echo \$? > $L/sync-$1.exit" >/dev/null 2>&1 < /dev/null &
sleep 5; tail -2 $L/sync-$1.log
