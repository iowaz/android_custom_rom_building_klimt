# Build pipeline

One set of scripts for every build. The build name (`evox18`, `evox19`, ...) comes from the attempt ID
(`evox18-attempt01`); every location comes from [`paths.py`](paths.py). It replaced the per-build copies
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

```bash
P=/mnt/d/android_rom_building/repositories/android_custom_rom_building_klimt/build-setup/evox/pipeline
export KLIMT_BUILD=evox18
cd /mnt/wsl/evox/src

# 1. Source: sync the tree to a frozen manifest (make-frozen.py derives a new one), then
python3 -B $P/ready.py /path/to/evox18-frozen.xml --gate "review=/path/to/review.md"
#    -> diagnostics/builds/evox18/{evox18-frozen.xml,FINAL_SOURCE.json,semantic_checks.json,BUILD_READY.json}

# 2. Build and verify (detached; survives the shell): installclean, updatepackage, then verify.py
bash $P/start.sh evox18-attempt01 /mnt/d/android_rom_building/diagnostics/builds/evox18/BUILD_READY.json
python3 -B $P/controller.py status evox18-attempt01

# 3. Promote the verified delivery to output-zips/evox18 (a move; duplicate staged ZIPs are removed)
python3 -B $P/promote.py evox18-attempt01
```

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
- all 165 historical fix checks ([`legacy/fixcheck14.sh`](legacy/fixcheck14.sh) and the files it chains to,
  matched by name against [`expected-legacy-checks.json`](expected-legacy-checks.json));
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
python3 -B $P/tool_review.py evox18-attempt01 recheck01 evidence.txt
python3 -B $P/verify.py /mnt/wsl/evox/logs/evox18/evox18-attempt01 --recheck recheck01 \
  --tool-review /mnt/d/android_rom_building/diagnostics/builds/evox18/evox18-attempt01/TOOL_REVIEW.recheck01.json
python3 -B $P/promote.py evox18-attempt01 recheck01
```

Run long commands through `start.sh` or a background shell; a process started with `setsid ... &` inside a
one-off `wsl.exe` call can die when the call returns.

The controller and the verifier refuse to run while another build or extraction is alive. They look for
`soong_ui`, `soong_build`, `ninja` or `kati` processes, and for command lines like `build.sh evoxNN` or
`verify-evoxNN.sh`. Do not give helper scripts names that match: evox18's first verification stopped because a
progress watcher was called `watch-build.sh evox18-attempt01` (now `watch-attempt.sh`).

## Tests

`python3 -B tests.py` (controller, gates, flash helpers) and `python3 -B image-checks/tests.py` (checker
helpers and negative fixtures). Neither builds or verifies an image. Do not run them during an attempt: they
write files the controller's tooling snapshot would see change.
