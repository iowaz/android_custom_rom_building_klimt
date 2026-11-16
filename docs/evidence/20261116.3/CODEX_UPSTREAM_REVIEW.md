# Review: 20261113.3 -> 20261116.2

**Verdict: hold `vendor/gms` at `7ca1155fd6c010353c6b18b45173f4d77af285a7`. Also hold `lineage-sdk` at `1b8e843aedb2342485c9fec0059ae30b8ccc8d0c` until its LiveDisplay safety regressions are fixed.** The GMS rollback is correct and removes exactly one commit. No second definite build breaker was established. The restored keybox patch is complete, but the explanation of its Binder rebase is inaccurate, and the supplied artifacts cannot establish the safety of the unchanged upstream keybox setter/DuckRKP writers.

Locations below are **physical, one-based lines in the supplied diff/patch files**, not reconstructed source line numbers. This is a static review; no source checkout, compilation, flashing, or runtime validation was performed. Binary payloads, unchanged source bodies and the contents of the two newly added projects are outside what these diffs expose.

## Blocker

### B1. AmbientStreaming's source APK is an LFS pointer

- **Project/source:** `vendor/gms`, `product/packages/privileged_apps/AmbientStreaming/{AmbientStreaming.apk,Android.mk}` and `gms_full.mk`.
- **Evidence:** `diffs/vendor__gms.diff:71-79` adds the three-line pointer (declared payload size 33,307 bytes); `104-116` feeds it directly to `BUILD_PREBUILT`; `18-25` selects the app. `114` requires `matcher_tah`, whose definition and binary addition are present at `38-70`.
- **Impact:** pointer text cannot pass APK badging. This agrees with the reported klimt build failure. `.gitattributes` itself is not supplied, so its missing rule is reported context, not independently inspected evidence.
- **Fix:** pin the full old revision above. The commit list at `2-4` contains only `c90f7fc`; this drops the app, product selection and matcher dependency together. No other supplied project introduces a dependency on these module names. Upstream should add the appropriate LFS attributes and ensure the object is available/materialized before restoring the commit. Adding attributes alone does not repair an already checked-out pointer.

## High

### H1. LiveDisplay loses boot and handler exception containment

- **Project/source:** `lineage-sdk`, `LiveDisplayService.java`, `LiveDisplayFeature.java`, `PictureAdjustmentController.java`, `ColorTemperatureController.java` and related display controllers.
- **Evidence:** `diffs/lineage-sdk.diff:548-561` deletes the initialization catch and disabled fallback; `696-726` removes the fallback implementation and per-feature handler catches. `1071-1092` replaces the guarded picture-adjustment range query with a direct HAL call. `145-170` similarly removes color-balance catches. Readiness/publication guards are removed at `514-544` and `739-946`; display callbacks switch from the service handler to an implicit handler at `629-655`.
- **Impact on klimt:** an advertised but unsupported picture-adjustment call, a HAL runtime exception, or an update failure can now escape instead of disabling the feature. An uncaught exception on the service handler can kill system_server. The deleted code specifically handled `EX_UNSUPPORTED_OPERATION` from `IPictureAdjustment.getHueRange()`. The current patch set only changes SDK build constants and does **not** restore these protections.
- **Confidence:** removal of failure containment is confirmed. An actual boot loop on this phone is **not established**: the unchanged `LineageHardwareManager` implementation and current HAL behavior are not included. The newest commit's “Harden LineageHardwareManager” subject does not prove that every removed safeguard is redundant.
- **Fix:** hold the old SDK revision while retaining its two identity patches, or restore the guarded initialization, safe disabled config, per-feature catches, readiness checks and explicit handler delivery. If holding it, restore/re-export the corresponding SDK patch manifest base/final metadata; the current manifest expects the new head. No supplied consumer change requires a new SDK API that would prevent this holdback.

## Medium

### M1. Persisted picture-adjustment parsing can throw after a dirty flash

