# evox21: bionic's overlay hiding, and no adb root policy in the user build

Status on 2026-10-20: **building** (`evox21-attempt01`, started 11:00); not image-checked yet, **not flashed**.
The source and the gates below are up for review before anything goes on the phone.

evox21 is evox20 plus three project changes, the follow-up to two Duck Detector scans of evox20
(`D:\android_rom_building\duck_detector_report_2506BPN68G_20261020_125849.txt`, app build 1036). The task list is
`D:\android_rom_building\evolution_x_klimt_build_tasks_20261020.md` (rev 3). Only two of its tasks change the
build; the rest are the phone's state during the scan and are listed under [On the phone](#on-the-phone).

| Scan finding (evox20) | Cause | evox21 |
|---|---|---|
| Custom ROM: 11 `*__evolution_klimt__auto_generated_rro_*.apk` files listed, `framework-res.apk mapped from 3 devices` | the ROM-named overlays in `/product/overlay` and `/vendor/overlay` show in directory listings and `/proc/self/maps` | bionic moves to Evolution X `cnb` `f8b37b8`, which hides them from both (Task 1) |
| SELinux: `adbd -> adbroot : binder call` allowed | Lineage's adb root policy is built into every variant, though a user build ships no `adb_root` | the policy goes only into userdebug and eng builds (Task 3) |
| TEE: `SELF_CHAIN_SPLIT` (grant chain 5 certs, owner chain 4) | the TrickyStore switch in Evolver is on | no build change; the owner chooses (Task 5) |
| ADB Runtime, `persist.sys.usb.config=adb` | the scan ran with USB and wireless debugging on | no build change: no prop file sets it (Task 4) |
| Dangerous Apps: Termux, ADB Helper, 3 UIDs without a package | installed apps | no build change (Task 6) |

## Source

`diagnostics\builds\evox21\evox21-frozen.xml`: evox20's 1,263 projects, three revisions changed.
`SOURCE_VS_EVOX20.json` checks that only these differ, that each builds on its evox20 commit and that every worktree
is clean:

- **bionic** `3d41693` -> `f8b37b8`, the four commits Evolution X added on `cnb` since evox20, nothing else (bionic
  has no local change, so only the pin moves):
  - `33095e6` "custom_rom_hide: Hide ROM-named RRO overlays from apps" and its fix `fff9253` "Only hide ROM-named
    overlays from listings": overlay APKs in `/system`, `/system_ext`, `/product`, `/vendor` and `/odm/overlay`
    whose name carries a ROM marker (`evolution`, `lineage`, ...) are left out of directory listings and
    `/proc/self/maps` for app processes. Opening one by its path still works: `fff9253` exists because
    `33095e6` alone stopped SystemUIGoogle from loading its vendor overlay on a device with an optical sensor,
    which broke fingerprint enrollment there.
  - `f8b37b8` "Do not spoof /data/local/tmp": `stat()` no longer gives `/data/local/tmp` the fixed inode 4223.
  - `299a83f` "ifaddrs: don't require inet sockets for name/flag resolution", an unrelated libc fix between the two.
- **device/lineage/sepolicy** `fe4d5dd` (the `cnb` head, unchanged since evox20) -> `9112cda` "sepolicy: Keep the
  adb root policy to debuggable builds". `vendor/lineage/config/common.mk` installs `adb_root` only with
  `WITH_SU=true`, which klimt never sets, but its policy was not gated. The commit wraps `adbroot.te`'s rules,
  `adbd.te` (binder call and service find on adbroot) and `system_server`'s find on `adbroot_service` in
  `userdebug_or_eng`, as `system/sepolicy` does for `su`. The four adbroot types stay, because `file_contexts` and
  `service_contexts` label with them. On a user build `adbd` already answers `adb root` with "cannot run as root in
  production builds" before it would use the service, and with no binary the service never registers, so nothing
  that worked stops working.
