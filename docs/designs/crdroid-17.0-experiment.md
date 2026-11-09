# Plan: one experimental crDroid 17.0 build for klimt (Xiaomi 15T Pro) — rev 2 (after Codex review)

Status: approved 2026-11-09, not started. Saved from the planning session; nothing in it has run.

## Context

The phone runs Evolution X (EvoX) 12.3 build **20261108**, made by the forkless pipeline in
`repositories/android_custom_rom_building_klimt` (patches in `device/xiaomi/klimt/patches`). The owner wants
**one experimental crDroid build** to compare against EvoX. Nothing may disturb the EvoX daily driver: not its
tree (`/mnt/wsl/evox/src`), its pipeline, the `cnb` device branch or the phone.

Owner decisions (2026-11-09):
- **Scope now: source only.** Sync, port, freeze, then stop. Build and flash are later gates.
- **Build output space:** decide later between deleting `evox-out` (146 GiB of regenerable EvoX build output)
  and adding a disk.
- **GApps:** MindTheGapps, built in, and required: no silent fallback to vanilla.
- **ROM patches:** only what klimt needs.
- **Identity:** strip to crDroid defaults. No Xiaomi build identity, no fixed security date, no fixed
  build-host or kernel metadata.
- **Device tree:** one long-lived ROM branch `crdroid-17.0` in `iowaz/android_device_xiaomi_klimt`. Kernel and
  vendor repositories unchanged.

## Answers to the four questions

1. **Do the EvoX patches apply or help on crDroid?** Four of the 15 are needed (in three projects), and one new
   fastbootd patch (system/core) must be added. Three are EvoX-specific, already in crDroid or made unnecessary
   by stripping the identity. The other eight are the personal identity layer, which is not ported (owner's
   choice). Table below.
2. **Disk, and sharing the AOSP/Lineage clone:**
   - 1,167 of crDroid's 1,252 projects have the same path and name in EvoX, including all 939 AOSP projects at
     the same tag `android-17.0.0_r1`.
   - `repo init --reference` can borrow EvoX's git objects. That saves an estimated 25–35 GiB, unproven until a
     pilot sync.
   - The working trees and build outputs cannot be shared.
   - The source fits now. The build output does not fit next to `evox-out`.
3. **Is the build process similar?** Yes, nearly identical. crDroid is LineageOS 24.0 plus 63 crDroid
   projects (`snippets/crdroid.xml`). It keeps `vendor/lineage` (as `android_vendor_crdroid`), the product
   `lineage_klimt`, the release `cp2a` and the same kernel build code. So it is the same `lunch`,
   `m installclean`, `m updatepackage` flow, and the result flashes the same way. Differences:
   - keys go in `vendor/lineage-priv/keys`;
   - there are no GApps in the manifest;
   - the README uses `brunch`/`bacon`, which we don't need.
4. **Does the device tree or kernel need changing?**
   - Kernel: no change, same source. Only the build label changes, and it lives in the device tree.
   - Device tree: small changes on the `crdroid-17.0` branch: the patch set, removing the identity
     overrides, the MindTheGapps inherit and the kernel label.
   - No new repository.

### The EvoX patches on crDroid (checked against crDroid `17.0` sources)

