# Evox31 — upstream refresh of 2026-11-04

Prepared on 2026-11-04 for `lineage_klimt-cp2a-user`, signed with the existing private keys, from evox30 plus the current Evolution X / LineageOS / AOSP heads. The separate evox29 Wallet/native-property experiment stays excluded; its branches are preserved. No flash is authorized by this build task.

## Changes against evox30

- Evolution X manifest `cnb` `16cc234` → `c6ea714`. Its only change moves twelve projects from AOSP to new LineageOS forks set up for the 2026-11 security bulletin. Eleven are still identical to AOSP; broadcom/wlan is not built for klimt.
- 35 projects have new code. For klimt: frameworks/base (Dynamic Island, ColorOS quick settings, TrickyStore boot key/hash, KeyMint attestation version and MODULE_HASH, keybox parsing, PIF CANARY release, SettingsProvider PCC caller check, SystemUI restart coalescing, zram writeback), bionic (four `custom_rom_hide` hardening commits), frameworks/native (phh's GED KPI rewrite, Liquid Glass blur), MediaTek vendor policy (`/dev/conn_dbg_dev`), system/core (property set result check), vendor/lineage (kernel header flags) and LineageOS apps (LatinIME, Canvas, Aperture, Launcher3, translations). hardware/xiaomi's new recovery BLE scanner and `sepolicy/` are not used by klimt.
- AOSP stays at `android-17.0.0_r1`, 1,263 projects.
- **The 2026-11 security bulletin is not in this build.** LineageOS has its 103 patches in review and none merged; AOSP has not published the source yet.
- 16 of the 19 local commits replayed without conflicts, each with the same stable patch ID. Three were dropped because Evolution X now ships the same fix: the TrickyStore all-zero boot key fix (upstream `3bedba09`, and `435c37cb` for the hash) and both GED KPI follow-ups (upstream `74d98cda`). klimt still sets `libgui/support_mtk_ged_kpi`.
- Device tree: kernel `-ab31` and regenerated exact-base exports for the five primary projects. Kernel, kernel-prebuilt and vendor blobs unchanged.
- `wsl-keepalive.ps1` ran `exec -a` under `/bin/sh` (dash), which has no `-a`, so the sleeper exited at once and WSL was never held up. It now uses `/bin/bash`.

## Review and source record

`diagnostics/builds/evox31/REVIEW_DISPOSITION.md` records the decisions. Saved patches, sync, moved projects, replay, patch identities and publication are under `diagnostics/builds/evox31/preparation`; the source snapshot is `manifests/snapshots/evox31.xml` (frozen manifest on iowaz/evox16_manifest `evox31`, `969bd39`). No independent second-agent review was requested for this build.

Readiness: all eight gates passed (frozen graph and live heads, patch bundle final, five semantic purposes, staging cleanup, seven registered image checks, review, source publication, patch identity), with 168.9 GiB free on D: and 168.6 GiB on the build disk.

## Status

Attempt01 started at 09:57 BRT on 2026-11-04. The owner asked for a check every 20 minutes, and a fix and restart on failure.

Runtime checks after a separately authorized flash: kernel `-ab31`; Play Integrity, Wallet and Duck Detector (new TrickyStore and bionic hiding code, upstream's boot key handling instead of ours); GED KPI and GPU frequency; blur and quick settings rendering; calls, IMS, eSIM and mobile data; camera; Bluetooth; MTP. Static image checks are not a boot test.
