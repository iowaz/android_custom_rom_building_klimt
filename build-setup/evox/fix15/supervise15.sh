#!/bin/bash
set -u
B=/mnt/c/XiaomiBuilds/build-setup/evox/fix15
R=/mnt/c/XiaomiBuilds/debug/noise15
if pgrep -f '^bash /mnt/c/XiaomiBuilds/build-setup/evox/fix15/(wait-verify|supervise15).sh' | grep -v "^$$$" >/dev/null; then
  echo 'Existing verification supervisor; refusing concurrent extraction';exit 1
fi
bash "$B/monitor15.sh" >> "$R/monitor15.log" 2>&1 &
monitor_pid=$!
echo 'Persistent evox15 monitor/verification supervisor started'
bash "$B/wait-verify.sh" >> "$R/wait-verify15.log" 2>&1
verify_rc=$?
echo "verification supervisor exit=$verify_rc"
wait "$monitor_pid" || true
exit "$verify_rc"
