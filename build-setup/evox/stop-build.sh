#!/bin/bash
# Kill running Evo build sessions (build.sh started with setsid) and their children. Never matches the caller.
me=$(ps -o sid= -p $$ | tr -d ' ')
for p in $(pgrep -f "^bash /mnt/c/XiaomiBuilds/build-setup/evox/build[.]sh"); do
  sid=$(ps -o sid= -p $p | tr -d ' '); [ "$sid" = "$me" ] && continue
  echo "killing session $sid (build.sh pid $p)"; pkill -TERM -s $sid
done
sleep 5; pkill -x soong_ui; pkill -x soong_build; pkill -x ninja; sleep 3
pgrep -ax "soong_ui|soong_build|ninja|kati" | head
