#!/bin/bash
# One-time (2026-10-15): copy the source disk (/mnt/wsl/evox, vhdx-images\source.vhdx) into the build disk at
# /mnt/wsl/build/evox. After the switch (merge-source-switch.ps1), /mnt/wsl/build/evox is bind-mounted at
# /mnt/wsl/evox, so every path stays the same.
#   snapshot <out.tsv>  as the user: HEAD and dirty state of every project in evox18's frozen manifest
#   copy                as root: rsync everything except lost+found
#   verify              as root: checksum every file and compare every attribute; prints nothing when identical
set -euo pipefail
S=/mnt/wsl/evox/
D=/mnt/wsl/build/evox/
M=/mnt/d/android_rom_building/diagnostics/builds/evox18/evox18-frozen.xml
RSYNC=(rsync -aHAX --numeric-ids --exclude=/lost+found)

case "${1:-}" in
snapshot)
  python3 - "$M" "$2" <<'EOF'
import subprocess, sys, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
paths = sorted(p.get('path') or p.get('name') for p in ET.parse(sys.argv[1]).getroot().iter('project'))
def g(path, *a):
    r = subprocess.run(['git', '-C', '/mnt/wsl/evox/src/' + path, *a], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else 'ERROR'
def state(path):
    return f"{path}\t{g(path, 'rev-parse', 'HEAD')}\t{'dirty' if g(path, 'status', '--porcelain') else 'clean'}"
rows = list(ThreadPoolExecutor(12).map(state, paths))
open(sys.argv[2], 'w').write('\n'.join(rows) + '\n')
print(f"{len(rows)} projects, {sum('ERROR' in r for r in rows)} errors, {sum(r.endswith('dirty') for r in rows)} dirty")
EOF
  ;;
copy)
  test ! -e "$D" || { echo "refusing: $D exists"; exit 1; }
  "${RSYNC[@]}" --info=stats2 "$S" "$D"
  ;;
verify)
  # -c compares contents; -i lists any file whose contents or attributes (time, mode, owner, ACL, xattr) differ,
  # and --delete lists files only the copy has. Identical trees print nothing.
  "${RSYNC[@]}" -c -n -i --delete "$S" "$D"
  echo "files: source $(find "$S" -xdev -path "${S}lost+found" -prune -o -print | wc -l), copy $(find "$D" -print | wc -l)"
  ;;
*) echo "usage: $0 snapshot <out.tsv> | copy | verify"; exit 2 ;;
esac
