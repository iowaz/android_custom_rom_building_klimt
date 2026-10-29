# Evox27 - Evolution X cnb of 2026-10-29 and MediaTek GED KPI

Prepared on 2026-10-29 for `lineage_klimt-cp2a-user`. No flash is authorized by this build task.

## Source

The whole tree was synced to the Evolution X manifest `cnb` 16cc234 (2026-10-29), which also moves the LineageOS
`lineage-24.0` projects to their heads; AOSP stays on `android-17.0.0_r1`. The 1,263-project snapshot is
[`manifests/snapshots/evox27.xml`](../manifests/snapshots/evox27.xml); every project with a local commit uses its
iowaz fork, branch `evox27`. evox26 was synced on 2026-10-21.

Manifest changes: `external/conscrypt`, `external/selinux` and `system/ca-certificates` now come from LineageOS forks,
`external/libpng` and `system/netd` from Evolution X. Our copy of `default.xml` fetches LineageOS from
`https://github.com` because the manifest is served from a local clone (`fetch=".."` resolved to the clone's folder).

Evolution X had rebased every changed `cnb` branch after evox26, so the owner commits were re-applied on the new
heads: eight with `git am -3`; three by hand because upstream rewrote the code they touch (vendor/lineage
`common_mobile.mk`; Settings' hardware info page is now `ModelPageController`; Updater was rewritten in Kotlin and
reads the device name in `DeviceInfoUtils`). The evox20 design is kept: no `ro.evolution*`/`ro.lineage.device`
props, their readers take build constants.

Upstream changes klimt gets (selection; the review packet `diagnostics\builds\evox27\reviews\03-upstream-input.txt`
lists every commit): the TrickyStore/PIF/keybox rework and a TrickyStore timing fix, bionic `custom_rom_hide` fixes
for `fstat`/`statx` and O_CLOEXEC, the GrapheneOS-derived hardening batch (bionic stack/TLS guard pages and
canaries, `fs.protected_*` sysctls, mount flags, `Build.SERIAL` UNKNOWN, no fingerprint in screenshot EXIF,
non-persistent network adb, no DHCP hostname, secure NFC by default, URL confirmation), several security fixes
(WAP push header length, PiP use-after-free, a WindowManager PID/UID mix-up, CT verifier TOCTOU, QUIC VPN bypass),
eSIM and per-SIM ringtone changes, and UI features (ColorOS QS panel, Dynamic Island, custom fonts, non-Pixel Now
Playing, double tap to sleep on Pixel Launcher).

## Local changes

- **frameworks/base** drops the evox22 TrickyStore chain-persist and evox24 PIF-seeding commits (owner decision;
  upstream's rework persists the hacked chain at key generation). Two new commits:
  - `PackagePartitions.FINGERPRINT` also digests `ro.build.date.utc`. The package manager uses it to detect an
    upgrade and to name the package parser cache; klimt reports a fixed Xiaomi fingerprint and incremental, so
    without it a dirty flash would not count as an upgrade (the open item from evox26). Every new build now does
    the normal upgrade on its first boot (cache reset, dexopt), so that boot is slower.
  - TrickyStore: an all-zero verified boot key from the TEE (klimt's TEE attests zeros while the bootloader is
    unlocked) falls back to `AttestationUtils.getBootKey()`, as the generated-key path does. Upstream's rework
    would otherwise have attested a locked, Verified device with an all-zero boot key (review 03).
- **frameworks/native**: the MediaTek GED KPI hooks (upstream `cc9996b`) start with a known producer pid and
  surfaceflinger flag, declare them for every module, and skip a released buffer (review 01).
- **device/xiaomi/klimt** (`evox27`): `libgui/support_mtk_ged_kpi` is on, so every Surface reports its frame
  timestamps to `/proc/ged` for the GPU DVFS governor, as MediaTek's own libgui does on stock HyperOS. The stock
  `ged.ko` accepts the structures; no sepolicy change was needed. The kernel label moves to `-ab27` (source
  unchanged), and `patches/tree` is rebased on the new upstream heads.
- **Pipeline**: the kernel label check follows the build number (ab26 for evox26, ab27 for evox27).

klimt's existing `fastbootd/bypass_lock_state` flag now also reaches upstream's fastbootd and libfs_avb changes
(fastbootd always reports unlocked; libfs_avb counts "green" as unlocked). Reviewed as acceptable on an unlocked
bootloader.

Not taken: six newer commits on misakazip's device tree `17.0` (MIUI Camera/Gallery integration, shared MediaTek and
eSIM components); they need matching blob changes and are not Evolution X/LineageOS/AOSP.

## Reviews

Four independent read-only reviews (Claude Opus 5.5 subagents), disposition in
`diagnostics\builds\evox27\REVIEW_DISPOSITION.md`: device/BoardConfig PASS, ported commits PASS, upstream intake
CHANGES REQUIRED (the TrickyStore boot key, fixed), follow-up on the fixes PASS.

## Status

Built, verified and delivered: see below once the attempt finishes. Not flashed, not boot-tested.
