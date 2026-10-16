# Build history

Evolution X 12.2 and, from evox16, 12.3 (`cnb`, Android 17) for the Xiaomi 15T Pro (klimt), October 2026. Each build is an
incremental build on the same tree unless it says otherwise. The commits are in the repositories listed in the
README. Before Evolution X, builds 1 to 9 were WitAqua (LineageOS-based) on the same device tree; the device tree's other
branches (for example `deps-lineage-24` and `fstab-drop-mi-ext`) are pull requests from that time.

| Build | Date | Result | What changed |
|---|---|---|---|
| evox1 | 2026-10-05 | failed in analysis | Evolution X re-adds the HIDL `light@2.0`, which clashes with the stock vendor blob. Fixed in `hardware_interfaces` by dropping the interface. |
| evox2 | 2026-10-05 | failed in analysis | An absolute `OUT_DIR` outside the tree breaks soong's test packaging. `out` became a symlink instead. |
| evox3 | 2026-10-05 | failed at 76% | Evolution X's `blank_screen` uses the HIDL light as a fallback. Restored the AOSP version (AIDL only). |
| evox4 | 2026-10-05 | **first success** | userdebug, test keys. Flashed on 2026-10-09 with a clean wipe; it booted. |
| evox5 | 2026-10-09 | failed (sepolicy) | Vendor fingerprint HAL may not read `system_prop` (neverallow). The bridge properties were renamed. |
| evox6 | 2026-10-09 | success, flashed (wipe) | USB over the MediaTek gadget HAL, touch feature props, VoLTE on VIVO, double tap to wake, screen-off fingerprint. |
| evox7 | 2026-10-09 | success, flashed (wipe) | First **user** build with **private keys**. Doze through SystemUI, a wake-up sensor for screen-off fingerprint, the Evolution X fingerprint override, MIUI Camera, and A2DP hardware offload off (Bluetooth audio was silent). |
| evox8 | 2026-10-10 | success, flashed (dirty) | Camera crashes fixed: the A15 camera blobs get the stock `libui` as `libui_vendor.so`. Also charging control, reverse wireless charging, always-on display in the panel's doze mode, and Dolby Atmos controls. |
| evox9 | 2026-10-10 | success, flashed (dirty) | Security patch level 2026-10-01 plus the October fixes (PduParser, decodeWapPdu, Bluetooth). Custom ROM hiding synced with upstream. Play Integrity passes BASIC, DEVICE and STRONG. |
| evox10 | 2026-10-10 | success, flashed (dirty) | The lockscreen fingerprint icon showed as a white block because SystemUI had no `pixel_pitch`; an overlay now sets 56.82 (447 ppi). The icon is also back at the stock centre (640, 2518). |
| evox11 | 2026-10-11 | success, not flashed (evox12 includes it) | **UI lag:** Xiaomi's `mi_thermald` capped the CPU at 1.4/2.1/2.0 GHz, because on HyperOS the system picks its thermal profile and nothing did here (Geekbench 7: 1321 single, 5043 multi). A new XiaomiParts app (Settings > Battery > Performance & thermal, plus a Quick Settings tile) sets HyperOS's performance profile by default, with per-app profiles. **Slow charging:** the bundled 90 W charger gave about 9 W, because `batterysecret` could not read and write the charger's verification nodes in sysfs, so the phone stayed at 5 V. It now has the same sysfs access as on stock. Also allowed the mpbe ioctl `0x6703`. |
| evox12 | 2026-10-11 | success, flashed (dirty) | **Wakeup sources:** about 55 kernel wakeup sources had no label `system_suspend` can read, so they had no names in the stats and every poll logged about 560 denials, which used up the kernel's audit rate limit and hid other denials. 54 genfscon entries now label them `sysfs_wakeup`, most taken from the stock policy. **Video calling off:** Evolution X does not ship the stock `vtservice`, and with ViLTE/ViWiFi on, the IMS service waited for it every 5.5 s; VoLTE stays on. Also two stock rules: the power HAL may look up the fingerprint HAL in `/proc`, and the camera HAL may set attributes on its debug files. |
| evox13 | 2026-10-11 | success, flashed (dirty) | **Log noise.** SurfaceFlinger logged "Mapper error: 7" about 750 times a minute: RenderEngine asks every buffer for SMPTE 2094-50 metadata, new in Android 17, and the MediaTek mapper doesn't support it; libui now asks the mapper once (patch in `patches/tree`). The composer looked for Xiaomi's light sensor service about 190 times a minute: it was never shipped, so the stock daemon that corrects the under-display light sensor for the screen's own light is added. MIUI Camera logged about 7,000 lines on every launch because MiSys could not create its watermark folder. Also: dontaudit for harmless property lookups by the camera, audio and GPS HALs, stock labels for camera and TEE status properties, the FeliCa script's setup check, and the USB product name. |
| evox14 | 2026-10-11 | success, flashed (dirty) | **Camera and sensor policy.** Stock labels and permissions for the camera direct-I/O mapper, debug-file append, camera calibration/state properties and composer idle-mode property. MiSys reads the dedicated stock blackbox partition label. The sensor daemon gets narrow heap open/read access, the stock system-property dontaudit and an exact boolean label for its actual framebuffer property setter. Heap reads and the framebuffer setter are observed-need exceptions; all other new access follows stock. Offline policy/context/tests and image AVB/layout/module checks pass. Dirty-flashed to slot b and booted. Watermark photos save after re-enabling the watermark; the earlier DataStorager overflow was not observed in this session. Video lens switching still triggers a camera HAL watchdog abort. |
| evox15 | 2026-10-12 | attempt 1 failed; attempt 2 verified, flashed (dirty); re-flashed (dirty) on 2026-10-14 after the evox16 boot loop, boots | **Charging telemetry and controlled camera candidate.** Device Health normalizes the kernel current sign and reports the unreliable average/time estimate as unsupported, so BatteryStats can use charge-level history. Exact photo mode 0x9002 uses the existing bounded HIS initialization fallback; watchdog and lock ownership remain intact. Independent source review and offline vendor/recovery compilation passed. Kati rejected duplicate generic/custom Health install paths after analysis; attempt 2 completed with the independently reviewed unique-path repair (exit 0, 50m29s). AVB/layout/DTB/DTBO, all 888 module CRCs and all ten new Health/camera packaging checks pass. Phone runtime tests remain pending. See [evox15 details](evox15.md). |
| evox16 | 2026-10-14 | attempt01 verified; **boot-loops on the phone**, restored to evox15 (dirty) | **Boot loop:** dirty-flashed to slot b, `system_server` crashed every ~5 s in `TelecomLoaderService` (the mainline loader expects `ITelecomService`, the Telecom app returned `ITelecomLoader`). Restored evox15 without a wipe; it booted normally. **Cause: our build process.** The focused precheck's `m Telecom` installed the legacy Telecom app into the staging directory, the incremental build packed it next to TelecomShim, and PackageManager kept the legacy one ([review](evox16-review.md)). The review then reverted most of evox16's local changes as not needed. Build: **Evolution X 12.3** on the same Android 17 `cp2a` base, with every upstream change that touches a klimt patch reviewed. TouchBridge arms the panel for the new separate doze double-tap setting, the product overlay keeps AOD black, the UDFPS sensor read is bounded, the MediaTek carrier scan keeps its fallback, and the allocator stays on the existing backend. `vendor_evolution` is upstream again. 14 projects carry local changes; only the 5 klimt-specific ones got forks, the rest are in `patches/tree`. A 45-module focused precheck caught one javac error in our Telecomm change before the full build; the full `updatepackage` built in 1h01. All 165 historical checks, the must-hold checks and six new policy/packaging/vendor/Health/GMS/Doze image checks pass. See [evox16 details](evox16.md). |
| evox17 | 2026-10-15 | attempt01 image-checked (recheck01); flashed (dirty), **boots** | **Evolution X 12.3 with only what klimt needs.** Upstream everywhere except the evox15 device setup (plus the black-AOD overlay), the MIUI boot jar, SMPTE 2094-50 and lights forks, and the evox15 kernel, vendor, hardware/xiaomi and MediaTek policy. No precheck; `m installclean` before the build; a new image check fails on stray files, duplicate packages and a Telecom variant mismatch. Built in 1h17m; all 165 historical checks and seven image checks pass, and TelecomShim is the only Telecom app. A second independent Codex review found three verifier gaps, fixed and rechecked. Dirty-flashed to slot b: booted in 48 s, `system_server` stable, TelecomShim only, SIM/IMS, Wi-Fi, cameras and fingerprint present. See [evox17 details](evox17.md). |
| evox18 | 2026-10-15 | attempt01 image-checked (recheck04); not flashed (same ROM as evox17) | **Pipeline test after the reorganization** ([build PC layout](build-pc-layout.md)). Everything moved into one folder, the disks were compacted and moved, and the per-build tooling became one generic pipeline; evox18 is evox17's frozen source built again with it. Built in 1h15m. Three verification stops were defects of the move (a watcher name matching the competing-build guard, a local variable shadowing a module, a helper still called by its old C:\XiaomiBuilds path) and one was disk space; each was fixed and the same ZIP re-verified: 165/165 historical and all seven image checks pass with evox17's counts. File by file, the image differs from evox17 only in build.prop dates/host and kheaders.ko. See [evox18 details](evox18.md). |
| evox19 | 2026-10-15 | attempt01 image-checked (recheck01); flashed (dirty) 2026-10-16, **boots**; AOD fingerprint and double tap work | **AOD takes touch again.** Since evox8 AOD puts the display in `DOZE`, and InputReader disabled `goodix_ts` there (no IDC), so taps, double taps and the fingerprint on AOD were dropped while the panel kept reporting them; its FOD-press and double-tap events stay silent in doze. One device tree commit (`8f1f903`) adds `/vendor/usr/idc/goodix_ts.idc` with `touch.enableForInactiveViewport = 1`. Otherwise evox17's source. Built in about 48 min; the first verification stopped because `install_integrity` read `.installable_files`, which Soong renames to `.previous` whenever the install list changes (it never had before). The checker now reads either; the same ZIP passed every check with evox17's counts. See [evox19 details](evox19.md). |

