#!/bin/bash
# Read-only backup audit: every local branch of the repos backed by iowaz, compared with the iowaz remote.
T=/mnt/wsl/evox/src
audit() {  # audit <path> <iowaz repo>
  local p=$T/$1 u=https://github.com/iowaz/$2
  echo "=== $1 -> iowaz/$2"
  [ -d $p ] || { echo "  (no local checkout)"; return; }
  echo "  HEAD: $(git -C $p rev-parse --abbrev-ref HEAD) $(git -C $p rev-parse --short=10 HEAD) | dirty: $(git -C $p status --porcelain | wc -l) | stash: $(git -C $p stash list | wc -l) | shallow: $(git -C $p rev-parse --is-shallow-repository)"
  local remote; remote=$(git ls-remote --heads --tags $u 2>/dev/null)
  echo "  remote refs: $(echo "$remote" | grep -c .)"
  echo "$remote" | sed 's|refs/heads/||; s|refs/tags/|tag:|' | awk '{printf "    remote %s %s\n", substr($1,1,10), $2}'
  git -C $p for-each-ref --format='%(refname:short) %(objectname)' refs/heads refs/tags | while read -r ref sha; do
    if echo "$remote" | grep -q "^$sha"; then st="on remote (same sha)"
    elif git -C $p cat-file -e "$sha" 2>/dev/null && [ -n "$(echo "$remote" | awk '{print $1}' | while read -r r; do git -C $p merge-base --is-ancestor $sha $r 2>/dev/null && echo y; done)" ]; then st="contained in a remote branch"
    else st="NOT ON REMOTE"; fi
    echo "    local  ${sha:0:10} $ref -> $st"
  done
}
audit device/xiaomi/klimt android_device_xiaomi_klimt
audit vendor/xiaomi/klimt proprietary_vendor_xiaomi_klimt
audit vendor/lineage vendor_evolution
audit hardware/interfaces hardware_interfaces
audit build/soong build_soong
audit kernel/xiaomi/klimt android_kernel_xiaomi_klimt
echo "=== kernel/xiaomi/klimt-prebuilt (no iowaz repo)"
git -C $T/kernel/xiaomi/klimt-prebuilt log -1 --format='  HEAD %h %s' ; echo "  dirty: $(git -C $T/kernel/xiaomi/klimt-prebuilt status --porcelain | wc -l)"
echo "=== other git repos under WSL home and /mnt/wsl (depth 3, outside the Evo tree)"
find ~ /mnt/wsl/build -maxdepth 3 -name .git -not -path '*/evox-out/*' 2>/dev/null | head -20