- **Project/source:** `lineage-sdk`, `PictureAdjustmentController.java`.
- **Evidence:** `diffs/lineage-sdk.diff:1234-1252` removes the per-entry exception handling and null rejection, leaving `Integer.valueOf(modePA[0])` and `HSIC.unflattenFrom(modePA[1])` unchecked. `1255-1270` removes the null guard before `m.flatten()`. H1 removes the outer update containment too.
- **Impact:** a retained malformed `DISPLAY_PICTURE_ADJUSTMENT` value such as a nonnumeric mode ID can now throw when picture adjustment is read/applied; a null decoded HSIC can also fail later serialization. This is conditional on the feature being used and the persisted data being malformed; neither condition is proven for this phone. A wipe is not a fix for accepting unsafe persisted input.
- **Fix:** preserve the old per-entry validation, catch parse failures and discard invalid entries, and keep null filtering when packing. The recommended SDK holdback covers this finding.

### M2. Keybox writes outside the local queue remain an unverified interaction

- **Project/source:** `frameworks/base`, `ActivityManagerService`, `AxSpoofManager`, `TrickyStoreKeyboxMonitor`, and the unchanged upstream setter/DuckRKP implementation. **Suspicion / audit limitation, not a demonstrated new race or permission bypass.**
- **Evidence:** in `klimt-patches/frameworks/base/0003-TrickyStore-Add-scheduled-keybox-monitoring-and-vali.patch`:
  - `97-98`, `1075-1094` show the local writer uses system-user `Settings.Secure` keys `spoof_trickystore_keybox` and `spoof_trickystore_keybox_source`; `1164-1177` writes a private rollback JSON file under `/data/system/trickystore`. It does not directly write a `keybox.xml` file.
  - `309-387` replaces the legacy hourly writer with the monitor queue; `932-974` serializes local requests; `1064-1071` rechecks enablement, DuckRKP state, generation and the current keybox hash before committing. `238-267` requires both `WRITE_SECURE_SETTINGS` and exact UID 1000 for the new operation entry point. That trusts the system shared UID, not exclusively the Settings package.
  - `42-44` shows the upstream setter/RKP declarations, but neither its setter body nor `DuckRkpManager`'s writer is supplied. The upstream framework diff does not change those bodies. The Evolver diff likewise does not change `TrickyStore.kt` or `TrickyStoreContent.kt`; those are changed by the local patch.
- **Impact:** the local manual/check/hourly paths share validation and commit ownership, and monitoring/manual operations refuse to commit while DuckRKP is enabled. This does **not** prove another writer uses the same setting, permissions or queue. The hash check is not an atomic transaction with an independent writer, and a transient RKP enable/disable can escape a final-state-only check if that writer does not invalidate the operation.
- **Fix:** before claiming complete writer serialization, audit the unchanged setter and DuckRKP write/callback paths. If they target the same state, route them through a common commit owner, consistently enforce caller authorization, and invalidate pending operations on every RKP/source replacement. Do not remove the setter or monitor merely because both exist. These artifacts do not justify holding all of frameworks/base for a newly introduced keybox conflict.

## Low

### L1. Twilight receiver hardening is also removed

- **Project/source:** `lineage-sdk`, `TwilightTracker.java`.
- **Evidence:** `diffs/lineage-sdk.diff:1278-1284` removes `RECEIVER_NOT_EXPORTED`; `1369-1383` removes package restriction from the twilight alarm intent and exception containment around scheduling. Handler and location-operation catches also disappear at `1288-1365`.
- **Impact:** the explicit restriction on the internal update receiver is lost. Whether another app can actually inject its update action depends on the unchanged action definition and receiver-registration behavior, which are not shown; external injection is therefore **a suspicion**. Independently, location/alarm failures are no longer contained.
- **Fix:** retain explicit non-exported registration, package-target the alarm and preserve exception handling. The SDK holdback covers this too.

## Info

### I1. Binder append is correct for the new upstream interface, not numerically stable across these builds

`diffs/frameworks__base.diff:141-156` shows `setDuckRkpEnabled`, `provisionDuckRkp` and `setSpoofTrickyStoreKeyBox` **already existed in the old upstream base**. This refresh removes the three gesture methods after them. `diffs/device__xiaomi__klimt.diff:163-191` confirms the old monitor patch appended after those gesture methods and the new patch appends after the setter.

Consequently, the current append leaves all surviving upstream transactions undisturbed, but the local `requestTrickyStoreKeyboxOperation` transaction moves **three slots earlier** than in 20261113.3. Correct the device-tree explanation/comment if intended to claim cross-build stability. Rebuild/deploy framework, services and Settings together; no evidence here requires preserving the removed transaction slots for an ordinary full ROM update. A separately bundled client with hard-coded old transaction IDs would need review; none is identified in this folder.

