# Build pipeline

One set of scripts for every build. Builds are named by date from 2026-11-04: `20261105`, and `20261105.2` for a
second build the same day (evox1 to evox31 keep their names). The build name comes from the attempt ID
(`20261105-attempt01`); every location comes from [`paths.py`](paths.py). It replaced the per-build copies
`evox16/` and `evox17/` (kept in [`../../archive`](../../archive)).

Run it from WSL, from this repository on the build PC:
`/mnt/d/android_rom_building/repositories/android_custom_rom_building_klimt/build-setup/evox/pipeline`.

## Where things go

| What | Where |
|---|---|
| Android tree / build output | `/mnt/wsl/evox/src` / `/mnt/wsl/build/evox-out` (`src/out` is a symlink). Both are on `build.vhdx`: `/mnt/wsl/evox` is a bind mount of `/mnt/wsl/build/evox` |
| Attempt folders (status, build.log, verify.log, locks) | `/mnt/wsl/evox/logs/<build>/<attempt>` |
| Frozen manifest, readiness, per-attempt records | `D:\android_rom_building\diagnostics\builds\<build>\` |
| Verifier reports | `...\diagnostics\builds\<build>\reports\<attempt>[\rechecks\<recheckNN>]` |
| Image extraction (scratch, deletable) | `/mnt/wsl/build/compare/<build>/<attempt>` |
| Reference images for the must-hold checks | `/mnt/wsl/build/compare/{author,b9,live,tools}`, `D:\android_rom_building\backups\PartitionsBackup` |
| What you flash | `D:\android_rom_building\output-zips\<build>\` |

## Steps

There are no ROM-source forks and no per-build branches. The tree is plain Evolution X `cnb` plus the device,
kernel, kernel-prebuilt and vendor repositories ([`klimt-live.xml`](../../../manifests/local_manifests/klimt-live.xml));
the patches klimt needs, and the owner's personal identity layer, are in the device tree under
`device/xiaomi/klimt/patches` (`PATCHES.json`, applied by `patches/apply.py`). A build is recorded by
`docs/<build>.md`, `manifests/snapshots/<build>.xml` and a tag.

```bash
P=/mnt/d/android_rom_building/repositories/android_custom_rom_building_klimt/build-setup/evox/pipeline
export KLIMT_BUILD=20261105

# 1. Source (prepare.py; records in diagnostics/builds/20261105/preparation)
python3 -B $P/prepare.py upstream 20261105       # heads = previous snapshot; Evolution X manifest cnb -> .repo/manifests branch klimt
python3 -B $P/prepare.py move-renamed 20261105   # moves aside projects whose repository name changed (never deletes)
python3 -B $P/prepare.py sync 20261105           # repo sync (about an hour: background shell) -> UPSTREAM_CHANGES.json
python3 -B $P/prepare.py patch 20261105          # device patches/apply.py; MISMATCH = that patch needs a re-export
python3 -B $P/prepare.py label 20261105          # device tree commit: kernel -ab20261105 in configs/kernel/metadata.config
python3 -B $P/prepare.py freeze 20261105         # -> diagnostics/builds/20261105/20261105-frozen.xml, manifests/snapshots/20261105.xml

# 2. Readiness: every gate must pass
python3 -B $P/ready.py /mnt/d/android_rom_building/diagnostics/builds/20261105/20261105-frozen.xml --gate "review=/path/to/review.md"
#    -> diagnostics/builds/20261105/{FINAL_SOURCE.json,semantic_checks.json,BUILD_READY.json}

# 3. Build and verify (detached; survives the shell): installclean, updatepackage, then verify.py
bash $P/start.sh 20261105-attempt01 /mnt/d/android_rom_building/diagnostics/builds/20261105/BUILD_READY.json
python3 -B $P/controller.py status 20261105-attempt01