## Open items

- On the lockscreen, the Evolution X "Now Playing" pill and the Dynamic Bar music chip overlap above the
  fingerprint icon. This is an upstream layout bug; for now, disable one of the two.
- The two slots run different HyperOS firmware (slot a has OS3.0.302, slot b has OS3.0.335). Sync slot a's firmware
  before applying any A/B OTA.
- MIUI Camera: the watermark copy flood is fixed and photos with the Leica watermark save on evox13.
  On evox14, watermark 3 initially crashed the app because its private `config.json` was missing
  (ENOENT); the user re-enabled the watermark and photos then saved. The earlier DataStorager
  overflow and direct-I/O mapper denial did not recur in the session. Video lens switching
  triggered a GuardMonitor SIGABRT after MiaNode-Init stalled for 10.88 seconds; the immediate
  logged transition was video 0x8004 to photo 0x9002. The blocked thread waited in
  MiaOfflineSession::parallelInitAllNodes on a HIS session-lifetime gate held by the old session.
  Its adaptor flush had 24 outstanding requests. The evox15 bounded initialization candidate
  has not demonstrated old-flush recovery or correct image output on the phone. New property-read denials
  affect MiSys and the camera app
  on `vendor_mtkcam_prop`; investigate stock reader permissions before adding access.
- Camera search of category-labelled system data remains denied by MLS; stock does not justify an exception.
- Frequent libc warnings for non-vendor camera property names remain. A platform policy integration was
  deferred from evox14; vendor dontaudit does not silence libc.
