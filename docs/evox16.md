# evox16 controlled test build

Status on 2026-10-14: built and image-verified, then **dirty-flashed to slot b, where it boot-loops**
(`system_server` crashes in Telecom setup; see [Boot loop on the phone](#boot-loop-on-the-phone)). The phone was
restored to evox15 the same night without a wipe. **Do not flash this image.** The cause was our build process (a
stray legacy Telecom APK), and most of evox16's local changes were then reverted: see the
[evox16 review](evox16-review.md) and [evox17](evox17.md). `evox16` is the build name: it is still
Android 17 (`cp2a`, build ID `CP2A.260605.016`, security patch 2026-10-01). What changed is Evolution X itself,
from 12.2 to **12.3**, plus a review of every upstream change that touches a klimt patch.

## What changed

- **Evolution X 12.3** (`cnb`): ThemeStore and downloadable themes, more Quick Settings, font and lockscreen
  controls, UDFPS icon and refresh-rate fixes, separate wake and doze double-tap settings, LHDC V3 and per-device
  Bluetooth codec memory, several Wi-Fi failure fixes, Sandbox/AppLocker multi-user fixes, incoming-call flashlight
  alerts and a Google package refresh. There is no camera-specific fix upstream.
- **Manifest ownership.** Evolution X now declares libcore (AOSP), libdmabufheap, system/usb and the two
  `*/interfaces` projects from LineageOS, adds Canvas, ThemeStore and vendor/themes, and drops ThemeIcons and
  SimpleDeviceConfig. The frozen build manifest follows that.
- **vendor_evolution is upstream again.** Both of our old `cnb-klimt` commits (the security patch level and the
  fingerprint override) are in 12.3, so `vendor/lineage` is plain Evolution-X/vendor_evolution `12eed86f`.
- **14 projects carry a local change**, all exported to the device tree's
  [`patches/tree/`](https://github.com/iowaz/android_device_xiaomi_klimt/tree/evox/patches/tree) with exact
  bases, patch hashes and whole-tree checks (`apply.sh` refuses dirty projects and wrong bases, and skips a project
  whose tree is already final).

| Project | Change | Where it lives |
|---|---|---|
| device/xiaomi/klimt | TouchBridge arms the panel for wake **or** doze double-tap (the new separate setting); allocator stays on the existing libion backend; product overlay keeps AOD wallpaper off (black AOD) | device tree, `evox` |
| frameworks/native | libui keeps the SMPTE 2094-50 guard for the MediaTek mapper | fork, `evox16` |
| hardware/xiaomi | sensor HAL: bounded, terminated UDFPS status reads | fork, `evox16` |
| packages/apps/Settings | carrier scan: error and cancellation handling with the legacy fallback the MediaTek modem needs | fork, `evox16` |
| system/memory/libdmabufheap | the legacy allocator is selected independently of libion | fork, `evox16` |
| build/soong | MIUI boot jar package allowance | fork, `evox16` (`cnb-klimt` is the 12.2 history) |
| system/sepolicy | user builds keep `su` out of the permissive domains (12.3 added it) and keep the permissive check for every policy | `patches/tree` |
| frameworks/base, Sandbox, AppLocker | multi-user configuration and permission fixes | `patches/tree` |
| ThemeStore | install/uninstall callback isolation, per-app icon packs kept on theme updates | `patches/tree` |
| packages/services/Telecomm | incoming-call flash: cancel by session, keep the accessibility default | `patches/tree` |
| packages/modules/Bluetooth | no crash on an accessory without a device class | `patches/tree` |
| packages/apps/Seedvault | WebDAV out-of-space errors | `patches/tree` |
| libcore | keeps the Unix file visibility policy on the AOSP base | `patches/tree` |

Only klimt-specific changes get a fork. The generic fixes stay as patches so there is less to maintain.

## Build

The build was driven by new attempt-isolated tooling in [`build-setup/evox/evox16`](../build-setup/evox/evox16):
one detached controller per attempt, PID/boot/session ownership, a disk watchdog, a source lock, and a readiness
file that pins the full frozen manifest, the five signing certificates and the checks that must pass first.

1. **Focused precheck** ([`precheck.py`](../build-setup/evox/evox16/precheck.py)): 45 changed modules and policy
   tests compile before the full build. `precheck04` stopped at 92% after 1h02 on one error, in our Telecomm
   change: `Ringer.java` used the `android.util.Log` argument order with `android.telecom.Log`. Fixed in
   Telecomm `1029477e`. The host test had missed it because its stub copied the wrong signature; the stub now
   matches the real API and rejects the old code. `precheck05` passed.
2. **Policy and artifact gates on the precheck output**: 46 policy checks (permissive domains empty for normal and
   recovery, neverallows, all contexts, freeze and Treble mappings) and the compiled APK/RRO/native checks,
   including the eight Doze/AOD/UDFPS defaults.
3. **Full build** `evox16-attempt01`: `m -j12 updatepackage`, exit 0 in **1h01m07s** (11,990 Ninja steps; incremental).

## Verification

[`verify.py`](../build-setup/evox/evox16/verify.py) copies the ZIP into the attempt's delivery folder, extracts
it into a new folder and runs:

- the must-hold checks: AVB chain, `super_empty`, `fastboot-info.txt` and `android-info.txt` identical to the
  author build and build9, DTBO payload and `vendor_boot` DTB identical to the phone's slot b, **888 modules,
  0 CRC mismatches**, the one known unresolved symbol, kernel `6.6.142-android15-8-klimt-4k`;
- **all 165 historical fix checks** (the two old false-failure waivers are gone; each check is matched by name);
- **six new image checks** ([`image-checks/check_image.py`](../build-setup/evox/evox16/image-checks/check_image.py)):
  policy, patch packaging, private vendor compatibility, Health semantics, GMS/themes/apps and Doze packaging.

The first verification found no image defect but stopped on four checker bugs, each confirmed against the image
and the reference builds before changing the checker ([diff](../build-setup/evox/evox16/image-checks/check_image.recheck02.diff)):
a 45-second timeout too short for the full-build Ninja graph (55 s, 16 GB RAM), a regex for a trailing-dot
`persist.sys.tap_gesture.` entry no build ever had, an analyzer check looking for strings the source never
contained, and a GMS parser that could not read `$(LOCAL_MODULE).apk`. A verifier-only recheck (`recheck02`) of
the same ZIP passed everything without rebuilding.

## Verified image (boot-loops; do not flash)

- Archive: `lineage_klimt-evox16-img.zip` (5,663,178,762 bytes, 19 fastboot entries, same set as evox15).
- SHA-256: `bba4b20753f86d62cff99a4553cfedc0038991c393ddf2bd91a361d05b549438`.
- In `D:\WitAquaBuild\out-evox` with `lineage_klimt-evox16-flash.bat`/`.sh`, `VERIFIED-evox16.txt`,
  `SHA256SUMS-evox16`, `RESULTS-evox16.json`, `COMPARISON-evox16.md` and `SOURCE-evox16.xml`.
- The flash scripts check the ZIP hash and the `klimt` product, need `/flash` or `--flash`, run
  `fastboot update --skip-reboot` (data kept) and leave the reboot to you.

## Source and reproduction

- [Snapshot](../manifests/snapshots/evox16.xml): 1,263 projects; forks point at iowaz, the patched projects at
  their bases (run `apply.sh` after syncing). The private vendor commit is `74d378be` on `evox`.
- Device tree: [a80d3d1](https://github.com/iowaz/android_device_xiaomi_klimt/commit/a80d3d101e7d19f6f5460c36cfeabc7b980b5886).
- The local checkout is shallow, so the fork commits were published through the GitHub Git Data API with
  [`gh_replay_commits.py`](../build-setup/evox/evox16/gh_replay_commits.py), which only moves a branch when
  GitHub's commit SHA equals the local one.

## Boot loop on the phone

On 2026-10-14 around 23:00 Sao Paulo, the verified ZIP was dirty-flashed over evox15 on slot b. It used
`fastboot update --skip-reboot`, without `-w`, and the slot and firmware were unchanged. The flash itself was
clean: exit 0, 0 errors, no erase. ADB came up after 26 s, but the boot never completed. `system_server` crashed
53 times, about every 5 seconds, always with the same exception:

```
java.lang.SecurityException: Binder invocation to an incorrect interface
  at com.android.internal.telecom.ITelecomLoader$Stub.onTransact
  at com.android.internal.telecom.ITelecomService$Stub$Proxy.getSimCallManager
  at android.telecom.TelecomManager.getSimCallManager
  at com.android.server.telecom.TelecomLoaderService$LoaderServiceConnection.onServiceConnected(TelecomLoaderService.java:83)
```

Evolution X 12.3's frameworks/base has two `TelecomLoaderService` variants:
- **Mainline** (`services/telecom/mainline`) registers the binder returned by the Telecom app directly as the
  `telecom` service, so it expects an `ITelecomService`.
- **Platform** (`services/telecom/platform`) first unwraps an `ITelecomLoader` and calls `createTelecomService()`.

The image's `system_server` ran the mainline variant, but the Telecom app that answered was the legacy one
(`packages/services/Telecomm/legacy-src`, `TelecomService.onBind`), which returns an `ITelecomLoader` binder. The
first `TelecomManager` call therefore reached the wrong interface and killed the system process. All the other
"The system died" app crashes follow from that.

**Cause (found in the [review](evox16-review.md)): our build process, not the 12.3 sources.**
- The release flag `RELEASE_TELECOM_MAINLINE_MODULE` is true, so the product installs `TelecomShim` only.
- The focused precheck ran `m Telecom` to compile our Telecomm patch, and that installed the legacy `Telecom`
  app into `out/target/product/klimt/system/priv-app`.
- The incremental full build never removed it, so `system.img` shipped both APKs.
- Both are `com.android.server.telecom`. PackageManager kept the legacy one and logged
  `Failed to scan /system/priv-app/TelecomShim: ... Skipping duplicate`.

An earlier version of this page blamed a framework/Telecom mismatch in the 12.3 sources; that was wrong.
The evidence is in [evox16-bootloop/](evox16-bootloop/).

Nothing in verification booted the image, and the verifier recorded the duplicate package without failing.
evox17 removes the precheck, runs `m installclean` before the build, and fails on stray or duplicate
installs. It still needs a phone boot before anyone calls it ready.

Restore: rebooted to the bootloader and flashed the verified evox15 ZIP (`63982b33…3f90a`) the same way, still
on slot b with no wipe. Exit 0, 0 errors, no erase. It booted in 36 s with no `system_server` crashes. evox16 never
reached the lock screen, so the credential-encrypted user data was never unlocked by it.

The device logs are kept locally in `C:\XiaomiBuilds\debug\evox16\device-bootloop-20261014\`: bugreport, full
logcat, crash and events buffers, the dropbox `system_server_crash` records and getprop. The flash logs are
`C:\XiaomiBuilds\flash-evox16.log` and `flash-evox15-restore.log`.

## Not tested on the phone

It never booted, so none of the runtime items below were reached: AOD and double-tap (TouchBridge wake/doze
change and black-AOD overlay), fingerprint (UDFPS refresh-rate release changed upstream), Bluetooth codecs and
LHDC, Wi-Fi, SIM/eSIM carrier scan, charging, camera, themes, App Lock and Sandbox on a second user.
