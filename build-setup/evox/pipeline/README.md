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

### Controlled local kernel candidates

Ordinary builds keep the upstream/sync protections below. For an audited kernel candidate, use
`prepare.py candidate <build> --previous <control> --candidate-spec /absolute/candidate.json`, followed by
`label` and `freeze`. This path does no sync and does not move the build checkout's kernel branch: it fetches
the exact local object and checks it out detached. The audit repository alone advances its default `17.0`.
Every other project and the existing ROM patch bundle must still match the control snapshot.

The schema-1 specification contains `baseline_sha256` (the control snapshot), `audit_repository` (an absolute
bare Git directory), `heads` (exactly `kernel/xiaomi/klimt` and `device/xiaomi/klimt`, each an exact SHA), and
`tooling_sha256` (the complete `controller.tooling_hashes()` map). Device metadata must already name the
candidate kernel SHA with the previous build token. A dry run checks the specification and full control
graph without fetching, labeling or freezing. Never run upstream/sync after candidate preparation.

For a changed kernel, `ready.py` additionally requires `--kernel-audit /absolute/audit.json` and
`--rollback-baseline /absolute/baseline-security.json`. `candidate_gates.py` requires the named ancestry,
local-delta, pKVM semantic/type, STG ABI, protected-export, tracked-symbol, config and module checks to pass
with hashed proof files and exact kernel/prebuilt/vendor/control pins. The candidate record starts a
seven-day control freeze. Missing, altered or expired evidence stops readiness, the controller and promotion.
Configuration analysis may vary only the per-build LOCALVERSION; packaged options must match its hash.

Preparation retains the tools that performed its checkout/label/freeze. Readiness separately seals the
complete build/verifier tooling map after rechecking the frozen graph. A verifier correction before the
first attempt can therefore be recorded at readiness without rewriting preparation history. Changing any
tool after readiness invalidates that readiness; an attempt also retains its own immutable tooling map.

`kernel_contract.py` derives the expected release from Makefile, build.config.common and device metadata at
the frozen commits. Historical artifacts through 20261108 retain their old profile; new builds cannot use a
historical fallback. The verifier checks the resulting image banner. `rollback_security.py` compares all
emitted AVB rollback headers/chain locations/security properties, boot/init_boot v4 OS fields, actual source
SPL and reported partition patch levels against the extracted control. A difference fails verification.
Build dates/labels remain governed by their per-build checks, rather than equality to an older build.

Candidates remain local and runtime-unvalidated. An image check does not authorize flashing, a remote push,
tag or any slot-state change. Keep the previous boot-tested ZIP and the agreed recovery procedure available.

### Ordinary upstream builds

For the owner-requested local keybox feature, `local_rom_control.py` validates the
`local-rom-patches-audited-kernel` preparation record. It allows exactly the reviewed
frameworks/base and Evolver commits plus the device patch bundle/build label, preserves
the existing patches and upstream bases, and rejects all other source changes. The
record binds the full before/after graph, implementation source hashes, preparation
script, frozen snapshot and tooling. Readiness, the controller and promotion recheck
it alongside the carried kernel audit and rollback control. This path performs no sync;
ordinary upstream builds retain all six preparation requirements below.

When an ordinary upstream refresh retains a previously audited non-baseline kernel, complete the six
source-preparation steps below first. Then run `upstream_kernel_control.py <build> --control <full-control>`
to bind all six successful records and the frozen snapshot to the unchanged kernel/prebuilt/vendor pins.
Carry the full control's audit with `kernel_carry.py`, capture its rollback/security control, and supply both
to `ready.py`. ROM projects may refresh; kernel/prebuilt/vendor or normalized kernel configuration changes
still require a new audit. The refreshed build receives its own image verification; it does not inherit the
control's ROM result. `20261112.2` uses full verification for this path.

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
python3 -B $P/prepare.py patch 20261105          # device patches/apply.py; a project Evolution X rebased is re-exported
                                                # and committed on the device cnb; only a conflict stops
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

# 5. With the owner's OK: tag the build where its pinned commits are (no per-build branches)
for r in android_device_xiaomi_klimt android_kernel_xiaomi_klimt proprietary_vendor_xiaomi_klimt; do
  sha=...   # that repository's revision in manifests/snapshots/20261105.xml
  gh api -X POST repos/iowaz/$r/git/refs -f ref=refs/tags/20261105 -f sha=$sha
done        # and tag the build repository commit that records the build
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

### Simple and full modes

`ready.py` seals a verification mode in `BUILD_READY.json` (`verification`, see [`verification.py`](verification.py)
and [the design](../../../docs/designs/verifier-simplification.md)). It compares this build's readiness with the
newest earlier build that has `PROMOTED.json`:

- **full**, the verifier described below, when the private vendor blobs, signing certificates or target changed, a
  `klimt` patch moved to an unmapped project, `BoardConfig.mk` partition/super/AVB lines, `modules.load.*` or the
  fstab changed, there is no baseline, or the operator asks (`--mode full`);
- **simple** otherwise, with focused extras for what changed: a kernel project (`kernel`, the module CRC check),
  a patched project's base or patch (`policy`, `patch_packaging`), `hardware/xiaomi`, `vendor/gms*`,
  `device/mediatek/sepolicy_vndr`, or device-tree paths (`health/` → `health_semantics`, `sepolicy/` → `policy`,
  `udfps/`, `parts/`, `apps/`, overlays → `doze_packaging`, `wifi/` → `private_compatibility`, ...). A kernel head
  other than `kernel_contract.BASELINE` adds the `kernel` extra and the candidate checks.

`--extra NAME` (repeatable) and `--reason` add checks; nothing removes a computed one, and `--mode simple` is
refused when inputs require full. A readiness without the record is verified in full.