- On evox14 the light sensor service stays running and sends calibrated lux; no citsensorservice
  denials appeared in the capture. The user reports Adaptive brightness working in the dark/bright
  test and confirms turning it off afterwards. The framebuffer property remains unset, so its
  setter path has not been demonstrated at runtime.
- Charging estimates on evox14 can show many days: the kernel average current stays at 4.5 mA
  and its time-to-full value is stale; current polarity is opposite the Android convention.
  The evox15 Health correction is packaged and image-verified in evox15 and evox16; it still needs a phone
  charge/discharge test.
- evox16 boot-loops (a stray legacy Telecom APK, see the [evox16 review](evox16-review.md)). The phone runs evox17
  (Evolution X 12.3) since 2026-10-15; its hands-on checks are pending (see [evox17](evox17.md#before-calling-it-ready)).
- Evolution X's charging animation keeps running on AOD at the panel's 120 Hz: on evox17, with
  `charging_show_on_aod` on, SystemUI drew 121 frames a second and the phone used about two CPU cores (26% of eight
  vs 4% with it off), plus GPU and composer work. Upstream code (`SystemUI/.../charging/ChargingAnimationView.kt`,
  endless `ValueAnimator` plus `invalidate()`, no doze handling). For now, turn off "Show animation in ambient
  display mode"; a SystemUI change would stop or throttle the animators while dozing.
- AOD starts at doze brightness 0.0157 (`config_screenBrightnessDoze` = 5), which looks black on this panel, until a
  notification pulse raises it.
- The FeliCa apps stay enabled on phones that were set up before evox13; the script only acts before setup.
- Video calling over LTE/Wi-Fi is turned off (evox12). Turning it back on would need the stock `vtservice` and
  its libraries.
