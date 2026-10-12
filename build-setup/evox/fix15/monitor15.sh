#!/bin/bash
set -u
B=/mnt/c/XiaomiBuilds/build-setup/evox
L=/mnt/wsl/evox/logs
R=/mnt/c/XiaomiBuilds/debug/noise15
last=0; failed=0
while [ ! -f "$L/evox15.exit" ]; do
  now=$(date +%s)
  if [ $((now-last)) -ge 600 ] && [ -f "$L/evox15.log" ]; then
    date; bash "$B/progress.sh" evox15
    python3 -B "$B/fix15/health15.py"
    df -BG --output=avail /mnt/d | tail -1
    last=$now
  fi
  if [ -f "$L/evox15.dstop" ]; then echo 'DISK WATCHDOG STOP';cat "$L/evox15.dstop";exit 1;fi
  if [ "$failed" = 0 ] && grep -aqE '^FAILED:|^error:' "$L/evox15.log" 2>/dev/null; then
    echo 'BUILD FAILURE LINE DETECTED';grep -a -A3 -E '^FAILED:|^error:' "$L/evox15.log" | head -15;failed=1
  fi
  sleep 30
done
date;bash "$B/progress.sh" evox15;python3 -B "$B/fix15/health15.py"
