#!/bin/bash
# Git Bash side: emit one status line every 10 min, and immediately on FAILED / exit / D: watchdog stop.
# Flags a possible freeze when the ninja step count, the log size and the build processes' CPU time
# (soong_build, ninja, java, clang, ...) don't move for 30 min.
# monitor-build10.sh <name>
name=$1; i=0; lastfail=0; laststep=""; lastsize=""; same=0
q() { MSYS_NO_PATHCONV=1 timeout 75 wsl -d Ubuntu-24.04 --cd / -e bash -c "$1" 2>/dev/null | tr -d '\r'; }
while true; do
  s=$(q "bash /mnt/c/XiaomiBuilds/build-setup/evox/progress.sh $name; f=\$(grep -ac 'FAILED:' /mnt/wsl/evox/logs/$name.log); echo \"F=\$f\"; echo \"SZ=\$(stat -c %s /mnt/wsl/evox/logs/$name.log)\"; echo \"CPU=\$(ps -eo times=,comm= | awk '/soong|ninja|java|clang|ld|d8|r8|kotlin|metalava|aapt|python/ {s+=\$1} END {print s+0}')\"; [ -f /mnt/wsl/evox/logs/$name.dstop ] && echo DSTOP; df -BG --output=avail /mnt/d | tail -1")
  if [ -z "$s" ]; then
    [ $((i % 20)) -eq 0 ] && echo "$(date +%H:%M) WSL busy/unresponsive (soong analysis thrash?), retrying"
  else
    line=$(echo "$s" | head -1); f=$(echo "$s" | sed -n 's/^F=//p'); sz=$(echo "$s" | sed -n 's/^SZ=//p'); cpu=$(echo "$s" | sed -n 's/^CPU=//p')
    dfree=$(echo "$s" | tail -1 | tr -d ' ')
    if echo "$s" | grep -q DSTOP; then echo "$(date +%H:%M) D: WATCHDOG STOPPED THE BUILD (D: free $dfree)"; exit 0; fi
    if echo "$line" | grep -q 'DONE exit'; then echo "$(date +%H:%M) $line | D: free $dfree"; exit 0; fi
    if [ -n "$f" ] && [ "$f" -gt "$lastfail" ]; then
      echo "$(date +%H:%M) FAILED step appeared: $line"
      q "grep -a -A3 'FAILED:' /mnt/wsl/evox/logs/$name.log | head -12"
      lastfail=$f
    elif [ $((i % 20)) -eq 0 ]; then
      step=$(echo "$line" | grep -oE '[0-9]+/[0-9]+' | head -1)
      if [ -n "$laststep" ] && [ "$step" = "$laststep" ] && [ "$sz" = "$lastsize" ] && [ "${cpu:-0}" -le "${lastcpu:-0}" ]; then same=$((same + 1)); else same=0; fi
      laststep=$step; lastsize=$sz; lastcpu=$cpu
      if [ $same -ge 3 ]; then
        echo "$(date +%H:%M) POSSIBLE FREEZE: no progress for 30 min: $line | D: free $dfree"
      else
        echo "$(date +%H:%M) $line | build CPU ${cpu}s | D: free $dfree"
      fi
    fi
  fi
  i=$((i + 1)); sleep 30
done