# 4. Promote the verified delivery to output-zips/20261105 (a move; duplicate staged ZIPs are removed)
python3 -B $P/promote.py 20261105-attempt01
```

Each `prepare.py` step refuses to run before the step it needs, a second time after it succeeded, or on a dirty
tree (the manifests checkout and the klimt projects; `upstream` also checks every project against the previous
snapshot). `--dry-run` shows what a step would do. `--previous <build>` names the snapshot the tree holds, if it
is not the newest one before the new build. Nothing is pushed: after `freeze`, the owner pushes the device
commit to iowaz `cnb` (the frozen manifest pins it) and, once the build is recorded, tags the build.

The frozen manifest pins every patched project at its upstream base, so the snapshot syncs from public
repositories; the live tree has those projects at `final_head` from `PATCHES.json`. `ready.py`, the controller
(before and after the build) and the verifier (before and after verification) read `PATCHES.json` at the
device tree's frozen commit and accept exactly that: HEAD = `final_head` where the frozen pin is the project's
`base`. Any other difference, including a patched project left at its base or a pin that is not the base, stops
the build. `repo manifest -r` reports the live HEADs and is compared with the same heads.

`ready.py` also records, as information and not as a gate, the platform security patch level of the frozen
source (the `RELEASE_PLATFORM_SECURITY_PATCH` release flag; vendor/lineage's value overrides build/release's) and
the LineageOS review state of the current month's bulletin (`topic:C_asb_<YYYY-MM>`, open and merged changes);
without network it records `unavailable`. The reference patches for its five semantic purposes are in
[`semantic-patches/`](semantic-patches) (copied from the device tree's retired `patches/tree` and
`patches/tree-evox15`; [`SOURCES.txt`](semantic-patches/SOURCES.txt)), plus the device tree's own
`patches/<project>/`.

`build.sh` runs `m -j12 installclean` before `m -j12 updatepackage` and stops if any staged partition
survived: images are packed from the staging directories, so a leftover install would ship (evox16's boot
loop). Never run `m <module>` in this tree between builds.

The controller identifies its build by PID, `/proc` start time, boot ID and session, and a watchdog stops only
that build if a disk runs low (D: 10 GB, the ext4 disk 2 GB). It never restarts a build. A new attempt
always gets a new ID, and nothing in an attempt is overwritten.

## Verification

[`verify.py`](verify.py) only accepts the ZIP this attempt produced (hash, size, mtime from the build's own exit
record), extracts it, and requires:

- the must-hold checks ([`legacy/musthold.sh`](legacy/musthold.sh)): AVB, `super_empty`, `fastboot-info.txt`,
  `android-info.txt`, DTBO and `vendor_boot` DTB against the phone's slot b, 888 modules with 0 CRC mismatches;
- all 191 fix checks: the 165 historical ones, 22 for the evox20 device-metadata pass and 4 for evox21
  (bionic's overlay filter and `/data/local/tmp`, no `adb_root` in a user build, no `persist.sys.usb.config`)
  ([`legacy/fixcheck21.sh`](legacy/fixcheck21.sh) and the files it chains to,
  matched by name against [`expected-legacy-checks.json`](expected-legacy-checks.json)). Three checks were
  retired on 2026-11-04 with the patches they tested, which were dropped with the forks: the two adbroot policy
  checks (device/lineage/sepolicy) and "no init rc gives persist.sys.evox props a value" (system/core). The
  checks that depend on the build read its name through [`legacy/build-profile.sh`](legacy/build-profile.sh): a
  date-named build gets every rule from evox26 on and the kernel label `ab<build>`;
- seven image checks ([`image-checks/check_image.py`](image-checks/check_image.py), registered with their hash in
  `IMAGE_CHECKS.json`): policy, patch packaging, private compatibility, Health semantics, GMS/themes/apps, Doze
  packaging and install integrity.

It then stages the delivery: `lineage_klimt-<build>-img.zip`, `lineage_klimt-<build>-flash.bat`/`.sh`,
`SHA256SUMS`, `VERIFIED.txt` ("static image checks passed, NOT boot-tested"), `RESULTS.json`,
`COMPARISON.md`, `README.md` and the pre/post manifests. The flash helpers check the hash and the `klimt`
product, need `/flash` or `--flash`, run `fastboot update --skip-reboot` (no wipe) and use
`D:\android_rom_building\tools\platform-tools\fastboot.exe` when it exists.

### Verifier fixes without a rebuild

A checker defect (exit 2 = tooling, exit 1 = image defect) can be fixed and the same ZIP re-verified:
install the fixed checker, run `image-checks/tests.py`, re-register its hash in `IMAGE_CHECKS.json` and
`TEST_RESULTS.linux.json`, then

```bash
python3 -B $P/tool_review.py 20261105-attempt01 recheck01 evidence.txt
python3 -B $P/verify.py /mnt/wsl/evox/logs/20261105/20261105-attempt01 --recheck recheck01 \
  --tool-review /mnt/d/android_rom_building/diagnostics/builds/20261105/20261105-attempt01/TOOL_REVIEW.recheck01.json
python3 -B $P/promote.py 20261105-attempt01 recheck01
```

Run long commands through `start.sh` or a background shell; a process started with `setsid ... &` inside a
one-off `wsl.exe` call can die when the call returns.

The controller and the verifier refuse to run while another build or extraction is alive. They look for
`soong_ui`, `soong_build`, `ninja` or `kati` processes, and for command lines like `build.sh evoxNN`,
`build.sh 2026MMDD` or `verify-evoxNN.sh`. Do not give helper scripts names that match: evox18's first
verification stopped because a progress watcher was called `watch-build.sh evox18-attempt01` (now
`watch-attempt.sh`).

## Tests

`python3 -B tests.py` (controller, effective heads, gates, date names, `prepare.py` helpers, flash helpers) and
`python3 -B image-checks/tests.py` (checker helpers and negative fixtures). Neither builds or verifies an image.
Do not run them during an attempt: they write files the controller's tooling snapshot would see change.
