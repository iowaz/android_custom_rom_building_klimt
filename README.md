# Building Evolution X for the Xiaomi 15T Pro (klimt)

This repository is the recipe for my Evolution X builds for the Xiaomi 15T Pro: which repositories are involved,
how the build machine is set up, the scripts that drive the build, and how a build is checked and flashed.
It exists so that the build can be redone if my PC dies, moved to a CI machine, or replicated by anyone else.

No source code, blobs or keys live here. They are in the repositories listed below.

## The device

| | |
|---|---|
| Phone | Xiaomi 15T Pro, codename **klimt** |
| SoC | MediaTek Dimensity 9400+ (MT6991) |
| Display | 1280 x 2772 (447 ppi), under-display fingerprint sensor |
| Stock software | Xiaomi HyperOS 3; the ROM reuses the vendor blobs of **OS3.0.335** (Android 15 vendor) |
| Kernel | GKI 6.6 (`6.6.x-android15-8-klimt-4k`), built from source with the ROM |
| Partitions | A/B with dynamic partitions (`super`) and Virtual A/B; images are flashed with `fastboot update` |

The ROM is **Evolution X 12.3** (branch `cnb`, Android 17, build ID CP2A), built as `lineage_klimt-cp2a-user`,
signed with my own private keys, with Google apps included (`WITH_GMS=true`).

## Repositories

