# Build history

Evolution X 12.2 (`cnb`, Android 17) for the Xiaomi 15T Pro (klimt), October 2026. Each build is an
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
| evox11 | 2026-10-11 | success, not flashed yet | **UI lag:** Xiaomi's `mi_thermald` capped the CPU at 1.4/2.1/2.0 GHz, because on HyperOS the system picks its thermal profile and nothing did here (Geekbench 7: 1321 single, 5043 multi). A new XiaomiParts app (Settings > Battery > Performance & thermal, plus a Quick Settings tile) sets HyperOS's performance profile by default, with per-app profiles. **Slow charging:** the bundled 90 W charger gave about 9 W, because `batterysecret` could not read and write the charger's verification nodes in sysfs, so the phone stayed at 5 V. It now has the same sysfs access as on stock. Also allowed the mpbe ioctl `0x6703`. |

## Open items

- On the lockscreen, the Evolution X "Now Playing" pill and the Dynamic Bar music chip overlap above the
  fingerprint icon. This is an upstream layout bug; for now, disable one of the two.
- The two slots run different HyperOS firmware (slot a has OS3.0.302, slot b has OS3.0.335). Sync slot a's firmware
  before applying any A/B OTA.
- MIUI Camera leftovers (port issues): a deadlock on lens switches while recording, and crashes with watermarks.
- About 55 kernel wakeup sources have no SELinux label, so `system_suspend` cannot read their stats. Each poll
  logs hundreds of denials, which hides other denials behind the kernel's rate limit. A fix is being prepared.
- Video calling over LTE/Wi-Fi: MediaTek's IMS service waits for `media.VTS`, but Evolution X does not ship the
  stock `vtservice`.
