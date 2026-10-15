#!/bin/bash
# Read-only: every project's dirty state, plus the local commits on top of the snapshot manifest
# (/mnt/wsl/build/logs/evox-pre-sync.xml). Output: what the next build contains beyond upstream.
cd /mnt/wsl/evox/src
M=/mnt/wsl/build/logs/evox-pre-sync.xml
python3 - "$M" <<'EOF'
import subprocess, sys, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
root = ET.parse(sys.argv[1]).getroot()
projs = [(p.get("path") or p.get("name"), p.get("revision")) for p in root.iter("project")]
def g(path, *a):
    r = subprocess.run(["git", "-C", path, *a], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None
def check(item):
    path, rev = item
    dirty = g(path, "status", "--porcelain")
    head = g(path, "rev-parse", "HEAD")
    if head is None:
        return (path, "MISSING", [], "")
    local = []
    if rev and head != rev:
        log = g(path, "log", "--format=%h %s", f"{rev}..HEAD")
        local = log.splitlines() if log else [f"(HEAD {head[:10]} not a descendant of snapshot {rev[:10]})"]
    return (path, "DIRTY" if dirty else "", local, dirty or "")
res = list(ThreadPoolExecutor(12).map(check, projs))
dirty = [r for r in res if r[1] == "DIRTY"]
missing = [r for r in res if r[1] == "MISSING"]
changed = [r for r in res if r[2]]
print(f"projects: {len(res)} | dirty: {len(dirty)} | missing: {len(missing)} | with local commits: {len(changed)}")
for p, _, _, d in dirty:
    print(f"DIRTY {p}:\n  " + "\n  ".join(d.splitlines()[:10]))
for p, *_ in missing:
    print(f"MISSING {p}")
print("\n== local commits on top of the snapshot")
for p, _, local, _ in sorted(changed):
    print(f"{p} ({len(local)}):")
    for l in local:
        print("   " + l)
EOF
