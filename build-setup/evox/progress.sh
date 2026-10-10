#!/bin/bash
# One-line build status: progress.sh <name>
L=/mnt/wsl/evox/logs/$1.log
[ -f /mnt/wsl/evox/logs/$1.exit ] && { echo "DONE exit=$(cat /mnt/wsl/evox/logs/$1.exit)"; exit; }
f=$(grep -ac "FAILED:" $L)
p=$(tail -c 3000 $L | tr '\r' '\n' | grep -aoE "\[ *[0-9]+% [0-9]+/[0-9]+[^]]*\]" | tail -1)
echo "running failed=$f ${p:-$(tail -c 200 $L | tr '\r\n' '  ' | tail -c 120)} | mem $(free -g | awk '/Mem/{print $3"G"}') swap $(free -g | awk '/Swap/{print $3"G"}') | out $(df -h --output=used /mnt/wsl/build | tail -1) src $(df -h --output=used /mnt/wsl/evox | tail -1)"
