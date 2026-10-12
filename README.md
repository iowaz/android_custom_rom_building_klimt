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

The ROM is **Evolution X 12.2** (branch `cnb`, Android 17, build ID CP2A), built as `lineage_klimt-cp2a-user`,
signed with my own private keys, with Google apps included (`WITH_GMS=true`).

## Repositories

| Path in the source tree | Repository | Branch | Visibility | What it is |
|---|---|---|---|---|
| everything else | [Evolution-X/manifest](https://github.com/Evolution-X/manifest) | `cnb` | public | Evolution X (AOSP + LineageOS + Evolution X projects) |
| `device/xiaomi/klimt` | [iowaz/android_device_xiaomi_klimt](https://github.com/iowaz/android_device_xiaomi_klimt) | `evox` | public | Device tree, fork of [misakazip-dev](https://github.com/misakazip-dev/android_device_xiaomi_klimt). Also holds `patches/tree/` (see below) |
| `kernel/xiaomi/klimt` | [iowaz/android_kernel_xiaomi_klimt](https://github.com/iowaz/android_kernel_xiaomi_klimt) | `17.0` | public | Kernel source, fork of misakazip-dev (unchanged) |
| `kernel/xiaomi/klimt-prebuilt` | [misakazip-dev/android_kernel_xiaomi_klimt-prebuilt](https://github.com/misakazip-dev/android_kernel_xiaomi_klimt-prebuilt) | `17.0` | public | Builds the kernel from source |
| `vendor/xiaomi/klimt` | iowaz/proprietary_vendor_xiaomi_klimt | `evox` | **private** | Proprietary blobs extracted from HyperOS OS3.0.335 plus MIUI Camera. Uses Git LFS |
| `vendor/lineage` | iowaz/vendor_evolution | `cnb-klimt` | **private** | Evolution-X/vendor_evolution plus the security patch level and fingerprint override commits |
| `hardware/interfaces` | [iowaz/hardware_interfaces](https://github.com/iowaz/hardware_interfaces) | `cnb-klimt` | public | Drops the HIDL `light@2.0` interface so the stock vendor blob is used |
| `build/soong` | [iowaz/build_soong](https://github.com/iowaz/build_soong) | `cnb-klimt` | public | Allows the `miui` boot jar packages |
| `hardware/xiaomi` | [LineageOS/android_hardware_xiaomi](https://github.com/LineageOS/android_hardware_xiaomi) | `lineage-24.0` | public | Xiaomi HALs (fingerprint, sensors) |
| `device/mediatek/sepolicy_vndr` | [LineageOS/android_device_mediatek_sepolicy_vndr](https://github.com/LineageOS/android_device_mediatek_sepolicy_vndr) | `lineage-24.0` | public | MediaTek vendor SELinux policy |
| `vendor/evolution-priv/keys` | not in git | | **offline only** | Signing keys, generated once (see [Keys](#keys)) |

Eight Evolution X projects carry small local changes but have no fork: bionic, frameworks/base, frameworks/av,
frameworks/native, frameworks/opt/telephony, packages/apps/Evolver, packages/modules/Bluetooth and system/core.
Most of the changes are upstream picks: the October 2026 security fixes, the Play Integrity fix default, and custom
ROM hiding. The frameworks/native one is ours: libui stops asking the MediaTek mapper for a metadata type it doesn't
know. They are kept as patches in the device tree under
[`patches/tree/`](https://github.com/iowaz/android_device_xiaomi_klimt/tree/evox/patches/tree), applied with
`patches/tree/apply.sh <tree root>`. Patches that are already in the tree are skipped.

### Without access to the private repositories

- **Blobs:** extract your own from the HyperOS OS3.0.335 OTA with the device tree's `extract-files.py`
  (it reads `proprietary-files.txt`), then put the result in `vendor/xiaomi/klimt`.
- **vendor_evolution:** use Evolution X's own `vendor_evolution` by removing its `extend-project` line from the
  local manifest. Both of our commits came from upstream (the October 2026 security patch level and the bluejay
  fingerprint override), so a recent `cnb` already has them.

### Why a manifest and not git submodules

An Android tree is about 1,260 git repositories managed by [`repo`](https://gerrit.googlesource.com/git-repo).
`repo` already pins, fetches and checks out every one of them, including ours, through a local manifest.
Submodules would duplicate that for a handful of projects. They would also break `git clone --recursive` for
anyone without access to the two private repositories. So this repository ships manifests instead:

- [`manifests/local_manifests/klimt.xml`](manifests/local_manifests/klimt.xml) adds the klimt repositories and
  swaps in the forks on top of the latest Evolution X `cnb`. This is what you want for a new build.
- [`manifests/snapshots/`](manifests/snapshots) pins every project at the commit used for each build (latest:
  [`evox15.xml`](manifests/snapshots/evox15.xml), attempt 2 verified), as generated by
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

The builds run on a Windows 11 PC (12 threads, 32 GB RAM) inside WSL2 (Ubuntu 24.04). The source and the build
output live on two ext4 virtual disks attached to WSL, because an Android build on NTFS (`/mnt/c`) is far too slow.

| What | Where (Windows) | Where (WSL) | Size |
|---|---|---|---|
| Source tree | `D:\EvoXBuild\evox.vhdx` | `/mnt/wsl/evox/src`, logs in `/mnt/wsl/evox/logs` | ~155 GB of 200 GB |
| Build output, ccache | `D:\WitAquaBuild\build.vhdx` | `/mnt/wsl/build/evox-out` (`src/out` is a symlink to it), `/mnt/wsl/build/ccache` | ~270 GB of 480 GB |
| Scripts (this repo's `build-setup/`) | `C:\XiaomiBuilds\build-setup` | `/mnt/c/XiaomiBuilds/build-setup` | |
| Finished images | `D:\WitAquaBuild\out-evox` | `/mnt/d/WitAquaBuild/out-evox` | ~5.6 GB per build |

`.wslconfig`:

```ini
[wsl2]
memory=28GB
processors=12
swap=48GB
swapFile=C:\\WSL\\swap.vhdx

[experimental]
autoMemoryReclaim=gradual
```

The soong analysis at the start of every build needs about 25 GB of RAM plus up to 24 GB of swap. While it
runs, WSL may stop answering (`Wsl/Service/WSAETIMEDOUT`). The build keeps going; wait for it.

The scripts in [`build-setup/`](build-setup) are copies of the ones used on the build PC, with the same layout,
so their absolute paths (`/mnt/c/XiaomiBuilds/build-setup/...`, `/mnt/wsl/...`, `D:\...`) are the ones in the
table above. To restore them, copy `build-setup/` to `C:\XiaomiBuilds\build-setup`. On another machine, change
those paths.

## How a build goes

### 1. One-time setup

1. Install WSL2 with Ubuntu 24.04, put the `.wslconfig` above in place, and install the usual AOSP/LineageOS
   build packages plus `repo`, `git-lfs`, `ccache` and `python3`.
2. Create and format the two disks (elevated PowerShell):
   - Build disk: [`create-vhdx.ps1`](build-setup/create-vhdx.ps1), then
     [`format-build-disk.ps1`](build-setup/format-build-disk.ps1).
   - Source disk: [`create-evox-disk.ps1`](build-setup/evox/create-evox-disk.ps1).
3. After every Windows reboot or `wsl --shutdown`, run
   [`mount-disks.ps1`](build-setup/evox/mount-disks.ps1) elevated to attach both disks again.

### 2. Sources

```bash
mkdir -p /mnt/wsl/evox/src /mnt/wsl/evox/logs && cd /mnt/wsl/evox/src
repo init -u https://github.com/Evolution-X/manifest -b cnb --git-lfs --depth=1 --no-clone-bundle
mkdir -p .repo/local_manifests
cp <this repo>/manifests/local_manifests/klimt.xml .repo/local_manifests/
repo sync -c --no-tags --no-clone-bundle -j8      # build-setup/evox/sync.sh; about an hour, ~140 GB
bash device/xiaomi/klimt/patches/tree/apply.sh .  # the seven patched projects
```

On a newer `cnb` some patches may already be upstream (skipped) or may need a small rebase (`git am -3` stops
and says where).

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

[`env.sh`](build-setup/evox/env.sh) holds the build environment and [`build.sh`](build-setup/evox/build.sh)
runs it:

```bash
source build/envsetup.sh
lunch lineage_klimt-cp2a-user
m -j12 updatepackage   # fastboot image zip: out/target/product/klimt/lineage_klimt-img.zip
m -j12 otapackage      # optional: A/B OTA zip
```

On the build PC this is one detached command, followed by a disk watchdog:

```bash
bash /mnt/c/XiaomiBuilds/build-setup/evox/start-build.sh evox14 updatepackage   # log: /mnt/wsl/evox/logs/evox14.log
bash /mnt/c/XiaomiBuilds/build-setup/evox/progress.sh evox14                    # one-line status
```

The evox15 controlled test build uses [`build-evox15.sh`](build-setup/evox/build-evox15.sh),
which starts the same build plus the 10 GB disk watchdog. Its source snapshot is pinned to device commit
`a528622c4f52e603a1f3cfa4d998b60da6e0e5c9` and private vendor commit
`74d378be9f0b832f2c83284474a0f5da72062ca2`. The initial attempt failed packaging with exit 1 at 10:33 Sao Paulo on
2026-10-12. Attempt 2 started at 11:01 Sao Paulo with the reviewed naming repair.
Attempt 2 completed at 11:51 with exit 0 in 50 minutes 29 seconds and passed image verification.
It has not been flashed; camera and charging runtime tests remain pending.
See [the charging and camera notes](docs/evox15.md) before treating it as a release.

Start this wrapper once from WSL, after creating `C:\XiaomiBuilds\debug\noise15`:

```bash
setsid nohup bash /mnt/c/XiaomiBuilds/build-setup/evox/build-evox15.sh >/dev/null 2>&1 </dev/null &
```

Use one persistent monitor/verification supervisor after starting the build:

```powershell
New-Item -ItemType Directory -Force C:\XiaomiBuilds\debug\noise15
powershell -File C:\XiaomiBuilds\build-setup\evox\fix15\supervise15.ps1
```

The supervisor waits for the exit marker before running verification and refuses another active supervisor.
It exits without extraction if the build failed; a failed build requires a deliberate new build invocation.
It retries WSL connection timeouts without restarting the build. [`health15.py`](build-setup/evox/fix15/health15.py)
records Ninja progress, log size/time, process count and build-subtree CPU time, including reaped children.
A quiet analysis step is normal while CPU time increases. Flag a possible freeze only when progress, log size
and CPU time all stay unchanged for at least 30 minutes. Monitor logs are under `debug/noise15/`.

Typical times on this PC:

| Build | Analysis | Total |
|---|---|---|
| Full build (~188k ninja steps) | ~40 min | ~6 h |
| Incremental build after device-tree changes | ~30 min | 1-2 h |

### 5. Verify

[`verify-evox14.sh`](build-setup/evox/verify-evox14.sh) copies the image zip to `out-evox` (with `SHA256SUMS`),
unpacks every image and runs two sets of checks.

[`musthold.sh`](build-setup/evox/cmp/musthold.sh) runs before anything else and covers:
- The AVB chain verifies.
- `super_empty` and `fastboot-info.txt` are unchanged.
- The device tree blob matches the phone's own.
- All 888 kernel modules match the kernel's symbol CRCs.

[`fixcheck*.sh`](build-setup/evox/cmp) checks that every fix from every build so far is still in the images.

For evox15, [`verify-evox15.sh`](build-setup/evox/verify-evox15.sh) also checks the exact experimental HIS
blob SHA/BuildId, both custom Health modules and their packaged binaries, and retained init/VINTF files.
The strict report validator accepts only two documented legacy false failures and requires all ten new checks.
Health provenance follows current generated Soong module/install rules through the built binaries into the package.
VINTF checks compare packaged files to processed build output and retain strict source HAL semantics.
Success is recorded in `C:\XiaomiBuilds\compare\evox15\VERIFIED.txt`; this marker is not a phone test.
Use the queued supervisor rather than launching another extraction while it is waiting or running.

The must-hold checks compare against reference images (an earlier build, misakazip's build, the phone's own
partitions) that are not in this repository.

### 6. Flash

[`flash-evox.ps1`](build-setup/evox/flash-evox.ps1) runs `adb reboot bootloader`, then
`fastboot update --skip-reboot lineage_klimt-<name>-img.zip`:

- **First install, or after changing keys:** wipe afterwards with `fastboot -w` and Format data in recovery.
- **Updating a build signed with the same keys:** flash without a wipe ("dirty").

Firmware is not part of the ROM. Both slots should have the same HyperOS firmware (OS3.0.335) before anyone
relies on an A/B OTA, because the OTA writes to the other slot.

## Lessons learned

- **Stick to one build backend.** `env.sh` sets `SOONG_NINJA=ninja`. Switching between ninja and siso throws
  away the incremental state and costs a full rebuild.
- **Do not set `OUT_DIR` to a path outside the tree.** Soong's test packaging breaks. Make `out` a symlink to the
  other disk instead.
- **Watch the host disk.** The VHDX files grow during a build, and a full host disk corrupts the ext4 inside
  them. [`dwatch.sh`](build-setup/evox/dwatch.sh) stops the build when D: drops below 10 GB.
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

The build history, from the first failed build to evox15, is in [docs/history.md](docs/history.md).

## Running it in CI

GitHub's hosted runners cannot build this: a build needs about 450 GB of disk, 28 GB or more of RAM and several
hours. A CI setup needs a self-hosted runner, or a cloud VM with:

- Ubuntu 24.04, 16 or more cores, 64 GB RAM (or 32 GB plus 48 GB swap), and 500 GB of SSD. Keep the ccache
  between runs.
- A GitHub token that can read the two private repositories.
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
