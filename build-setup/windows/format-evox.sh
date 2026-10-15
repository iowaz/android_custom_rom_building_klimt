#!/bin/bash
set -e
dev=$(bash /mnt/c/XiaomiBuilds/build-setup/evox/finddev.sh)
echo "device: [$dev]"
[[ "$dev" =~ ^sd[a-z]+$ ]] || { echo "device not found"; exit 1; }
mkfs.ext4 -F -L evox -m 0 "/dev/$dev"