Simple runs eight checks on the producing ZIP, then the extras: `attempt.provenance`, `archive.integrity` (19
entries, CRC, the delivery copy hashed while copying and read back), `avb.chain` (`verify_image
--follow_chain_partitions`; vbmeta/chain keys equal the baseline's), `flash.layout` (super_empty,
fastboot-info, android-info against author/build9), `dtb.live` (DTBO payload and vendor_boot DTB against the
live slot b), `identity.metadata` (check-metadata26's 112 assertions on the staged build.prop files, packaged
kernel banner), `staging.clean` (every staged path is a product install, kernel modules excepted; only the
selected Telecom variant) and `signing.platform` (staged framework-res.apk signer). The staging inputs are
captured by `build.sh` at packaging time ([`staging_evidence.py`](staging_evidence.py), hashed into
`build-exit.json`); an attempt without them cannot be verified in simple mode. A simple candidate extracts only
`vendor_dlkm` and `system_dlkm` for the module CRC and kernel binding checks. Track extras extract all eight
filesystems and run the registered image check. Results are `RESULTS.json` schema 2 with one entry per
required check; `promote.py` requires exactly the sealed list, all passing. The marker says `SIMPLE` and that
filesystem contents were not inspected.

`verify.py` exits 0 passed, 1 artifact/assertion defect, 2 missing tool/evidence or wrong host, 3 unexpected
error, 130 interrupted; it writes `verify-exit.<run>.json` beside the attempt, and the controller copies the code
and failing check into `status.json`. Every Linux-only entry point stops under Windows Python with exit 2 and
the `wsl.exe` command to use ([`hostcheck.py`](hostcheck.py)).

### Full mode

[`verify.py`](verify.py) only accepts the ZIP this attempt produced (hash, size, mtime from the build's own exit
record), extracts it, and requires:

- the must-hold checks ([`legacy/musthold.sh`](legacy/musthold.sh)): AVB, `super_empty`, `fastboot-info.txt`,
  `android-info.txt`, DTBO and `vendor_boot` DTB against the phone's slot b, 888 modules with 0 CRC mismatches;
- all 195 fix checks: the 165 historical ones, 22 for the evox20 device-metadata pass, 4 for evox21
  (bionic's overlay filter and `/data/local/tmp`, no `adb_root` in a user build, no `persist.sys.usb.config`)
  and 4 for the 20261105 log-review fixes (hypsys camera properties, mpbe f2fs dontaudit, quieted ambient-light
  debug tags, charging animation kept off the always-on display)
  ([`legacy/fixcheck21.sh`](legacy/fixcheck21.sh) and the files it chains to,
  matched by name against [`expected-legacy-checks.json`](expected-legacy-checks.json)). Three checks were
  retired on 2026-11-04 with the patches they tested, which were dropped with the forks: the two adbroot policy
  checks (device/lineage/sepolicy) and "no init rc gives persist.sys.evox props a value" (system/core). On
  2026-11-05 "klimt_felica may call system_server" became "Mobile FeliCa removed": the owner had FeliCa taken
  out. The
  checks that depend on the build read its name through [`legacy/build-profile.sh`](legacy/build-profile.sh): a
  date-named build gets every rule from evox26 on and the kernel label `ab<build>`;
- seven image checks ([`image-checks/check_image.py`](image-checks/check_image.py), registered with their hash in
  `IMAGE_CHECKS.json`): policy, patch packaging, private compatibility, Health semantics, GMS/themes/apps, Doze
  packaging and install integrity.

It then stages the delivery: `lineage_klimt-<build>-img.zip`, `lineage_klimt-<build>-flash.bat`/`.sh`,
`SHA256SUMS`, `VERIFIED.txt` ("static image checks passed, NOT boot-tested"), `RESULTS.json`,
`COMPARISON.md`, `README.md` and the pre/post manifests. The flash helpers check the hash and the `klimt`
product, need `/flash` or `--flash`, run `fastboot update --skip-reboot` (no wipe), then run
`fastboot reboot` only if the update succeeds. A failed flash stays in fastboot. Flash authorization
includes the successful-flash reboot unless the owner explicitly asks to remain in fastboot. Helpers
use `D:\android_rom_building\tools\platform-tools\fastboot.exe` when it exists. For older delivery
helpers that stop in fastboot, the agent performs the final reboot after checking successful completion.

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

`tool_review.py ... --mode full` or `--extra NAME` widens the sealed verification record for that recheck (more
checks, never fewer); omitted, the recheck inherits it. A simple recheck reads the ZIP from `out/` while it is still
this attempt's, otherwise from the attempt's staged or promoted copy, matched by the build-exit digest.

Run long commands through `start.sh` or a background shell; a process started with `setsid ... &` inside a
one-off `wsl.exe` call can die when the call returns.

The controller and the verifier refuse to run while another build or extraction is alive. They look for
`soong_ui`, `soong_build`, `ninja` or `kati` processes, and for command lines like `build.sh evoxNN`,
`build.sh 2026MMDD` or `verify-evoxNN.sh`. Do not give helper scripts names that match: evox18's first
verification stopped because a progress watcher was called `watch-build.sh evox18-attempt01` (now
`watch-attempt.sh`).

## Tests

`python3 -B tests.py` (controller, effective heads, gates, date names, `prepare.py` helpers, flash helpers),
`python3 -B test_simple_verification.py` (host guard, mode resolver, recheck widening, schema-2 promotion, archive/AVB/
layout/identity/staging/signer fixtures including the evox16 stray Telecom), the other `test_*.py` files and
`python3 -B image-checks/tests.py` (checker helpers and negative fixtures). Neither builds or verifies an image.
Do not run them during an attempt: they write files the controller's tooling snapshot would see change.