| Path in the source tree | Repository | Branch | Visibility | What it is |
|---|---|---|---|---|
| everything else | [Evolution-X/manifest](https://github.com/Evolution-X/manifest) | `cnb` | public | Evolution X (AOSP + LineageOS + Evolution X projects) |
| `device/xiaomi/klimt` | [iowaz/android_device_xiaomi_klimt](https://github.com/iowaz/android_device_xiaomi_klimt) | `evox` | public | Device tree, fork of [misakazip-dev](https://github.com/misakazip-dev/android_device_xiaomi_klimt). Also holds `patches/tree/` (see below) |
| `kernel/xiaomi/klimt` | [iowaz/android_kernel_xiaomi_klimt](https://github.com/iowaz/android_kernel_xiaomi_klimt) | `17.0` | public | Kernel source, fork of misakazip-dev (unchanged) |
| `kernel/xiaomi/klimt-prebuilt` | [misakazip-dev/android_kernel_xiaomi_klimt-prebuilt](https://github.com/misakazip-dev/android_kernel_xiaomi_klimt-prebuilt) | `17.0` | public | Builds the kernel from source |
| `vendor/xiaomi/klimt` | iowaz/proprietary_vendor_xiaomi_klimt | `evox` | **private** | Proprietary blobs extracted from HyperOS OS3.0.335 plus MIUI Camera. Uses Git LFS |
| `hardware/interfaces` | [iowaz/hardware_interfaces](https://github.com/iowaz/hardware_interfaces) | `cnb-klimt` | public | Drops the HIDL `light@2.0` interface so the stock vendor blob is used |
| `build/soong` | [iowaz/build_soong](https://github.com/iowaz/build_soong) | `evox16` | public | Allows the `miui` boot jar packages (`cnb-klimt` is the 12.2 history) |
| `frameworks/native` | [iowaz/frameworks_native](https://github.com/iowaz/frameworks_native) | `evox16` | public | libui stops asking the MediaTek mapper for SMPTE 2094-50 metadata it doesn't list |
| `hardware/xiaomi` | [LineageOS/android_hardware_xiaomi](https://github.com/LineageOS/android_hardware_xiaomi) | `lineage-24.0` | public | Xiaomi HALs (fingerprint, sensors) |
| `device/mediatek/sepolicy_vndr` | [LineageOS/android_device_mediatek_sepolicy_vndr](https://github.com/LineageOS/android_device_mediatek_sepolicy_vndr) | `lineage-24.0` | public | MediaTek vendor SELinux policy |
| `vendor/evolution-priv/keys` | not in git | | **offline only** | Signing keys, generated once (see [Keys](#keys)) |

`vendor/lineage` is plain Evolution-X/vendor_evolution again since evox16: both of our old `cnb-klimt` commits
(the security patch level and the fingerprint override) are upstream in 12.3.

**Only changes that klimt needs get a fork, and everything else stays upstream.** The upstream maintainers test
on real devices; our changes are untested until a build boots on the phone. As of evox17 the local changes are
the device tree, the kernel and vendor repositories, and the three small forks above (build/soong,
frameworks/native, hardware/interfaces), all of which were already in evox15. evox16 had added generic fixes to
twelve more projects; the [evox16 review](docs/evox16-review.md) reverted them. The build/soong and
frameworks/native patches are also exported in the device tree under
[`patches/tree/`](https://github.com/iowaz/android_device_xiaomi_klimt/tree/evox/patches/tree), each with its exact
base commit, patch hash and the expected final tree, for a checkout without the forks. Apply them with
`patches/tree/apply.sh <tree root>`. It refuses a dirty project or a different base, and skips a project whose
tree is already final, so with the forks it does nothing. The evox15 patch set is kept in `patches/tree-evox15/`;
all of it is in 12.3. The iowaz `packages_apps_Settings`, `android_hardware_xiaomi` and
`android_system_memory_libdmabufheap` forks are only used by the evox16 snapshot.

### Without access to the private repositories

- **Blobs:** extract your own from the HyperOS OS3.0.335 OTA with the device tree's `extract-files.py`
  (it reads `proprietary-files.txt`), then put the result in `vendor/xiaomi/klimt`.
- **vendor_evolution:** nothing to do since evox16; the local manifest uses Evolution X's own.

### Why a manifest and not git submodules

An Android tree is about 1,260 git repositories managed by [`repo`](https://gerrit.googlesource.com/git-repo).
`repo` already pins, fetches and checks out every one of them, including ours, through a local manifest.
Submodules would duplicate that for a handful of projects. They would also break `git clone --recursive` for
anyone without access to the private vendor repository. So this repository ships manifests instead:

- [`manifests/local_manifests/klimt.xml`](manifests/local_manifests/klimt.xml) adds the klimt repositories and
  swaps in the forks on top of the latest Evolution X `cnb`. This is what you want for a new build.
- [`manifests/snapshots/`](manifests/snapshots) pins every project at the commit used for each build (latest:
  [`evox17.xml`](manifests/snapshots/evox17.xml), which boots on the phone; [`evox16.xml`](manifests/snapshots/evox16.xml)
  **boot-loops**, see the [evox16 review](docs/evox16-review.md)), as generated by
  [`snapshot-manifest.py`](build-setup/evox/snapshot-manifest.py) from `repo manifest -r`.
  - Evolution X force-pushes `cnb` often. Of the 312 GitHub projects in the evox10 snapshot, 23 were rebased upstream
    within days. Their old commits can still be fetched by SHA for now, but that is not guaranteed.
  - Three are already gone: frameworks/base's base commit, `system_memory_libdmabufheap` (repository deleted)
    and one ThemeIcons commit.
  - So the snapshot is a record of the build, not a guaranteed way to rebuild it bit for bit. A full copy of
    the source disk is the only way to do that.
- [`manifests/local_manifests/klimt-live.xml`](manifests/local_manifests/klimt-live.xml) is the local manifest
  actually installed on the build PC. The klimt projects there were switched to their iowaz branches by hand
  after the first sync.

## The build machine

The builds run on a Windows 11 PC (12 threads, 32 GB RAM, two NVMe SSDs) inside WSL2 (Ubuntu 24.04). The source
and the build output live on two ext4 virtual disks attached to WSL, because an Android build on NTFS (`/mnt/c`)
is far too slow. Since 2026-10-15 everything on the Windows side is in one folder, `D:\android_rom_building`
(`/mnt/d/android_rom_building` in WSL); its own `README.md` is the map, and
[docs/build-pc-layout.md](docs/build-pc-layout.md) describes it and the reorganization that created it.

| What | Where (Windows) | Where (WSL) | Size |
|---|---|---|---|
| Source tree | `vhdx-images\source.vhdx` | `/mnt/wsl/evox/src`, logs in `/mnt/wsl/evox/logs` | ~165 GB of 200 GB |
| Build output, ccache, reference images | `vhdx-images\build.vhdx` | `/mnt/wsl/build/evox-out` (`src/out` is a symlink to it), `/mnt/wsl/build/ccache`, `/mnt/wsl/build/compare` | ~270 GB of 480 GB |
| The WSL distro and its swap | `vhdx-images\wsl-ubuntu-24.04\`, `vhdx-images\wsl-swap.vhdx` | `/` | |
| This repository (the pipeline runs from it) | `repositories\android_custom_rom_building_klimt` | `/mnt/d/android_rom_building/repositories/...` | |
| Readiness records, verifier reports, phone logs | `diagnostics\` | | |
| Finished images (what you flash) | `output-zips\<build>\` | | ~5.4 GB per build |
| adb / fastboot | `tools\platform-tools` | | |
| Phone partition backup, stock firmware, key backup | `backups\` | | |

`.wslconfig`:

```ini
[wsl2]
memory=28GB
processors=12
swap=48GB
swapFile=D:\\android_rom_building\\vhdx-images\\wsl-swap.vhdx

[experimental]
autoMemoryReclaim=gradual
```

The soong analysis at the start of every build needs about 25 GB of RAM plus up to 24 GB of swap. While it
runs, WSL may stop answering (`Wsl/Service/WSAETIMEDOUT`). The build keeps going; wait for it.

The scripts in [`build-setup/`](build-setup) use the build PC's absolute paths (`/mnt/d/android_rom_building`,
`/mnt/wsl/...`); the pipeline keeps all of them in one file,
[`paths.py`](build-setup/evox/pipeline/paths.py). On another machine, change that file.

## How a build goes

### 1. One-time setup

1. Install WSL2 with Ubuntu 24.04, put the `.wslconfig` above in place, and install the usual AOSP/LineageOS
   build packages plus `repo`, `git-lfs`, `ccache` and `python3`.
2. Create and format the two disks (elevated PowerShell), in [`build-setup/windows`](build-setup/windows):
   - Build disk: [`create-vhdx.ps1`](build-setup/windows/create-vhdx.ps1), then
     [`format-build-disk.ps1`](build-setup/windows/format-build-disk.ps1).
   - Source disk: [`create-evox-disk.ps1`](build-setup/windows/create-evox-disk.ps1).
3. After every Windows reboot or `wsl --shutdown`, run
   [`mount-disks.ps1`](build-setup/windows/mount-disks.ps1) elevated to attach both disks again, and
   [`wsl-keepalive.ps1`](build-setup/windows/wsl-keepalive.ps1) so WSL keeps running while a build is detached.

### 2. Sources

```bash
mkdir -p /mnt/wsl/evox/src /mnt/wsl/evox/logs && cd /mnt/wsl/evox/src
repo init -u https://github.com/Evolution-X/manifest -b cnb --git-lfs --depth=1 --no-clone-bundle
mkdir -p .repo/local_manifests
cp <this repo>/manifests/local_manifests/klimt.xml .repo/local_manifests/
repo sync -c --no-tags --no-clone-bundle -j8      # build-setup/evox/sync.sh; about an hour, ~140 GB
bash device/xiaomi/klimt/patches/tree/apply.sh .  # reports "already final" with the forks
```

For a release, the tree is synced to a frozen manifest instead (every project at an exact commit):
[`make-frozen.py`](build-setup/evox/pipeline/make-frozen.py) derives it from the previous one, and the frozen
manifests are kept in the private `iowaz/evox16_manifest` repository (one branch per build).

### 3. Keys

Builds are signed with private keys, not the public AOSP test keys:

```bash
git clone https://github.com/Evolution-X/vendor_evolution-priv_keys-template vendor/evolution-priv/keys
cd vendor/evolution-priv/keys && ./keys.sh
```

[`keys-generate.sh`](build-setup/evox/keys-generate.sh) does this once, refuses to regenerate, checks that the
certificates are not the AOSP test ones, and writes a tarball backup.

- **Generate the keys once and keep an offline copy.** A build signed with different keys cannot be installed
  over the existing one without wiping data.
- **Never commit or upload the keys.**

### 4. Build

[`env.sh`](build-setup/evox/env.sh) holds the build environment. By hand, a build is:

```bash
source build/envsetup.sh
lunch lineage_klimt-cp2a-user
m -j12 installclean    # empty the staging directories the images are packed from
m -j12 updatepackage   # fastboot image zip: out/target/product/klimt/lineage_klimt-img.zip
```

On the build PC it goes through the [pipeline](build-setup/evox/pipeline) (its README has the details). The
build name comes from the attempt ID, and every path from [`paths.py`](build-setup/evox/pipeline/paths.py):

```bash
P=/mnt/d/android_rom_building/repositories/android_custom_rom_building_klimt/build-setup/evox/pipeline
export KLIMT_BUILD=evox18
python3 -B $P/ready.py <frozen manifest>                 # gates -> diagnostics\builds\evox18\BUILD_READY.json
bash $P/start.sh evox18-attempt01 /mnt/d/android_rom_building/diagnostics/builds/evox18/BUILD_READY.json
python3 -B $P/controller.py status evox18-attempt01
python3 -B $P/promote.py evox18-attempt01                # -> D:\android_rom_building\output-zips\evox18
```

- The readiness JSON pins the whole frozen manifest (every project HEAD, checked clean before and after), the
  five public signing certificates, the disk budget and the checks that must pass first.
- One detached controller runs `m -j12 installclean`, `m -j12 updatepackage`, then the verifier. Each attempt
  gets its own ID and folders, and nothing from an earlier attempt is overwritten.
- The controller and its watchdog identify the build by PID, `/proc` start time, boot ID and session. They stop
  only that build (disk below 10 GB on D: or 2 GB on either ext4 disk) and never restart one.
- A fixed verifier can re-check a successful build without rebuilding (`verify.py --recheck`).

There is no focused precheck any more: `m <module>` installs into the staging directories the images are packed
from, and that is how evox16 shipped a stray Telecom app. The per-build copies of this tooling (evox16, evox17)
and the evox1-15 scripts are in [`build-setup/archive`](build-setup/archive).

Typical times on this PC:

| Build | Analysis | Total |
|---|---|---|
| Full build (~188k ninja steps) | ~40 min | ~6 h |
| Incremental build after device-tree changes | ~30 min | 1-2 h |
| Same source again (evox18 after evox17) | ~30 min | under 1 h |

### 5. Verify

[`verify.py`](build-setup/evox/pipeline/verify.py) runs in a fresh, attempt-only folder, and only for a ZIP
produced by that attempt (hash, size and mtime from the build's own exit record). It requires:
- the must-hold checks ([`legacy/musthold.sh`](build-setup/evox/pipeline/legacy/musthold.sh)): the AVB chain;
  `super_empty`, `fastboot-info.txt` and `android-info.txt` unchanged; the device tree blob and DTBO identical
  to the phone's own; all 888 kernel modules matching the kernel's symbol CRCs;
- all 165 historical fix checks (`legacy/fixcheck*.sh`), matched by name;
- seven image checks in [`image-checks/check_image.py`](build-setup/evox/pipeline/image-checks/check_image.py):
  - policy: recompiled policy, the exact permissive domains (`su`, as upstream), device labels, upstream sepolicy;
  - patch packaging: MIUI jars, libui/Gralloc, lights, upstream libcore;
  - private vendor compatibility: blob hashes, ELF dependencies, the allocator symbols the blobs use, Wi-Fi shim;
  - Health semantics;
  - GMS/themes/apps;
  - Doze packaging: TouchBridge bytecode, UDFPS/sensor producers, resolved AOD defaults;
  - install integrity: every staged file is in the build's install list, no package is installed twice, and
    the Telecom app (bound to its producer, binder contract read from its DEX) matches the framework's loader.

Only then does it stage the delivery, which [`promote.py`](build-setup/evox/pipeline/promote.py) moves to
`D:\android_rom_building\output-zips\<build>\`: `lineage_klimt-<build>-img.zip`, its `-flash.bat`/`-flash.sh`
helpers, `SHA256SUMS`, `RESULTS.json`, `COMPARISON.md`, `README.md` and `VERIFIED.txt`. **`VERIFIED.txt` is not
a phone test**: it says "NOT boot-tested".

The must-hold checks compare against reference images (an earlier build, misakazip's build, the phone's own
partitions) that are not in this repository.

### 6. Flash

From `D:\android_rom_building\output-zips\<build>\`, with the phone in the bootloader (`adb reboot bootloader`):

```bat
lineage_klimt-<build>-flash.bat /flash
```

It checks the ZIP's hash and that the phone is a `klimt`, runs `fastboot update --skip-reboot` with the
`fastboot.exe` in `D:\android_rom_building\tools\platform-tools`, and leaves the reboot to you.

- **First install, or after changing keys:** wipe afterwards with `fastboot -w` and Format data in recovery.
- **Updating a build signed with the same keys:** flash without a wipe ("dirty"), as every build since evox8.

Firmware is not part of the ROM. Both slots should have the same HyperOS firmware (OS3.0.335) before anyone
relies on an A/B OTA, because the OTA writes to the other slot.

## Lessons learned

- **Stick to one build backend.** `env.sh` sets `SOONG_NINJA=ninja`. Switching between ninja and siso throws
  away the incremental state and costs a full rebuild.
- **Do not set `OUT_DIR` to a path outside the tree.** Soong's test packaging breaks. Make `out` a symlink to the
  other disk instead.
- **Watch the host disk.** The VHDX files grow during a build, and a full host disk corrupts the ext4 inside
  them. [`dwatch.sh`](build-setup/archive/pre-evox16/dwatch.sh) stops the build when D: drops below 10 GB.
- **Keep `.repo/manifests` on the commit the tree was synced from.** The build runs `repo manifest -r`, and an
  aborted sync once left a newer manifest there that broke a build an hour in.
- **Upstream moves fast.** Evolution X rebases `cnb`, so compare commits by subject, not SHA. Keep every local
  change in a fork or in `patches/tree`, never only in the tree.
- **The vendor is A15, the system is A17.** The stock camera blobs expect Android 15's `libui` (`GraphicBuffer`
  is 256 bytes there, 3,376 in Android 17). The device tree ships the stock `libui` as `libui_vendor.so` and
  relinks those blobs to it, as HyperOS itself does.
- **Several agents may work on the same tree.** Check `git reflog` and recently changed files before building,
  and always build through `env.sh`.
- **A new file in a globbed directory reruns the whole Soong analysis.** Adding a `.te` file or a source file
  that a glob picks up cost about 40 minutes and 25 GB of RAM (plus swap) on this PC before ninja even started.
- **The kernel logs at most 5 SELinux denials per second.** Apps that probe for root (banking and delivery
  apps) can fill that budget and hide everything else. Close them before looking for denials, and check
  `audit_lost` in the kernel log.
- **Check SELinux changes before the build, not during it.** `ninja -t commands -s <target>` prints the build's own
  m4, checkpolicy and secilc commands for the vendor policy. Replaying them on the edited sources (outputs in /tmp)
  compiles the whole policy with every neverallow in a few minutes, as long as no new `.te` file was added.
- **A log flood names its thread.** SurfaceFlinger's "Mapper error: 7" came from the RenderEngine and
  RegionSampling threads, which pointed straight at an Android 17 metadata request the Android 16 mapper doesn't
  support. Check the TID before guessing.

- **Never build module goals in the tree you package.** `m <module>` installs that module into
  `out/target/product/<device>/`, and the images are packed from that directory, not from the product's install
  list. evox16's precheck ran `m Telecom` for one of our patches; the incremental build kept the stray legacy
  Telecom app next to TelecomShim, and the phone boot-looped. Run `m installclean` before a release build and
  check that the image only holds the product's installs.
- **A checker failure is not an image failure.** The image checks exit 1 for a real defect and 2 for missing
  tools or evidence. In evox16 all four stops were checker bugs: a timeout, a regex, wrong source strings and a
  Make parser. Each was confirmed against the reference builds before the checker was changed, then the same ZIP
  was re-verified without rebuilding.
- **Image verification is not a boot test, and evidence nobody reads is not a check.** evox16 passed every
  compile, policy and image check and still boot-looped. Its verifier even listed the duplicate Telecom package,
  as information only. Make such findings fail the build. Keep the last working ZIP next to the new one and be
  ready to restore it; a dirty restore to the same slot with the same keys worked.
- **Trust upstream over our own fixes.** The upstream maintainers test on devices; our changes are untested until
  the phone boots them. evox16 carried twelve "improvements" klimt did not need. Change upstream code only for a
  failure seen on klimt, or for something klimt cannot work without.
- **A shallow checkout can't push a fork.** `repo sync --depth=1` leaves git unable to tell GitHub what it
  already has, and large pushes fail with HTTP 500.
  [`gh_replay_commits.py`](build-setup/evox/tools/gh_replay_commits.py) recreates the commits through the
  GitHub API instead, and only moves the branch when the SHAs match.

The build history, from the first failed build to evox17, is in [docs/history.md](docs/history.md).

## Running it in CI

GitHub's hosted runners cannot build this: a build needs about 450 GB of disk, 28 GB or more of RAM and several
hours. A CI setup needs a self-hosted runner, or a cloud VM with:

- Ubuntu 24.04, 16 or more cores, 64 GB RAM (or 32 GB plus 48 GB swap), and 500 GB of SSD. Keep the ccache
  between runs.
- A GitHub token that can read the private vendor repository.
- The signing keys as an encrypted secret, unpacked into `vendor/evolution-priv/keys` for the build only.

The job is then steps 2 to 5 above:

1. `repo init` and `repo sync` with the local manifest.
2. `apply.sh`.
3. Unpack the keys.
4. `lunch` and `m updatepackage`.
5. Run the checks.
6. Upload the image zip and its SHA-256 as a build artifact or release.

## Credits

Building a custom ROM is pretty cool. It is complex, but it is not out of this world. I could not have done
this one without Claude (Anthropic's AI, working through Claude Code), which did most of the investigation,
building, debugging and checking behind this repository and the device-tree commits.

Just as surely, none of this exists without the community:

- **[misakazip](https://github.com/misakazip)**, who explored the klimt ecosystem first: the device tree, the
  kernel and the bring-up in [misakazip-dev](https://github.com/misakazip-dev). **Without that work, this ROM
  could not have been done.**
- **The Evolution X developers**, whose ROM this is.
- **LineageOS** and **AOSP**, which everything is built on.
- The authors of every change picked into these trees, credited in each commit.

Thank you.

## Dedication

Academic work, like a thesis or a dissertation, usually has a page dedicated to the people behind it. That is
rare in software development, but this project deserves one.

To my brothers, to Carol and to Mendonça:

- **João Gabriel ([@jgcl](https://github.com/jgcl))**, my brother, also a software engineer, who always
  motivated me to follow this career. I only became a developer because of him, more than 15 years ago, when I
  was 14 or 15.
- **[Vinicius](http://lattes.cnpq.br/8470339884809920)**, my oldest brother: a fucking genius, and one of the
  coolest human beings I know. I look up to him very much.
- **Carol ([@carolsantossilva](https://github.com/carolsantossilva))**, my girlfriend and also a software
  developer, who encourages me a lot and lets me spend a few Saturdays on my "Coisinhas de menino".
- **[Luiz Mendonça](https://www.linkedin.com/in/luiz-mendon%C3%A7a-561b8b17/)**, known simply as Mendonça: a
  long-time leader (and boss, hahaha) who taught me a lot in the past and still does.
