#!/bin/bash
# Usage: build.sh <name> [targets...]  (default target: evolution) -> /mnt/wsl/evox/logs/<name>.log, <name>.exit when done
name="$1"; shift; targets="${*:-evolution}"; L=/mnt/wsl/evox/logs; log=$L/$name.log
rm -f $L/$name.exit
source /mnt/c/XiaomiBuilds/build-setup/evox/env.sh
{
  echo "=== $(date) lunch $LUNCH_TARGET"
  lunch "$LUNCH_TARGET" || { echo LUNCH_FAILED; echo 1 > $L/$name.exit; exit 1; }
  echo "=== $(date) m -j12 $targets"
  m -j12 $targets
  rc=$?
  echo "=== $(date) exit $rc"
  echo $rc > $L/$name.exit
} > "$log" 2>&1