- **device/xiaomi/klimt** `52487ef` -> `d71b3e4` "klimt: patches: Carry the user-build adb root policy gate": the
  sepolicy commit goes into `patches/tree` (PATCHES.json, BASES, the patch, and a README that now also lists
  evox20's build/soong patch). `apply.py` reports all three bundle projects as final.

Where they are: bionic `f8b37b8` is Evolution X's own commit. The device tree commit is on
`iowaz/android_device_xiaomi_klimt` `evox`
([`d71b3e4`](https://github.com/iowaz/android_device_xiaomi_klimt/commit/d71b3e43d2eaea4f3e5e63b5c495e5f475c59c22)),
and it carries the sepolicy commit as
[`patches/tree/device/lineage/sepolicy/0001-...patch`](https://github.com/iowaz/android_device_xiaomi_klimt/blob/evox/patches/tree/device/lineage/sepolicy/0001-sepolicy-Keep-the-adb-root-policy-to-debuggable-buil.patch).
The sepolicy commit `9112cda` itself has no fork to live in yet (an `iowaz/device_evolution_sepolicy` fork with
an `evox21` branch, like evox20's forks), so the frozen manifest pins it in the local tree only. Its
PATCHES.json `publication` line still says "not published yet"; that file is part of the frozen source of the
running build, so it changes with the next device tree commit.

**Upstream first.** The bionic move is upstream code. The sepolicy change is a deviation from LineageOS: it is
justified by the scan finding, it only removes rules from the user build, and those rules served a binary the
user build doesn't have.

Not taken: `packages_apps_Evolver`'s "Rework spoofing UI with Material 3 Expressive" (`28ffb688`) is a Settings
screen change with no scan finding behind it, and it would bring the rest of the force-pushed Evolver delta. It
stays an owner decision.

### Policy check before the build

`diagnostics\builds\evox21\policy-replay.sh` replays the build's own m4, checkpolicy, filter_out and secilc commands
(from `ninja -t commands`) on the edited sources, with outputs in `/tmp` only (`policy-replay.txt`):

- user conf: 0 adbroot allow lines; the same sources as userdebug: 23, so the gate only touches the user variant;
- the system_ext CIL compiles against the platform policy, and the full `precompiled_sepolicy` secilc run, every
  neverallow on, compiles with the new CIL; the permissive domains are `su` only, as in evox20;
- against evox20's built system_ext CIL, the user policy loses exactly the adbroot rules: 24 `allow` statements
  (22 distinct), one `dontaudit`, the `init` type transition into adbroot, and one generated attribute (from
  `add_service`'s neverallow). Nothing else changes.

### Gates, written first

`legacy/fixcheck21.sh` runs fixcheck20.sh and adds six checks (194 in all); `verify.py` runs it.

| Check | evox20 image |
|---|---|
| libc filters the five */overlay dirs (the APEX libc carries `/system/overlay` ... `/odm/overlay`) | FAIL |
| libc no longer fakes the /data/local/tmp inode (no `#0x107f` in `custom_rom_hide_spoof_stat`) | FAIL |
| no packaged policy rule names an adbroot type (all five packaged CILs) | FAIL |
| adbroot types stay declared for the contexts | OK |
| no adb_root binary or init service | OK |
| no prop file sets persist.sys.usb.config | OK |

Every other check passes on evox20 as before (`fixcheck21-on-evox20.txt`). `tests.py`: 22 OK. `ready.py` passed
its nine gates (frozen graph and clean worktrees, patch bundle final, the five semantic purposes, staging clean,
image checks registered, the source comparison, the task plan, the policy replay and the red run).

## Build

`bash pipeline/start.sh evox21-attempt01 ...` at 11:00 after `ready.py`: `m installclean`, then `m updatepackage`.
Soong re-analysed the tree (about 30 min, about 24 GB of swap at its peak, WSL stopped answering new connections
meanwhile, as expected), then Ninja: 15,606 steps, including `bionic/custom_rom_hide.cpp`, the runtime APEX
and the sepolicy neverallow checks. Results follow when the attempt finishes.

## Verification

Follows the build: the controller runs `verify.py` (must-hold checks, the 194 fix checks, the seven image checks),
then `promote.py` moves the delivery to `output-zips\evox21`.

## Not build changes

- **Vendor build lineage (Task 2), an accepted leftover.** `ro.vendor.build.id` stays `CP2A.260605.016` and
  `ro.vendor.build.version.incremental` the build number, while the base identity is `ZP11.260918.007` /
  `16484274`. Make writes `vendor/build.prop` (`build/make/core/sysprop.mk`) and no override key reaches those two
  props; evox20 kept them on purpose (decision C1). Duck Detector does not flag it (its Build block reads "System
  properties: Clean / Build fields: Clean"); only the separate `vdinfos` probe lists it, as `SPLIT vendor{...} ; ok`.
  `ro.vendor.build.security_patch=2026-02-01` must not move: it is the vendor's AVB patch level. The delivery's
  `COMPARISON.md` is generated by the verifier and covered by `SHA256SUMS`, so this note lives here and in the
  evox21 diagnostics, not in that file.
- **ADB state (Task 4).** No prop file in the image sets `persist.sys.usb.config` (now a gate). `UsbDeviceManager`
  writes `adb` to it when USB debugging is turned on and clears it when it is turned off; `Wireless debugging:
  Enabled` and `init.svc.adbd: running` are the same session.
- **TrickyStore (Task 5).** Evolution X doesn't modify keystore2 or KeyMint. `SELF_CHAIN_SPLIT` is how the enabled
  attestation replacement looks to a local grant probe; attestation itself is aligned (StrongBox, Google root,
  trust path consistent). Only turning the Evolver switch off clears it; with it on, the finding stays.
- **Apps (Task 6).** Termux and ADB Helper are visible to apps; three app UIDs (10375, 10401, 10403) showed no
  package in the scan's `getpriority` sweep.

## On the phone

Not flashed. Flashing only on the owner's request: slot b, `lineage_klimt-evox21-flash.bat /flash`
(`fastboot update --skip-reboot`, no wipe), with `output-zips\evox20` ready to restore the same way.

1. Before flashing, with adb on: `diagnostics\builds\evox21\runtime-check.sh before` on evox20; after the boot,
   `runtime-check.sh after` (evox20's identity checks, the corrected empty `ro.bootimage.build.fingerprint`,
   SELinux Enforcing, no `adb_root`, no `adbroot_service`).
2. Fingerprint enrollment and unlock, from the lock screen and AOD (the case `fff9253` fixed upstream), UDFPS
   illumination, and the evox20 checklist in `diagnostics\builds\evox20\RUNTIME.md` (Play Integrity basic/device/
   strong, Evolver, camera, calls, Bluetooth, DRM).
3. For the scan: choose Task 5 (TrickyStore off to clear the TEE finding, or keep it and accept the finding);
   optionally remove Termux / ADB Helper and look up the three UIDs (`pm list packages --uid <uid>`) while adb is
   still on; then turn off USB debugging and wireless debugging and check that `persist.sys.usb.config` is empty and
   `adbd` stopped (Settings, or the last adb session).
4. Re-run the same Duck Detector build and compare with the 2026-10-20 12:58 report. Expected: no ROM-named overlay
   in the Custom ROM traces, `/data/local/tmp` stock; `adbd -> adbroot` denied with SELinux Enforcing; no ADB Runtime
   or `persist.sys.usb.config` item; the TEE finding gone only with TrickyStore off; build identity as evox20.
