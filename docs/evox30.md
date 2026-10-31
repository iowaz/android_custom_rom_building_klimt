# Evox30 — current upstreams after the RisingOS klimt review

Prepared on 2026-10-30 for `lineage_klimt-cp2a-user`, signed with the existing private keys, from evox28 plus the current Evolution X / LineageOS / AOSP manifest heads. The owner explicitly kept the separate unbuilt evox29 Wallet/native-property experiment out of this build. Its branches and commits remain preserved. No flash is authorized by this build task.

## Changes against evox28

- RisingOS klimt was reviewed by two agents. No cherry-pick: useful fixes are already present or superseded; the other changes require missing shared MediaTek/eSIM providers and regenerated vendor modules, or remove protections without a reproduced problem.
- The current Evolution X `cnb` manifest is still `16cc234`, but five project heads changed: `frameworks/base` (SystemUI/ColorOS quick settings, glass blur and status-bar behavior), `frameworks/native` (matching RenderEngine blur materials/shaders), `frameworks/opt/telephony` (disconnect tracked IMS calls after a failed start), `packages/apps/Evolver` (Ukrainian translations) and `device/qcom/sepolicy` (audio diagnostic access, not selected by klimt).
- The graph remains 1,263 projects and AOSP `android-17.0.0_r1`. All applicable branch tips were synced. Kernel, kernel-prebuilt, Xiaomi hardware and MediaTek policy have no newer applicable code; their reviewed pins remain.
- All 19 local patches replayed without conflicts across 12 forks. Every stable patch ID matches evox28; a separate aggregate-delta review agrees. Device kernel label `-ab30`; regenerated exact-base bundle for five projects.

## Review and source record

`diagnostics/builds/evox30/REVIEW_DISPOSITION.md` records the A/B decisions and independent review. Source preservation, sync, patch identities and publication records are under `diagnostics/builds/evox30/preparation`; the complete source snapshot is `manifests/snapshots/evox30.xml`.

Checks before launch: clean full graph, exact frozen/live manifest agreement, unchanged signing certificates, all five patch-bundle final trees, five historical semantic purposes, registered image checks and disk gates. The pipeline runs installclean before updatepackage, then its full static verifier.

## Status

Attempt01 started at 23:10 BRT on 2026-10-30. All nine readiness gates passed, with 79.2 GiB free on D: and 100.1 GiB on the build disk. Updatepackage completed successfully in 2h05m08s. Full verification passed at 01:52 BRT on 2026-10-31, without a source fix, verifier correction or recheck:

- All 194 historical checks and must-hold AVB/layout/DTB/DTBO checks passed.
- All 112 metadata assertions passed; kernel `6.6.142-android15-8-gf6a5b29f9fe5-ab30`.
- All seven supplemental image checks passed.
- 888 modules checked, zero CRC mismatches.

Delivery: `output-zips/evox30`, 5,645,910,187-byte ZIP, SHA256 `84b2395b3b90c866e53ef4c8c7a2fa74837fb4a20c9929c70792907796f9a3d2`, with slot-b no-wipe flash helpers. **Image-checked; not flashed or boot-tested.** Evox27 remains the phone build. The separate evox29 experiment remains excluded and preserved.

Records: `diagnostics/builds/evox30/PROMOTED.json`, full verification under `reports/evox30-attempt01`, logs `/mnt/wsl/evox/logs/evox30/evox30-attempt01`. The requested 20-minute monitor stops after verified delivery is prepared.

Runtime checks after a separately authorized flash: SystemUI/quick-settings glass rendering and screenshots/external displays; IMS failed-call retry/cleanup and normal calling; eSIM/mobile data; camera; Bluetooth; MTP; unchanged charging and GED behavior. These are source-reviewed changes, not on-phone validation.
