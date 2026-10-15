# evox17: Evolution X 12.3 with only what klimt needs

Status on 2026-10-15: built and image-checked (`evox17-attempt01`, verifier recheck `recheck01`), then
**dirty-flashed to slot b, where it boots** (see [First boot on the phone](#first-boot-on-the-phone)). The hands-on
checks (calls, camera, fingerprint, AOD) are still to do.

evox17 is what evox16 should have been: Evolution X 12.3 (`cnb`, Android 17, `CP2A.260605.016`) with the evox15
device setup and nothing else. It follows the [evox16 review](evox16-review.md).

## Source

The frozen manifest is [`manifests/snapshots/evox17.xml`](../manifests/snapshots/evox17.xml): 1,263 projects.
All 315 GitHub pins were fetchable from their branches when it was written. 313 of them are exactly their
branch head; the other two are the deliberate evox15 pins below.

- **Upstream everywhere**, at the branch heads of 2026-10-15. Since evox16 that brought:
  - three frameworks_base commits: two re-pushed font fixes and a Pixel-features tweak for Tensor;
  - an Evolver font-style change;
  - LineageOS updates: LatinIME, Launcher3, APNs, WebView, and Qualcomm projects klimt does not build.
- **Local changes, all already in evox15:**
  - device tree [`43b71ec`](https://github.com/iowaz/android_device_xiaomi_klimt/commit/43b71ecbde010c3444dfb297e9dbd755b1b443c5):
    the evox15 device plus the black-AOD product overlay. The doze double-tap bridge and the allocator flag are
    reverted, and `patches/tree` holds only the two patches below;
  - build/soong `evox16` fork: the MIUI boot jar packages;
  - frameworks/native `evox16` fork: libui's SMPTE 2094-50 guard for the MediaTek mapper;
  - hardware/interfaces `cnb-klimt` fork: AIDL-only lights.
- **Kept at the evox15 commits:**
  - kernel and kernel prebuilt build;
  - proprietary vendor `74d378be`;
  - LineageOS hardware/xiaomi `af5766ac`: one newer upstream commit, a translation import;
  - MediaTek vendor policy `117a8de2`: 20 newer LineageOS commits, mostly labels for other MediaTek chips. They are
    not part of the move to 12.3 and can come in a later build.
- **Back on upstream:** packages/apps/Settings, hardware/xiaomi and system/memory/libdmabufheap. The iowaz `evox16`
  branches remain, so the evox16 snapshot still resolves.

**Behaviour that changes from evox15, all from upstream:**
- Evolution X 12.3 features: ThemeStore, more Quick Settings, font and lockscreen options, a separate doze
  double-tap setting. Double tap to wake works as before; the new doze setting does not arm the panel.
- The `su` SELinux domain is permissive on user builds (upstream's choice). On a user build nothing can enter it
  without a root solution.
- The ION-free allocator, with the same exported entry points the blobs use.

## Build

Tooling: [`build-setup/evox/evox17`](../build-setup/evox/evox17), the evox16 controller with these changes:
- no focused precheck;
- `m installclean` before `m updatepackage`, failing if any staged partition survives;
- seven image checks, including the new `install_integrity` (see the [review](evox16-review.md#what-changes-in-the-process));
- the checks for evox16's optional patches now check that those projects are the reviewed upstream commits;
- the marker says "static image checks passed, NOT boot-tested".

The frozen manifest was generated with [`make-frozen.py`](../build-setup/evox/evox17/make-frozen.py) from
evox16's. It is on the private `iowaz/evox16_manifest` repository, branch `evox17-manifest`. The readiness record
([`ready/BUILD_READY.evox17-attempt01.json`](../build-setup/evox/evox17/ready/BUILD_READY.evox17-attempt01.json))
passed eight gates, including the evox16 negative test of the new check and the five semantic source checks.

`evox17-attempt01`:
- `m -j12 installclean` took 9 s;
- `m -j12 updatepackage` exited 0 in **1h17m37s**: 16,391 Ninja steps, incremental, with Soong analysis at about
  27 GB of RAM plus swap.

## Verification

- **Original verification (attempt01).** Archive gate and must-hold checks: AVB; `super_empty`,
  `fastboot-info.txt` and `android-info.txt` identical to the author build and build9; DTBO and `vendor_boot` DTB
  identical to the phone's slot b; **888 modules, 0 CRC mismatches**; kernel `6.6.142-android15-8-klimt-4k`. Also
  **all 165 historical fix checks** and **all seven image checks**:

  | Check | Assertions | Notes |
  |---|---|---|
  | policy | 31 | permissive domains exactly `su`, normal and recovery, as upstream |
  | patch packaging | 33 | MIUI boot jars, the SMPTE guard in the compiled libui, lights, upstream libcore |
  | private compatibility | 100 | blobs, ELF dependencies, upstream libdmabufheap exporting all 15 symbols the blobs use, libion stub, Wi-Fi shim |
  | Health semantics | 45 | |
  | GMS/themes/apps | 674 | |
  | Doze packaging | 62 | evox15 TouchBridge; AOD stays black |
  | install integrity | 9 | no stray staged file; image APK set = staged = product installs; only the two evox15 overlay pairs duplicated; **TelecomShim is the only `com.android.server.telecom`** |

- **Recheck after the second Codex review.** The [Codex review of evox17](evox17-review/codex-independent-review.md)
  found the source matched the plan, agreed to keep the black-AOD overlay and the SMPTE guard, and accepted the
  upstream allocator and `su` policy. It found three verifier gaps ([findings](evox17-review/codex-findings.json)):
  - *E17-001.* The Telecom gate trusted the path. It now binds the APK to its producer and reads the
    `TelecomService` binder contract from the DEX. On the real APKs, evox16's `Telecom.apk` reads as legacy and
    `TelecomShim.apk` as mainline.
  - *E17-002.* APK symlinks are now rejected; none exist.
  - *E17-003.* The vendor `libdmabufheap` and `libion` are now bound to their producers.
  - Tool output is now decoded tolerantly, because `dexdump` of the legacy Telecom APK emits non-UTF-8 bytes.

  The revised checker passed 45 unit tests and a dry run of all seven modes, then a verifier-only recheck of the
  same ZIP (`recheck01`, with [`TOOL_REVIEW.recheck01.json`](../build-setup/evox/evox17/ready/TOOL_REVIEW.recheck01.json)).

## Compared with evox15 (the build that runs on the phone)

The installed APK lists differ only by upstream changes. 461 APKs in evox15 and 462 in evox17:

- **Added:**
  - ThemeStore (`AxThemeStore`);
  - the GMS refresh in Evolution X 12.3: `CustomizationBundlePrebuiltFullVersion`, `PixelSearchPrebuilt`, new
    versioned `SetupWizard*` directories.
- **Removed or replaced:**
  - the retired ThemeIcons overlay (`PixelLauncherIconsOverlay`);
  - `PersistentBackgroundServices`;
  - two versioned GMS prebuilts that upstream moved to *older* versions: `DeviceConnectivityServicePrebuilt`
    26.03 to 26.01, and `GoogleRestorePrebuilt` v1068888 to v1054408.

  Watch those two after the first boot; Play Store updates in `/data`, if any, still take precedence.
- **Vendor and odm:** the same files as evox15, except one new charger image (`battery_overheat.png`).

## Image (not boot-tested)

- Archive: `lineage_klimt-evox17-img.zip`, 5,661,595,211 bytes, the same 19 fastboot entries as evox15.
- SHA-256: `5961c6a7546d3b3dfbdb8642263bd7e619eabd12926da8a9aa39b08e413cf958`.
- In `D:\WitAquaBuild\out-evox`, with:
  - `lineage_klimt-evox17-flash.bat`/`.sh`: they check the hash and the `klimt` product, need `/flash` or
    `--flash`, run `fastboot update --skip-reboot` (data kept) and leave the reboot to you;
  - `VERIFIED-evox17.txt` ("NOT boot-tested"), `SHA256SUMS-evox17`, `RESULTS-evox17.json`,
    `COMPARISON-evox17.md`, `SOURCE-evox17.xml`, `README-evox17.md`.
- `BOOTLOOPS-DO-NOT-FLASH-evox16.txt` sits next to the evox16 files.

## First boot on the phone

On 2026-10-15 at 07:27 Sao Paulo, `lineage_klimt-evox17-img.zip` was flashed over evox15
(`EvolutionX-17.0-20261012-klimt-12.2`) on slot b with `fastboot update --skip-reboot`, without `-w`
([flash log](evox17-firstboot/flash.txt)): exit 0, 0 errors, no erase, slot still b. The evox15 ZIP was checked
(`63982b33…3f90a`) and kept ready to restore.

- `sys.boot_completed=1` **48 s** after the reboot. The build is `EvolutionX-17.0-20261015-klimt-12.3`, verified
  boot is green and the user data is intact: the user unlocked, and there are 706 packages (705 before; the image
  has one more APK).
- `system_server` kept the same PID for the first five minutes. There are no crashes, no new tombstones and no
  dropbox entries.
- **Telecom:** `/system/priv-app/TelecomShim/TelecomShim.apk` is the only `com.android.server.telecom`.
  `dumpsys telecom` reports `Init Path: On mainline`, and no "incorrect interface" line appears in the logs
  ([output](evox17-firstboot/telecom.txt)).
- **Radio:** the SIM in slot 2 is loaded and in service on LTE, with IMS registered. Mobile data and Wi-Fi
  networks are up.
- **Other hardware:** 8 cameras listed; the fingerprint provider and the UDFPS wake sensor are present; charging
  over USB; SELinux enforcing.
- **SurfaceFlinger:** 0 "Mapper error" lines, so the SMPTE 2094-50 guard works.
- **SELinux denials** ([checks](evox17-firstboot/phonecheck-t5min.txt)) are the known ones: MiSys reading
  `vendor_mtkcam_prop` (an open item since evox14) and apps probing for root. The `gesture_prop` denial is from
  `adb shell getprop`, which may not read that property; TouchBridge itself is running.

The full logs (logcat, events, dropbox, getprop) stay on the build PC in
`C:\XiaomiBuilds\debug\evox17\device-firstboot-20261015\`.

## Before calling it ready

Items 1 and 2 passed on the first boot; the rest needs hands-on testing.

1. `adb shell getprop sys.boot_completed` returns 1;
2. `system_server` stays up. `adb shell pm list packages -f com.android.server.telecom` shows
   `/system/priv-app/TelecomShim/TelecomShim.apk` only, and logcat has no "incorrect interface" crash;
3. the lock screen unlocks; calls (in and out, VoLTE), SMS, mobile data, SIM/eSIM;
4. graphics, video and camera (including the video lens switch); fingerprint, AOD and double tap to wake;
   Wi-Fi and Bluetooth audio; charging and its time estimate.
