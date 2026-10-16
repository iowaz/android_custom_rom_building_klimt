# evox19: AOD takes touch, double tap and fingerprint again

Status on 2026-10-16: built and image-checked (`evox19-attempt01`, verifier recheck `recheck01`), then
**dirty-flashed to slot b, where it boots, and AOD takes the fingerprint and double tap** (see
[On the phone](#on-the-phone)).

evox19 is evox17 plus one device tree commit. On evox17 the phone ignores taps, double taps and the fingerprint
on AOD (always-on or AOD while charging); only the power button wakes it.

## Why AOD ignored touch

Since evox8 (`a4629ed`, `doze.display.supported=true`) the display is in `DOZE` while AOD shows.

- `goodix_ts` has no IDC, and AOSP's `TouchInputMapper` disables a touchscreen whose viewport is not active unless
  the IDC sets `touch.enableForInactiveViewport`. On the phone in AOD: `Touch Input Mapper (mode - DISABLED)`,
  viewport `isActive=[0]`.
- The panel keeps sending the touches: in its doze mode the Goodix THP reported all 20 test touches with full
  coordinates, and none reached the framework.
- The panel raises neither its FOD press (`fod_press_status`, the `org.lineageos.sensor.udfps` wake-up sensor)
  nor `KEY_WAKEUP` in doze. The UDFPS sensor stayed registered and silent through AOD; it fires when the display is
  fully off, including on a charger with AOD-on-charge turned off.
- Touch did work in two windows: the 4 s SystemUI keeps the display ON for the lock-to-AOD animation
  (`DozeScreenState.ENTER_DOZE_DELAY`), and notification pulses (display ON for about 6 s).

Stock HyperOS does the same thing with the panel: its bugreports show raw `goodix_ts` touches reaching MIUI's
`miui-touch-fod` gesture monitor while the display is in `DOZE`, then a fingerprint wake-up. MIUI keeps the
touchscreen live in its framework (`EnableForInactiveViewport` is false there too).

Phone evidence and the stock comparison: `D:\android_rom_building\diagnostics\device\2026-10-15-aod-touch\FINDINGS.md`
(not in this repository: it quotes phone logs).

## Source

[`manifests/snapshots/evox19.xml`](../manifests/snapshots/evox19.xml): evox17's 1,263 projects, with one change.
`diagnostics\builds\evox19\SOURCE_VS_EVOX17.json` checks that only `device/xiaomi/klimt` differs and that it is
exactly one commit on top of evox17's `43b71ec`:

- device tree `8f1f903` "klimt: Keep the touchscreen enabled during AOD": `configs/idc/goodix_ts.idc` with
  `touch.enableForInactiveViewport = 1`, installed as `/vendor/usr/idc/goodix_ts.idc` (`device.mk`, 4 lines). AOSP
  already labels that path `vendor_idc_file` and lets `system_server` read it, so no sepolicy change. The IDC sets
  nothing else: `touch.wake` stays false, so a touch alone does not wake the phone.

The commit is pushed to `iowaz/android_device_xiaomi_klimt` `evox`
([`8f1f903`](https://github.com/iowaz/android_device_xiaomi_klimt/commit/8f1f90332c692c4b9ae859d361d04d5333409712)).

`ready.py` passed its seven gates (frozen graph and clean worktrees, patch bundle final, the five semantic source
purposes, staging clean, image checks registered, the source comparison above, and the investigation).

## Build

`bash pipeline/start.sh evox19-attempt01 ...` at 23:35 after `ready.py`. `m installclean`, then
`m updatepackage`: exit 0 at 00:23 (about 48 min), 14,989 Ninja steps. Soong re-analysed the tree because
`device.mk` changed; with 27 GB of RAM in WSL, `soong_build` (26 GB) used about 21 GB of swap during analysis.
- ZIP: 5,661,591,901 bytes, SHA-256 `2b70cdede70cb1133e797327dd6be626085c5fd8a2baeb4149c56778bc075b30`.
- The image holds `vendor/usr/idc/goodix_ts.idc` with `touch.enableForInactiveViewport = 1`.

## Verification, and a checker that assumed nothing changes

The first verification stopped at `install_integrity` with a tooling failure: `.installable_files` was missing.
Soong's `cleanOldFiles()` (`build/soong/ui/build/cleanbuild.go`, called after Kati) keeps that list only when it
equals the previous build's `.installable_files.previous`; when it changed, it removes the stale installs and renames
the list to `.previous`. evox17 and evox18 installed the same files, so the list stayed. evox19 adds one file, so
only `.installable_files.previous` was left. It was this build's list (written by this attempt's Kati run, 55,913
entries, including the new IDC).

`check_image.py` now reads the list through `install_listing()`: `.installable_files` when present, otherwise
`.installable_files.previous`; the "written by this attempt" mtime gate still rejects a stale list. New test
`test_install_listing_follows_soong_rename` (46/46 checker tests, 20/20 pipeline tests). The checker hash
(`c907ff9d…` -> `f5000c2d…`) was re-registered for the seven checks and the same ZIP re-verified
(`tool_review.py`, `verify.py --recheck recheck01`).

**`recheck01` passed everything** with evox17's counts: the must-hold checks (888 modules, 0 CRC mismatches), all
historical checks, and the seven image checks (policy 31, patch packaging 33, private compatibility 115, Health
45, GMS/themes/apps 674, Doze 62, install integrity 16). `promote.py` moved the delivery to
`output-zips\evox19`.

## On the phone

Dirty-flashed on 2026-10-16 with `lineage_klimt-evox19-flash.bat /flash` (`fastboot update --skip-reboot`, slot b,
no wipe; 296 s, every partition OKAY), then rebooted: `sys.boot_completed=1` after 34 s, `system_server` stable,
no crashes in the crash buffer.

1. `dumpsys input`: `goodix_ts` has `ConfigurationFile: /vendor/usr/idc/goodix_ts.idc`,
   `EnableForInactiveViewport: true`, and the mapper stays `DIRECT` while the phone is `Dozing`.
2. **Fingerprint on AOD unlocks.** The owner locked the phone, waited past the 4 s window and unlocked with the
   fingerprint; logcat shows the lock at 09:12:12.9 and `authenticationState updated: Succeeded(FINGERPRINT,
   DeviceEntryAuthentication)` at 09:13:09.8, 57 s into AOD, through the UDFPS touch overlay. The open question
   from the plan (whether the spot lights and captures while the panel is in doze) is answered: it does.
3. **Double tap on AOD wakes** (owner's test, with Evolution X's AOD double-tap setting on).

Still to watch: pocket wakes and AOD drain over a normal day.