| EvoX patch file | On crDroid | Action |
|---|---|---|
| `hardware/interfaces/0001-klimt-local-Drop-the-light-2.0-HIDL-interface.patch` | same AOSP light/2.0 | **port** (build fails without it) |
| `hardware/interfaces/0002-klimt-local-blank_screen-Use-only-the-AIDL-lights-HA.patch` | same HIDL fallback in light/utils | **port** |
| `frameworks/native/0001-libui-Preserve-the-supported-SMPTE2094_50-metadata-g.patch` | same unguarded `getSmpte2094_50` | **port** |
| `build/soong/0001-klimt-Retain-MIUI-boot-jar-package-allowance-on-Evox.patch` | no `miui` entries | **port** (device keeps `miui-stub/`) |
| *new* `system/core`: fastbootd `FASTBOOT_BYPASS_LOCK_STATE` | missing; crDroid/Lineage treat the device as locked unless `verifiedbootstate == orange`. With Fenrir, crDroid's fastbootd would refuse to flash logical partitions | **port** EvoX's `fastboot/Android.bp` select and `fastboot/device/utility.cpp` `#ifdef`; credit the EvoX author |
| `frameworks/base/0001-PackagePartitions-…` | only needed with a fixed fingerprint | **not needed** (identity stripped; crDroid's fingerprint and incremental change every build) |
| `frameworks/base/0002-SystemUI-Keep-the-charging-animation-off-the-always-.patch` | `ChargingAnimationView.kt` doesn't exist (crDroid has `AXCharging*`) | skip; check AOD charging on the phone |
| `device/lineage/sepolicy/0001-…adb-root…` | crDroid already has `common/private/adbroot_debug/` | not needed |
| build/soong 0002, build/make, vendor/lineage, lineage-sdk ×2, Settings, Updater, recovery | personal identity layer / EvoX-only | not ported |

That gives **5 patches in 4 projects** (hardware/interfaces ×2, frameworks/native, build/soong, system/core).
The new `PATCHES.json` lists exactly these files, in this order.

### Device tree facts
- Every resource in `overlay/`, `overlay-product/`, `rro_overlays/` and the lineage-sdk overlay exists in
  crDroid's sources; this was checked by name through the GitHub API.
- The MediaTek GED-KPI soong flag exists in crDroid's `frameworks/native`.
- `lineage.dependencies` (`hardware/xiaomi`, `sepolicy_vndr`, both `lineage-24.0`) is shared.
- The kernel makefiles differ from EvoX only in one `DO_NOT_REBUILD_KERNEL` ordering hunk.

## Steps (source phase)

All WSL work runs from script files in `D:\android_rom_building\tmp\crdroid\` (`wsl ... bash -c` loses
`$VARs`). Long jobs run in a background shell with `wsl-keepalive.ps1`. Units are GiB throughout.

### 0. Pre-flight (read-only, plus one owner choice)
1. **Mutual exclusion.** Every crDroid script takes the EvoX pipeline's own lock with a non-blocking
   `flock` on `/mnt/wsl/evox/logs/source.lock` (the lock `controller.py` uses), and refuses to start if
   `ninja`, `soong_ui` or `repo` processes are running. No separate lock.
2. **Baseline pins** from `manifests/snapshots/20261108.xml`:

   | Project | Pin |
   |---|---|
   | device | `dd6cb608…` |
   | kernel | `f6a5b29f…` |
   | klimt-prebuilt | `a2d1dae4…` |
   | vendor | `5ee96dc9…` |

   Then run `git fetch --tags` in the local device clone and check that tag `20261108` resolves to `dd6cb608`.
3. **Record:** repo v2.68.1 and git 2.43.0 versions, `df` and `Get-PSDrive`.
4. **Disk gate D0.**
   - Measured: build disk 179 GiB free; D: 62.8 GiB free.
   - `build.vhdx` is a 613 GiB file on D: and not sparse, so it can grow up to about 27 GiB more. Worst case
     that leaves D: at about 36 GiB, below EvoX `ready.py`'s 45 GiB.
   - The owner picks before the sync: free about 10 GiB on D: first (for example, move
     `output-zips\20261106` and `diagnostics\builds` of old builds to `C:\android_rom_building_archive`), or
     accept that risk.
   - During the sync, a guard stops it if D: < 47 GiB or the build disk < 25 GiB.
5. **Phone check (owner, read-only):** `adb shell getprop ro.boot.verifiedbootstate` in Android, and in
   recovery if possible. This is evidence for the fastbootd patch, which is ported either way.

### 1. Build-repo scaffolding (`android_custom_rom_building_klimt`; the EvoX pipeline stays untouched)
- `manifests/local_manifests/klimt-crdroid.xml`:
  - device, kernel, prebuilt and vendor pinned to the baseline SHAs (`upstream="cnb"`/`17.0`);
  - `hardware/xiaomi` and `sepolicy_vndr` on `remote="github"`, `lineage-24.0`;
  - MindTheGapps `vendor/gapps` (GitLab `MindTheGapps/vendor_gapps`, `cinnamonbun`), pinned to a SHA.
- `build-setup/crdroid/`: `env.sh`, `sync.sh`, `build.sh` and `README.md`.
  - Tree `/mnt/wsl/build/crdroid/src`; out symlink to `/mnt/wsl/build/crdroid-out` (never `OUT_DIR`).
  - `SOONG_NINJA=ninja`, shared ccache with the 20 GiB cap, `lineage_klimt-cp2a-user`.
  - `build.sh` is written but not run now.
- Naming (documented exception for the experiment): build `crYYYYMMDD` (`.N` for a second build the same
  day), `docs/crYYYYMMDD.md`, `manifests/snapshots/crYYYYMMDD.xml`, and a line in `docs/history.md`.

### 2. Sync, with a reference pilot first
1. Run `repo init -u https://github.com/crdroidandroid/android.git -b 17.0 --git-lfs --depth=1 --no-clone-bundle --reference=/mnt/wsl/evox/src`,
   then copy the local manifest.
2. **Pilot.** `repo sync -c --no-tags` on three projects only: `prebuilts/clang/host/linux-x86` (AOSP, large),
   a LineageOS project, and `frameworks/base` (crDroid).
   - Check that `objects/info/alternates` exists and that `git fsck --connectivity-only` passes.
   - Measure the disk used against the pack sizes in EvoX.
   - If the borrowing doesn't save space or fsck fails, delete `.repo` and re-init without `--reference`.
3. **Full sync:** `repo sync -c --no-tags --no-clone-bundle -j8`, then `repo forall -c 'git lfs pull'`
   wherever LFS is used (vendor, gapps). Check the LFS files: no pointer files left and `git lfs fsck`.
4. **Borrowing rule** (alternates cover `.repo/project-objects/*` and `.repo/manifests.git`):
   - Never delete or re-init the EvoX tree while the crDroid tree exists.
   - Before the next EvoX `prepare.py sync` (its fetches can gc and prune), either delete the crDroid tree or
     dissociate it. To dissociate, run `git repack -a -d` in every object directory under the crDroid `.repo`
     (project-objects and `manifests.git`), remove the `alternates` files, then
     `git fsck --connectivity-only`. That needs the saved 25–35 GiB back.
   - `fsck` is also a gate before any build.

### 3. Signing keys (in the tree only, never committed or printed)
- Copy `vendor/evolution-priv/keys` to `vendor/lineage-priv/keys`.
- Rewrite every `vendor/evolution-priv/keys` path in `keys.mk` (`PRODUCT_DEFAULT_DEV_CERTIFICATE`,
  `AVB_CUSTOM_KEY_PATH`, `PRODUCT_MAINLINE_BLUETOOTH_SEPOLICY_DEV_CERTIFICATES` via `$(dir ...)`).
- Audit with `get_build_var` (product config only):
  - the resolved `PRODUCT_DEFAULT_DEV_CERTIFICATE`, `PRODUCT_CERTIFICATE_OVERRIDES` count,
    `PRODUCT_EXTRA_RECOVERY_KEYS` and `BOARD_AVB_*`;
  - the public certificate SHA-256 values against EvoX's.
- AVB stays on the device tree's test keys with `--flags 1`, as on EvoX (`WITH_AVB ?= false`).

### 4. Device tree branch `crdroid-17.0` (local; push only with the owner's OK)
Cut from `dd6cb608` (tag `20261108`) in the crDroid tree's `device/xiaomi/klimt`. Commits:
1. **Patch set:**
   - Delete every EvoX patch folder and record.
   - Add the 5 patch files above with stub records (`class: klimt`).
   - `apply.py` and `export.py` stay unchanged; a docstring note says they serve both ROMs.
2. **Identity stripped to crDroid defaults.**
   - `lineage_klimt.mk`: remove `KLIMT_BUILD_FINGERPRINT`, `BUILD_FINGERPRINT`, `BUILD_SYSTEM_FINGERPRINT`, the
     whole `PRODUCT_BUILD_PROP_OVERRIDES` identity block, `ro.build.display.id` and `ro.bootimage.fingerprint`.
   - `BoardConfig.mk`: remove the `KBUILD_BUILD_*` metadata, and set `VENDOR_SECURITY_PATCH` back to the blobs'
     real `2026-02-01` (misakazip's value).
   - Keep the genuine hardware identity: `PRODUCT_BRAND/MODEL/MANUFACTURER`, and `libinit`'s `ro.product.model`
     and `*_for_attestation` (the real klimt values the HALs and StrongBox use).
3. **`lineage_klimt.mk` ROM bits:**
   - Drop the EvoX-only `WITH_GMS` and `TARGET_ENABLE_FP_OVERRIDE`.
   - Add a **required** `$(call inherit-product, vendor/gapps/arm64/arm64-vendor.mk)`, so a missing gapps tree
     fails the build.
   - Keep `TARGET_SUPPORTS_QUICK_TAP := false` (crDroid uses it).
4. **`configs/kernel/metadata.config`:** keep the prefix and change only the suffix:
   `-android15-8-gf6a5b29f9fe5-crYYYYMMDD`. Remove the Xiaomi-provenance comment.
5. **README:** a line saying this branch is the crDroid line.

No crDroid tuning (blur, FaceUnlock, Smart Pixels, `cr_config.xml`) unless the phone shows a need.

### 5. Port the patches and normalize them
1. In each of the 4 projects, on a scratch branch: `git am -3` of the exact files (the 4 EvoX ones, in order)
   on crDroid's HEAD. Write the system/core commit by hand from EvoX's code, with the author found in the
   Evolution-X/system_core history.
2. In the device tree, run `export.py <tree> <the 4 projects> --base <project>=<crDroid HEAD SHA>`; this writes
   the patches and `PATCHES.json` records.
3. **Normalize.** In each project, check out its recorded base (detached), run
   `apply.py <tree>` (it applies the patches to branch `klimt` with the fixed committer), then
   `apply.py --check`. It must print **FINAL for all 4**.
4. Commit the device-tree branch: patch set, identity, gapps and label.
5. Check MindTheGapps is wired in, with `get_build_var PRODUCT_PACKAGES` and product config only:
   - its packages are present;
   - no SetupWizard or provider duplicates against crDroid's `SetupWizard`;
   - privapp-permissions files are present.

### 6. Freeze and record (no build)
- `repo manifest -r` into `manifests/snapshots/crYYYYMMDD.xml`:
  - patched projects pinned at their crDroid base (`apply.py` re-applies the patches);
  - the device at the new `crdroid-17.0` commit, marked **local-only** until the owner pushes the branch.
- `docs/crYYYYMMDD.md`: source state, the patch table, the identity change, the disk numbers, the Codex review
  disposition, and "source only, not built".
- Local commits only in the build repository and the device tree. Pushes need the owner's OK and review.

### Verification for this phase
- `repo status` is clean apart from the `klimt` branches.
- `apply.py --check` prints FINAL ×4.
- `git fsck --connectivity-only` passes in every project.
- LFS: no pointer files, and `git lfs fsck` passes.
- `lunch lineage_klimt-cp2a-user` resolves, and the `get_build_var` audits (keys, gapps) pass.
- Disk guards are recorded.
- The EvoX tree is untouched: `repo status` is clean and EvoX `apply.py --check` still prints FINAL.

## Later gates (each needs the owner's explicit go; not part of this phase)

- **G1 Soong analysis (optional):** `m nothing`. About 25 GiB RAM plus swap and about 10 GiB of out. Never
  `m <module>`.
- **G2 Space for the build output:**
  - Either delete `evox-out` and `compare/20261108` (after confirming the exact paths) or attach a disk.
  - Budget the peak: about 130 GiB out, about 20 GiB extraction, 5 GiB zip plus the delivery copy, and VHDX
    growth.
  - Keep ≥45 GiB on D: and ≥25 GiB on the build disk throughout.
- **G3 Build and verify:**
  - `build.sh`: `installclean`, then `updatepackage`. A full build, about 4–6 h.
  - Then a crDroid verifier profile that **fails on errors**, with the enforcement from `report-gates.py`
    (copying `musthold.sh` alone only prints). It covers:
    - zip provenance and extraction;
    - AVB chain;
    - `super_empty`, `fastboot-info` and `android-info` unchanged;
    - DTB identical, and DTBO payload identical (signature and footer compared separately);
    - 888 modules matching the kernel CRCs, with the one known unresolved symbol allowed explicitly;
    - from `check_image.py`, the ROM-independent checks: policy and neverallow on **crDroid's own** ninja
      graph, private-vendor blob hashes, ELF deps and allocator symbols, the Wi-Fi shim, VINTF, patch
      packaging (MIUI jars, libui, lights), GApps packaging, and install integrity (no duplicate or stray
      staged packages).
  - The verdict is "image-checked", never "works".
- **G4 Flash** (separately authorized; formatting data is its own explicit OK):
  - Before:
    - a full backup;
    - the 20261108 zip and its flash script ready;
    - the owner has reviewed the pushed commits;
    - crDroid's platform security patch level checked against EvoX's (rollback-index locations 2/4 use
      `PLATFORM_SECURITY_PATCH_TIMESTAMP`).
  - Flash slot b, `fastboot update --skip-reboot`, from EvoX's fastbootd, then **Format data**. crDroid's data
    is not compatible with EvoX's, and its vendor SPL goes back to 2026-02-01.
  - After the first boot:
    - set up PIF/TrickyStore in crDroid's own settings;
    - check `uname -r` ends in `-crYYYYMMDD`;
    - check camera, fingerprint, eSIM, AOD charging, Play Integrity and `getvar is-userspace` (mode only; no
      test flash).
  - **If crDroid's fastbootd refuses to flash:** flash EvoX's `vendor_boot` (which carries the recovery and
    fastbootd ramdisk with the bypass) from bootloader fastboot, then run `fastboot update` as usual.
  - **Rollback:** flash 20261108 to slot b, Format data, restore the backup. Firmware is unchanged by both
    ROMs.

## Codex review disposition (GPT-6.1 Sol, high: "APPROVE WITH CHANGES")

| # | Finding | Disposition |
|---|---|---|
| 1 | `*.patch` would port excluded patches | Accepted: exact file list |
| 2 | export doesn't normalize HEAD | Accepted: reset to base, then `apply.py` (now 4 projects, 5 patches) |
| 3 | moving branches ≠ baseline | Accepted: SHA pins and tag check |
| 4 | shallow `--reference` unproven, `manifests.git` | Accepted: pilot first; dissociation covers `manifests.git` |
| 5 | peak disk and units | Accepted: GiB, D0 gate (D: worst case ~36 GiB), sync guard, G2 peak budget |
| 6 | identity overrides contradict scope | Owner decided: strip to crDroid defaults; PackagePartitions dropped |
| 7 | MindTheGapps must fail closed | Accepted: required inherit, SHA pin, LFS check, no fallback |
| 8 | `musthold.sh` doesn't enforce | Accepted: enforcing profile at G3 |
| 9 | other ROM-independent checks | Accepted at G3, policy on crDroid's graph |
| 10 | signing config unproven | Accepted: `get_build_var` and certificate audit |
| 11 | status ≠ lock | Accepted: shared `source.lock` flock and process check |
| 12 | flash/rollback incomplete | Accepted: no test flash, `vendor_boot` recovery path, format OK separate |
| 13 | counts, naming, label prefix | Accepted: 63 crDroid projects, label keeps its prefix |

## Critical files
- New in the build repo:
  - `manifests/local_manifests/klimt-crdroid.xml`
  - `build-setup/crdroid/{env.sh,sync.sh,build.sh,README.md}`
  - `docs/crYYYYMMDD.md`
  - `manifests/snapshots/crYYYYMMDD.xml`
- Device tree, branch `crdroid-17.0`:
  - `patches/PATCHES.json`
  - `patches/{hardware/interfaces,frameworks/native,build/soong,system/core}/*.patch`
  - `lineage_klimt.mk`, `BoardConfig.mk`
  - `configs/kernel/metadata.config`
  - `README.md`
- Reused unchanged: `patches/apply.py`, `patches/export.py`, `wsl-keepalive.ps1`. Templates for G3:
  `report-gates.py`, `musthold.sh`, `image-checks/check_image.py`.

