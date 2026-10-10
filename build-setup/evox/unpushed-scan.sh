#!/bin/bash
# Read-only: every project in the Evo tree whose HEAD (or any local branch) has commits that are in no
# remote-tracking ref, or that has no remote at all, or has dirty files. Shallow clones are fine (fetched state).
cd /mnt/wsl/evox/src
python3 - <<'EOF'
import subprocess
from concurrent.futures import ThreadPoolExecutor
paths = subprocess.run(["repo", "list", "-p"], capture_output=True, text=True).stdout.split()
# local_manifests projects that repo may list too; add the known extras just in case
for extra in ["kernel/xiaomi/klimt-prebuilt"]:
    if extra not in paths: paths.append(extra)
def g(p, *a):
    r = subprocess.run(["git", "-C", p, *a], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None
def check(p):
    remotes = g(p, "remote") or ""
    out = []
    n = g(p, "rev-list", "--count", "HEAD", "--not", "--remotes")
    if n and n != "0":
        out.append(f"HEAD has {n} commit(s) in no remote ref: " + (g(p, "log", "--format=%h %s", "-3", "HEAD", "--not", "--remotes") or "").replace("\n", " | "))
    for b in (g(p, "for-each-ref", "--format=%(refname:short)", "refs/heads") or "").split():
        nb = g(p, "rev-list", "--count", b, "--not", "--remotes")
        if nb and nb != "0":
            out.append(f"branch {b}: {nb} commit(s) in no remote ref")
    d = g(p, "status", "--porcelain")
    if d: out.append(f"dirty: {len(d.splitlines())} file(s)")
    if not remotes: out.append("NO REMOTE")
    return p, remotes.replace("\n", ","), out
res = list(ThreadPoolExecutor(12).map(check, paths))
print(f"projects scanned: {len(res)}")
for p, r, out in res:
    if out:
        print(f"== {p} (remotes: {r or '-'})")
        for o in out: print("   " + o)
EOF
echo "== klimt-prebuilt detail"
git -C kernel/xiaomi/klimt-prebuilt remote -v; git -C kernel/xiaomi/klimt-prebuilt log --format='%h %ad %an %s' --date=short -5
echo "== local manifests"; ls -la .repo/local_manifests/
