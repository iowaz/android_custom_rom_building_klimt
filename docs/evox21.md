# evox21: bionic's overlay hiding, and no adb root policy in the user build

Status on 2026-10-20: built and image-checked (`evox21-attempt01`, every check passed on the first attempt),
reviewed, then **dirty-flashed to slot b, where it boots** (see [After the flash](#after-the-flash)).

evox21 is evox20 plus three project changes, the follow-up to the Duck Detector scan of evox20
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

`bash pipeline/start.sh evox21-attempt01 ...` at 11:00 after `ready.py`: `m installclean`, then `m updatepackage`:
exit 0 at 12:08, `updatepackage` 1h02m. Soong re-analysed the tree (about 30 min; at its peak WSL's 28 GB of RAM
were full and 24 GB of swap in use, and WSL stopped answering new connections for a while, as expected), then
Ninja ran 15,515 steps, among them `bionic/custom_rom_hide.cpp`, the runtime APEX and the sepolicy neverallow
checks. Soong's "ninja may be stuck" at 11:50 was `add_img_to_target_files` writing the partition images.

- ZIP: 5,661,642,110 bytes, SHA-256 `f956fed67323c9c5057764eef715637aae19748f6a57e9b904335a5236dda6ae`.

## Verification

**Everything passed on the first verification** (12:37), with evox20's counts: the must-hold checks (888 modules,
0 CRC mismatches, DTB/DTBO identical to the phone's slot b), **194/194 fix checks** (the six evox21 checks OK), and
the seven image checks (policy 31, patch packaging 33, private compatibility 115, Health 45, GMS/themes/apps 674,
Doze 62, install integrity 16). `promote.py` moved the delivery to `output-zips\evox21`; `sha256sum -c SHA256SUMS`
passes for all ten files, and the flash helper differs from evox20's only in the ZIP name and hash.

File by file against evox20 (`filesystem-files.json`, 12,663 files on both, 146 differ, none added or removed):

- from bionic: `bootstrap/libc.so` (and its hwasan copy), `bootstrap/linker64`, the static `snapuserd`, and
  `com.android.runtime.apex`;
- from the policy: `system_ext_sepolicy.cil`, its mapping hash, `odm/etc/selinux/precompiled_sepolicy` and its
  system_ext hash;
- from the build date: `org.lineageos.platform` (jar, odex, vdex), whose Evolution X display version carries it
  (`v12.3-20261019` -> `v12.3-20261020`, evox20's build constant), and the 29 APEX service `.odex`/`.art` files
  dexpreopted against the system server classpath it sits on;
- build dates in every `build.prop`, plus `ro.vendor.build.version.incremental`, which is the build number
  (Task 2); `product/etc/build-manifest.xml` (the manifest);
- all 96 `system_dlkm` kernel modules. `diagnostics\builds\evox21\module-sections.py` compares them section by
  section: 95 have the same section contents as evox20 and differ only in file layout, so their signature bytes
  differ too, with the same build-time key (signer serial `065FE6B3…`, as in evox19 and evox20); the 96th is
  `kheaders.ko`, which embeds a header tarball with timestamps. The 517 `vendor_dlkm` modules are byte-identical.
  The kernel `Image` is the same size and differs in 55 bytes, the build timestamp in its version string.

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

Flashed on the owner's request after the review: slot b, `lineage_klimt-evox21-flash.bat /flash`
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

## After the flash

Dirty-flashed on 2026-10-20 at 13:01 with `lineage_klimt-evox21-flash.bat /flash` (slot b, no wipe; 292 s, 111
steps OKAY), then `fastboot reboot`: `sys.boot_completed=1` after 27 s. `runtime-check.sh after` passes as on
evox20; packages are identical (708); no crash, FATAL or ANR; fingerprint unlock works. Record:
`diagnostics\builds\evox21\RUNTIME.md`.

The first Duck Detector scan (13:08, about a minute after boot, adb on, TrickyStore on; app build 1038, the evox20
scan used 1036): Danger 1, Warning 4 (evox20: 1 and 5).

- **Fixed:** the 11 ROM-named overlay files are gone from the Custom ROM traces (`nativeFiles: Clean`, `Product
  overlays: Clean`), and Evolution-X with them: "2 ROM signatures" became "Modified System" only.
  `/data/local/tmp` stays stock ("Shell tmp view: Clean").
- **Not measured:** the SELinux probe's carrier service was killed before it answered, so every policy edge,
  `adbd -> adbroot` included, reads "Unavailable". The image has no adbroot rule (fixcheck21); a later scan has to
  show the edge denied.
- **Unchanged:** TEE `SELF_CHAIN_SPLIT` (TrickyStore), ADB Runtime and `persist.sys.usb.config=adb` (adb was on).
- **Still flagged, with a cause found:**
  - `framework-res.apk mapped from 3 devices`: the three devices are product, system and userdata, never vendor,
    before and after the bionic filter. The only files named `*framework-res.apk` are framework-res itself and
    Evolution X's `vendor/pixel-style` overlay `Pixelframework-res.apk` (plus its idmap on /data), not the
    ROM-named overlays.
  - Dangerous Apps' 3 UIDs without a package are `org.evolution.updater`, `org.omnirom.omnijaws` and
    `org.lineageos.profiles`: the framework hides them from PackageManager, but their processes answer
    `getpriority`, so the hiding is what shows.

A second scan at 13:23 with **adb and wireless debugging turned off** confirms the Task 3 and Task 4 fixes the
13:08 scan could not measure: Danger 1, Warning 2.

- **SELinux: CLEAR, Enforcing** — the probe ran and reported `adbd -> adbroot binder: Denied` with every other
  edge denied. Task 3 confirmed on-device.
- **ADB Runtime: CLEAR**, and the `persist.sys.usb.config` property signal is gone (EMPTY). Task 4 confirmed.
- **Custom ROM** stays a warning for the `framework-res.apk` maps trace, and **Dangerous Apps** for the hidden
  ROM-app UIDs. **Owner decision (2026-10-20): leave both.** The maps trace is Evolution X's `Pixelframework-res`
  file name, not a klimt change; the UIDs are legitimate ROM apps whose "mismatch" is the package-hiding feature
  working. Either can be dealt with per-device (disable the apps) rather than in the build.
- **TEE** `SELF_CHAIN_SPLIT` stays — TrickyStore is on (Task 5). Turning the Evolver switch off clears it; no build
  change. `vdinfos-20261020-1324.json` shows attestation otherwise all-MATCH (StrongBox, verified+locked, Google
  root, patch levels), with only the accepted vendor-lineage split (Task 2) among its build rows.

**No evox22 build change follows from this scan.** Everything it flagged that was a klimt build issue is fixed; the
rest is accepted or is the TrickyStore config choice.