### I2. Patch completeness and interaction results

All **17 manifest-registered patches** have matching SHA-256 values. The eight changed patched projects have bases matching `INDEX.json`. The four additional MiuiCamera patches were also reviewed. The current frameworks/base 0003 has all 14 file changes, including the AMS implementation, shared contract, controller, resources and tests. The net device-tree diff changes its AIDL placement and AMS indices, rather than dropping its feature implementation.

| Patches | Interaction with this refresh |
| --- | --- |
| frameworks/base 0001 / 0002 | No upstream changes to PackagePartitions or the two charging animation files. Keep the dirty-flash cache discriminator and AOD animation guard. The new edge-light code is a separate feature. |
| frameworks/base 0003 + Evolver 0001 | Still complementary; upstream adds no equivalent scheduled monitor in these diffs. Shared UI helpers retain the signatures used by the patch; the changed switch callback is now nullable and existing callbacks remain valid. Writer uncertainty is M2. |
| frameworks/native 0001 | Gralloc5 is untouched; the MediaTek metadata guard is not replaced by the RenderEngine/SurfaceFlinger or installd changes. |
| lineage-sdk 0001 / 0002 | Build.java and its source group are untouched by the display refactor; constants patches remain necessary. H1/M1 are independent runtime regressions. |
| Settings / Updater / recovery | Their identity consumers and generated-source/header wiring remain intact. Updater changes are translations; recovery changes menu sizing/touch calibration. No overlap making these patches redundant. |
| device/lineage/sepolicy 0001 | New overlay-remounter directory search and ATV Netflix dontaudit rules do not touch the guarded adbroot domain/rules. Keep the patch. |
| hardware/interfaces 0001 / 0002 | Project is unchanged in INDEX. No new supplied dependency on the removed source HIDL lights modules; keep the paired AIDL-only blank_screen change. |
| build/soong 0001 / 0002, build/make 0001, vendor/lineage 0001 | These projects are unchanged in INDEX. No new shown consumer of the removed identity properties. Keep the generated constants provider and all its consumers together. |
| MiuiCamera 0001-0004 | No supplied change to their smali, manifest or required Xiaomi JNI libraries. No interaction found with the Bluetooth audio-policy change. |

### I3. Other build/runtime checks and limits

- The new framework native backup dependency on `libzstd` (`frameworks__base.diff:10969-10975`) has its visibility allowance in `external__zstd.diff:13-20`; keep those updates together. The crypto module, compiled sources and JNI registration are supplied. The absent Argon2 `genkat.h` is behind `GENKAT`; the module does not enable it and explicitly disables worker threads. No missing active vendored include was identified.
- `vendor/extras` moves GoogleSansFlex from its deleted binary to a new fonts project (`vendor__extras.diff:18-32`, `evolution__manifest.diff:35-46`). INDEX pins that new project but supplies no contents: its fonts.mk/module/payload cannot be verified here. WebView APKs were already LFS-managed before this update; pointer changes alone do not establish another AmbientStreaming defect. Materialization of binary payloads remains unverified.
- No automatic app-data wipe or schema rewrite on boot is shown. Backup manifests missing `dataType` default to app backups (`frameworks__base.diff:7188-7192`); new system-data restores are explicit service operations with validation before provider writes. The stricter installd tar handling can now reject truncated/unsupported archives previously accepted; retain matching frameworks/base and frameworks/native updates rather than holding one alone.
- Launcher changes concern layout/cutout handling and secondary displays; no workspace database migration is shown. New edge-light modes default to lockscreen behavior and normalize persisted style/effect values. Lock-screen timeout falls back to the existing device default when unset (`frameworks__base.diff:4644-4658`). Bluetooth codec cleanup moves later in disconnect handling (`frameworks__av.diff:13-34`); reconnect/route behavior needs device testing. APN changes concern China Telecom, with no Brazilian carrier changes shown. Qualcomm HAL/policy changes provide no demonstrated MediaTek dependency failure.

**Holdback decision:** GMS and lineage-sdk as above. No evidence-based additional project holdback. After those decisions, a successful full build and dirty-flash boot/runtime validation are still required; this review does not certify them.
