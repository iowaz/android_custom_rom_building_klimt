# evox17: Evolution X 12.3 with only what klimt needs

Status on 2026-10-15: source frozen and published, build `evox17-attempt01` started. This page is updated when the
build and its checks finish. **Not boot-tested.**

evox17 is what evox16 should have been: Evolution X 12.3 (`cnb`, Android 17, `CP2A.260605.016`) with the evox15
device setup and nothing else. It follows the [evox16 review](evox16-review.md).

## Source

The frozen manifest is [`manifests/snapshots/evox17.xml`](../manifests/snapshots/evox17.xml): 1,263 projects.
All 315 GitHub pins were fetchable from their branches when it was written.

- **Upstream everywhere**, at the branch heads of 2026-10-15. Since evox16 that brought three frameworks_base
  commits (two re-pushed font fixes and a Pixel-features tweak for Tensor), an Evolver font-style change, and
  LineageOS updates (LatinIME, Launcher3, APNs, WebView, and Qualcomm projects klimt does not build).
- **Local changes, all already in evox15:**
  - device tree [`43b71ec`](https://github.com/iowaz/android_device_xiaomi_klimt/commit/43b71ecbde010c3444dfb297e9dbd755b1b443c5):
    the evox15 device plus the black-AOD product overlay. The doze double-tap bridge and the allocator flag are
    reverted, and `patches/tree` holds only the two patches below;
  - build/soong `evox16` fork: the MIUI boot jar packages;
  - frameworks/native `evox16` fork: libui's SMPTE 2094-50 guard for the MediaTek mapper;
  - hardware/interfaces `cnb-klimt` fork: AIDL-only lights.
- **Kept at the evox15 commits:** kernel, kernel prebuilt build, proprietary vendor `74d378be`, LineageOS
  hardware/xiaomi `af5766ac` and MediaTek vendor policy `117a8de2`. The MediaTek policy has 20 newer LineageOS
  commits, mostly labels for other MediaTek chips. They are not part of the move to 12.3 and can be taken in a
  later build.
- **Back on upstream** (the iowaz `evox16` branches remain, so the evox16 snapshot still resolves):
  packages/apps/Settings, hardware/xiaomi, system/memory/libdmabufheap.

**Behaviour that changes from evox15, all from upstream:**
- Evolution X 12.3 features: ThemeStore, more Quick Settings, font and lockscreen options, the separate doze
  double-tap setting. Double tap to wake works as before; the separate doze setting does not arm the panel.
- The `su` SELinux domain is permissive on user builds. Upstream's choice; nothing on a user build can enter it
  without a root solution.
- The ION-free allocator.

## Build process

Tooling: [`build-setup/evox/evox17`](../build-setup/evox/evox17), the evox16 controller with these changes:

- no focused precheck;
- `m installclean` before `m updatepackage`, failing if any staged partition survives;
- seven image checks, including the new `install_integrity` (see the [review](evox16-review.md#what-changes-in-the-process)),
  which fails on the evox16 image;
- checks for evox16's optional patches replaced by "this project is the reviewed upstream commit";
- the marker says "static image checks passed, NOT boot-tested".

The frozen manifest was generated with [`make-frozen.py`](../build-setup/evox/evox17/make-frozen.py) from
evox16's, and is on the private `iowaz/evox16_manifest` repository, branch `evox17-manifest`.

## Before calling it ready

Flash it only with the evox15 ZIP ready to restore (slot b, no wipe, as before), then check in order:

1. `sys.boot_completed=1`;
2. `system_server` stays up, `pm list packages -f com.android.server.telecom` shows TelecomShim only, and there
   is no "incorrect interface" crash;
3. the lock screen unlocks; calls, SMS, mobile data, SIM/eSIM;
4. graphics, video, camera; fingerprint, AOD and double tap; Wi-Fi, Bluetooth; charging.
