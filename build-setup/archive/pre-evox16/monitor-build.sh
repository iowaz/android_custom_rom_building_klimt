#!/bin/bash
# Git Bash side: emit one status line every ~4 min, and immediately on FAILED / exit / D: watchdog stop.
# monitor-build.sh <name>
name=$1; i=0; lastfail=0
q() { MSYS_NO_PATHCONV=1 timeout 75 wsl -d Ubuntu-24.04 --cd / -e bash -c "$1" 2>/dev/null | tr -d '\r'; }
while true; do
  s=$(q "bash /mnt/c/XiaomiBuilds/build-setup/evox/progress.sh $name; f=\$(grep -ac 'FAILED:' /mnt/wsl/evox/logs/$name.log); echo \"F=\$f\"; [ -f /mnt/wsl/evox/logs/$name.dstop ] && echo DSTOP; df -BG --output=avail /mnt/d | tail -1")
  if [ -z "$s" ]; then
    [ $((i % 8)) -eq 0 ] && echo "$(date +%H:%M) WSL busy/unresponsive (soong analysis thrash?), retrying"
  else
    line=$(echo "$s" | head -1); f=$(echo "$s" | sed -n 's/^F=//p'); dfree=$(echo "$s" | tail -1 | tr -d ' ')
    if echo "$s" | grep -q DSTOP; then echo "$(date +%H:%M) D: WATCHDOG STOPPED THE BUILD (D: free $dfree)"; exit 0; fi
    if echo "$line" | grep -q 'DONE exit'; then echo "$(date +%H:%M) $line | D: free $dfree"; exit 0; fi
    if [ -n "$f" ] && [ "$f" -gt "$lastfail" ]; then
      echo "$(date +%H:%M) FAILED step appeared: $line"
      q "grep -a -A3 'FAILED:' /mnt/wsl/evox/logs/$name.log | head -12"
      lastfail=$f
    elif [ $((i % 8)) -eq 0 ]; then
      echo "$(date +%H:%M) $line | D: free $dfree"
    fi
  fi
  i=$((i + 1)); sleep 30
done
