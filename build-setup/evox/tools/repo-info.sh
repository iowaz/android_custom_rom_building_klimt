#!/bin/bash
# Read-only: what the public build-recipe repo needs from the tree (upstream manifest entries we override,
# the pinned snapshot, the current pinned manifest). Writes copies to /mnt/c/XiaomiBuilds/build-setup/evox/release/manifests/.
O=/mnt/c/XiaomiBuilds/build-setup/evox/release/manifests; mkdir -p $O
cd /mnt/wsl/evox/src/.repo/manifests
echo "manifest HEAD: $(git log --oneline -1)"
grep -rn 'path="vendor/lineage"\|path="hardware/interfaces"\|path="build/soong"\|path="vendor/gms"\|evolution-priv\|<remote \|<default ' *.xml snippets/*.xml | head -30
echo "== build/soong entry"; grep -h -A4 'path="build/soong"' default.xml snippets/*.xml | head -12
M=/mnt/wsl/build/logs/evox-pre-sync.xml
echo "== snapshot $M: $(grep -c '<project' $M) projects"; grep '<remote' $M
grep -n 'file://\|/mnt/\|localhost' $M | head
echo "== keys dir"; ls /mnt/wsl/evox/src/vendor/evolution-priv/ | head; git -C /mnt/wsl/evox/src/vendor/evolution-priv/keys remote -v 2>/dev/null | head -2
cd /mnt/wsl/evox/src
REPO_TRACE=0 timeout 300 python3 .repo/repo/repo manifest -r -o $O/evox10-pinned.xml 2>&1 | tail -2
echo "pinned: $(grep -c '<project' $O/evox10-pinned.xml) projects"
grep -n 'path="device/xiaomi/klimt"\|path="vendor/lineage"\|path="hardware/interfaces"\|path="build/soong"\|path="kernel/xiaomi/klimt"\|path="vendor/xiaomi' $O/evox10-pinned.xml
echo "== done"
