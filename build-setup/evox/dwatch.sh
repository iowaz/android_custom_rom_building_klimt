#!/bin/bash
# D: watchdog for a build: dwatch.sh <build-name> [min_free_GB=10]
# build.vhdx and evox.vhdx live on D: and grow during a build; a full host disk corrupts the ext4 inside.
# Logs D: free every 60 s; if it drops below the limit, stops the build (stop-build.sh) and writes <name>.dstop.
name=$1; min=${2:-10}; L=/mnt/wsl/evox/logs; log=$L/$name.dfree
echo "$(date +%T) start min=${min}G" >> $log
while [ ! -f $L/$name.exit ]; do
  free=$(df -BG --output=avail /mnt/d | tail -1 | tr -dc 0-9)
  echo "$(date +%T) D_free=${free}G build.vhdx=$(stat -c %s /mnt/d/WitAquaBuild/build.vhdx | awk '{printf "%.1f", $1/2^30}')G" >> $log
  if [ -n "$free" ] && [ "$free" -lt "$min" ]; then
    echo "$(date +%T) D: below ${min}G -> stopping build" >> $log
    bash /mnt/c/XiaomiBuilds/build-setup/evox/stop-build.sh >> $log 2>&1
    echo "D_free=${free}G at $(date)" > $L/$name.dstop
    exit 1
  fi
  sleep 60
done
echo "$(date +%T) build finished, watchdog exit" >> $log
