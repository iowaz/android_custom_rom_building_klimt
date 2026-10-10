#!/bin/bash
# Check the public local manifest against today's Evolution X cnb manifest without syncing any source:
# repo init (manifest only) in a scratch dir, merge, and confirm every klimt URL/branch exists.
set -e
T=/mnt/wsl/build/manifest-test; rm -rf $T; mkdir -p $T/.repo/local_manifests; cd $T
repo init -q -u https://github.com/Evolution-X/manifest -b cnb --git-lfs --depth=1 --no-clone-bundle </dev/null 2>&1 | tail -3
cp /mnt/c/XiaomiBuilds/android_custom_rom_building_klimt/manifests/local_manifests/klimt.xml .repo/local_manifests/
echo "manifest: $(git -C .repo/manifests log --oneline -1)"
repo --version 2>&1 | head -2
repo manifest -o merged.xml 2>&1 | tail -3
echo "projects: $(grep -c '<project' merged.xml)"
python3 - <<'EOF'
import xml.etree.ElementTree as ET, subprocess, collections
root = ET.parse("merged.xml").getroot()
rem = {r.get("name"): r.get("fetch") for r in root.iter("remote")}
d = root.find("default")
paths = collections.Counter(p.get("path") or p.get("name") for p in root.iter("project"))
dups = [p for p, n in paths.items() if n > 1]
print("duplicate paths:", dups or "none")
for p in root.iter("project"):
    path = p.get("path") or p.get("name")
    if path not in ("device/xiaomi/klimt", "kernel/xiaomi/klimt", "kernel/xiaomi/klimt-prebuilt", "vendor/xiaomi/klimt",
                    "hardware/xiaomi", "device/mediatek/sepolicy_vndr", "build/soong", "hardware/interfaces", "vendor/lineage"):
        continue
    r = p.get("remote") or d.get("remote"); f = rem[r]
    if f == "..": f = "https://github.com"
    url = f.rstrip("/") + "/" + p.get("name")
    rev = (p.get("revision") or d.get("revision")).replace("refs/heads/", "")
    out = subprocess.run(["git", "ls-remote", url, f"refs/heads/{rev}"], capture_output=True, text=True).stdout.split()
    print(f"{path:32} {url} {rev} -> {out[0][:10] if out else 'MISSING'}")
EOF
cd /; rm -rf $T
echo "== done"
