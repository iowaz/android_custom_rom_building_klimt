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

Attempt01 started at 23:10 BRT on 2026-10-30. All nine readiness gates passed, with 79.2 GiB free on D: and 100.1 GiB on the build disk. The detached controller startup was confirmed and its status entered `building`. Build startup and eventual result are recorded in `diagnostics/builds/evox30`. Not yet image-checked, flashed or boot-tested.

The requested 20-minute monitor is active in this chat (`monitor-evox30-build-every-20-minutes`). It may diagnose/fix build failures and launch a fresh attempt, and promotes delivery only after the full verifier passes. It must stop when complete or when user action is required. Current logs: `/mnt/wsl/evox/logs/evox30/evox30-attempt01`.

Runtime checks after a separately authorized flash: SystemUI/quick-settings glass rendering and screenshots/external displays; IMS failed-call retry/cleanup and normal calling; eSIM/mobile data; camera; Bluetooth; MTP; unchanged charging and GED behavior. These are source-reviewed changes, not on-phone validation.
