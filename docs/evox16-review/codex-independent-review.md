# evox16 independent read-only review

Review date: 2026-10-14/15. Target decision: minimal evox17 on Evolution X 12.3 cnb.

## Verdict

**Reject evox16 as bootable. The demonstrated cause is build-output contamination, not an upstream Telecom protocol defect.** The focused precheck installed unselected legacy Telecom into shared product staging. The full build packaged it alongside the selected TelecomShim. PackageManager chose the legacy package and rejected the correct shim; the mainline loader then published an ITelecomLoader binder as ITelecomService. This reproduces the captured exception exactly. Reverting optional source patches alone will not repair contaminated staging. [B1-B7, F1-F7]

**Exported patches: KEEP 1, REVERT 18, across all 14 projects.** Keep the MIUI boot-jar allowance; retain the two existing lights compatibility commits. Revert the three new device behavior changes and two extra local changes hidden beneath the Soong/native BASES entries. Regenerate a minimal export rather than replaying evox16 wholesale. Keep the coherent upstream 12.3 release. A REVERT here means the adaptation does not meet the owner's necessity standard; it does not imply every patch is technically wrong. [S1-S4; individual verdicts below]

## Scope and verification method

Only the two named deliverables were created or modified. No build, sync, checkout, patch application, repository mutation, phone operation, signing-key read, or contact with the other reviewer occurred. Evox16 source was read through immutable commits in FINAL_SOURCE.json, avoiding the changing working tree. Its 1,263 heads agree with manifest-final-source.xml. Evox15.xml has 1,262 projects; 86 project records differ, including metadata-only changes. All 14 BASES entries, 19 patch SHA256 values and 28 base/final tree identities match Git. Export integrity does not establish patch necessity. [S1-S4]

The brief supplies evox15 as the known-working phone baseline. Both its manifest and archived patch bundle are considered. The manifest alone does not prove every applied/uncommitted patch byte in that historical image; this report does not infer that image's complete contents from pins. The ledger below exhausts project/pin/routing changes and gives local adaptations separate decisions; it does not claim runtime approval of every ordinary upstream feature commit. [BRIEF.md:Background; S5]

### Evidence paths and citation conventions

Source references are `project@immutable-commit:path:line`; reproduce with read-only `git -C /mnt/wsl/evox/src/<project> show <commit>:<path>`. Conventional line numbers refer to pinned source blobs. JSON citations name exact fields. Phone excerpts contain only the necessary technical lines.
- **S1**: `C:/XiaomiBuilds/debug/evox16/FINAL_SOURCE.json; manifest-final-source.xml; source snapshot SHA256 c720a44f043c991015d8d4cce8be77aa52dae8f2d0d245e71a391774bdd7bf2a`
- **S2**: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/BASES; PATCHES.json`
- **S3**: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/*.patch; all 19 patch hashes and recorded base/final trees independently checked`
- **S4**: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/apply.py:11-22; README.md:3-7`
- **S5**: `C:/Users/diogo/Documents/Codex/2026-10-14/ru/android_custom_rom_building_klimt/manifests/snapshots/evox15.xml; old local manifest read at recipe commit 29f5fa0:manifests/local_manifests/klimt.xml`
- **B1**: `C:/XiaomiBuilds/debug/evox16/device-bootloop-20261014/logcat-crash.txt:47-65`
- **B2**: `C:/XiaomiBuilds/debug/evox16/device-bootloop-20261014/logcat-all.txt:29924-29925,31392`
- **B3**: `/mnt/wsl/evox/logs/evox16/evox16-precheck05/precheck.log:36,425; C:/XiaomiBuilds/debug/evox16/PRECHECK_READY.json:modules`
- **B4**: `/mnt/wsl/evox/logs/evox16/evox16-attempt01/build.log:36,86916`
- **B5**: `/mnt/wsl/evox/src/out/target/product/klimt/obj/PACKAGING/target_files_intermediates/lineage_klimt-target_files/META/filesystem_config.txt:2449-2460; installed-files.txt:1479`
- **B6**: `C:/XiaomiBuilds/compare/evox16/evox16-attempt01/rechecks/recheck02/image-apk-duplicate-packages.json:com.android.server.telecom; supplemental-gms_themes_apps.json:status=passed (674 checks)`
- **B7**: `D:/WitAquaBuild/out-evox/lineage_klimt-evox16-img.zip; saved raw image /mnt/wsl/build/compare/evox16/evox16-attempt01/rechecks/recheck02/img/system.img; read-only sparse parsing/hash and debugfs cat results reproduced below`
- **P1**: `C:/XiaomiBuilds/build-setup/evox/evox16/precheck.py:4,40-51,110-114; precheck-build.sh:36-45`
- **P2**: `C:/XiaomiBuilds/build-setup/evox/evox16/controller.py:280-285,309-323`
- **P3**: `C:/XiaomiBuilds/build-setup/evox/evox16/verify.py:118-130,159-178,205-218`
- **P4**: `C:/Users/diogo/Documents/Codex/2026-10-14/ru/work/image_checks/check_image.py:483-507; accepted SHA256 62c7bb5a8087b080f011e1a31bcfce1bbd6b550d2a125d432153c90398248b0a`
- **P5**: `C:/XiaomiBuilds/debug/evox16/evox16-attempt01/TOOL_REVIEW.recheck02.json; /mnt/wsl/evox/logs/evox16/evox16-attempt01/tooling-snapshot.json`
- **D1**: `C:/Users/diogo/Documents/Codex/2026-10-14/ru/android_custom_rom_building_klimt/docs/evox16.md:Boot loop on the phone; checked as a hypothesis against logs/image/source, not used as independent proof`

The inspected precheck.py, controller.py, verify.py and build.sh hashes match the exact accepted recheck tooling contract. The six checker mode entries point to a script whose current hash matches that accepted recheck as well. Thus the process findings below describe the checker that accepted this archive, not an inferred earlier implementation. The original checker had another hash and failed for tooling reasons; its rechecks are preserved. [P5:tooling_sha256/image_checks/evidence; independent hash comparisons]

## Boot-loop root cause

### Exact mechanism

1. The framework contains two intentional protocols. Mainline TelecomLoaderService registers its bound binder directly as `telecom` at line 75 and queries `getSimCallManager` at line 83. Platform TelecomLoaderService first uses `ITelecomLoader.createTelecomService` and replaces the binder with the resulting ITelecomService at lines 69-75. The crash at loader line 83 matches the mainline variant. [F1,F2,B1]
2. `RELEASE_TELECOM_MAINLINE_MODULE` selects the framework variant. The pinned product makefile pairs true with TelecomShim, false with Telecom/TelecomUi/TelecomServiceResources. TelecomLib explicitly includes legacy-src TelecomService and excludes the mainline source; TelecomShim explicitly includes the mainline source. These are coherent alternative product configurations. [F3-F5]
3. Focused precheck05 explicitly requested `Telecom` and installed `/system/priv-app/Telecom/Telecom.apk` (line 425). Full build later installed the selected `/system/priv-app/TelecomShim/TelecomShim.apk` (line 86916). The selected installed-files.txt names only the shim APK, while target-files filesystem_config and the partition image contain both. It is unnecessary to speculate whether the legacy APK was also left from evox15: this precheck positively installed it again. [B3-B5]
4. Both APKs identify as `com.android.server.telecom`, versionCode 37/versionName 17. The accepted image checker recorded the collision. The phone log explicitly says PackageManager failed to scan TelecomShim because that application package was already installed, and nativeloader subsequently names the legacy Telecom path. This proves which package won in the captured boot. [B2,B6]
5. Independent dexdump of the image-identical APKs shows legacy TelecomService$1 extends `ITelecomLoader$Stub`; its createTelecomService initializes TelecomSystem, tags init path `legacy`, and returns ITelecomService. Its onBind returns that loader stub. The shim onBind instead invokes `TelecomServiceInitializerRepository.getInitializer().initialize(this)`. This matches both pinned sources exactly. [F6,F7; bytecode and image hashes below]
6. The mainline loader publishes the legacy ITelecomLoader binder as `telecom`. TelecomManager accesses it through ITelecomService.Proxy; its token fails enforcement in ITelecomLoader.Stub. The uncaught SecurityException escapes the main callback and kills system_server. The relevant log stack follows. [B1:47-65; F1,F6]

```text
logcat-crash.txt:47  *** FATAL EXCEPTION IN SYSTEM PROCESS: main
:48  java.lang.SecurityException: Binder invocation to an incorrect interface
:49  at android.os.Parcel.nativeEnforceInterface(Native Method)
:50  at android.os.Parcel.enforceInterface(Parcel.java:1173)
:51  at com.android.internal.telecom.ITelecomLoader$Stub.onTransact(ITelecomLoader.java:80)
:52  at android.os.Binder.transact(Binder.java:1230)
:53  at com.android.internal.telecom.ITelecomService$Stub$Proxy.getSimCallManager(ITelecomService.java:2077)
:54  at android.telecom.TelecomManager.getSimCallManager(TelecomManager.java:1411)
:55  at com.android.server.telecom.TelecomLoaderService$LoaderServiceConnection.onServiceConnected(TelecomLoaderService.java:83)
```

The decisive package scan is `logcat-all.txt:29925`: `Failed to scan /system/priv-app/TelecomShim: Application package com.android.server.telecom already installed. Skipping duplicate.` Line 31392 names the legacy APK as the loaded path. This evidence distinguishes an image-selection problem from an upstream binder-source disagreement. [B2]

**Attribution: our build/precheck/packaging/verification process.** The exported Telecomm changes affect only Ringer.java; frameworks/base changes only ActivityManagerService.java. Neither changes TelecomService.onBind, loader selection, or binder publication. The pinned upstream product has the correct mainline shim. No source workaround, forced legacy flag, or binder exception catch is justified by these observations. Upstream staging cleanup behavior could be investigated separately; it does not establish a source protocol defect. [F1-F7; per-project diff paths below]

The public build document leaves the selector unexplained and attributes the mismatch broadly to sources/build configuration. The primary evidence refines that account: the release-dependent source pairing is coherent, both APKs were packaged, and PackageManager rejected the correct one. Its narrower statement that Ringer is off the crash path is supported. [D1; B2-B7; F3-F7]

### Pinned reconstruction sources
- **F1**: `frameworks/base@f60f8d1357b56a5f0b946926defe13deae943d31:services/telecom/mainline/java/com/android/server/telecom/TelecomLoaderService.java:75`
- **F2**: `frameworks/base@f60f8d1357b56a5f0b946926defe13deae943d31:services/telecom/platform/java/com/android/server/telecom/TelecomLoaderService.java:69`
- **F3**: `frameworks/base@f60f8d1357b56a5f0b946926defe13deae943d31:services/telecom/Android.bp:12`
- **F4**: `build/make@646e5671fe2617107d12ec56b1ef11ad12bc087f:target/product/handheld_system.mk:104`
- **F5**: `packages/services/Telecomm@1029477e8adee7b35ca154e34b770fe61c5cf25d:Android.bp:253`
- **F6**: `packages/services/Telecomm@1029477e8adee7b35ca154e34b770fe61c5cf25d:legacy-src/com/android/server/telecom/components/TelecomService.java:84`
- **F7**: `packages/services/Telecomm@1029477e8adee7b35ca154e34b770fe61c5cf25d:src/com/android/server/telecom/components/TelecomService.java:34`

### Direct image and archive evidence

| Item | Independently measured value |
|---|---|
| delivered_zip_sha256 | `bba4b20753f86d62cff99a4553cfedc0038991c393ddf2bd91a361d05b549438` |
| delivered_zip_bytes | `5663178762` |
| sparse_system_img_sha256 | `e1dad9da235119d7f3759c980c6104e80a19e8c5fb12be8f4d5518ede6292ab5` |
| unsparsed_system_img_sha256 | `9817acb5e195cf3c8f8ba9257cd5957e392060bb37f759d8ad082a0fa60267ab` |
| legacy_telecom_apk_sha256 | `a077eb590ece405c8226474dfa440ee9b7fd60549e0af526f13e73f9bcc473fc` |
| telecom_shim_apk_sha256 | `1f393cec3869945daa207b587f42378de30e5625ccc5ff479e109835611cf5a1` |

The delivered ZIP hash was recomputed, not merely copied from RESULTS.json. Its sparse system.img was parsed read-only and hashed after expanding RAW/FILL/DONT_CARE chunks in memory: block size 4,096; output blocks 406,258; chunks 34. The expanded hash exactly matches the saved raw system.img. Read-only `debugfs -R "cat system/priv-app/<app>/<app>.apk" <raw-image>` returned 2,642,429 bytes for Telecom and 16,607 for TelecomShim. Their hashes match the saved extraction, recorded duplicate inventory and staged APKs inspected by dexdump. No temporary disk file or new extraction was created. [B6,B7; independent read-only command results]

Bytecode anchors: legacy TelecomService$1 superclass is ITelecomLoader$Stub; constructor invokes that Stub constructor; createTelecomService calls initializeTelecomSystem and getTelecomServiceImpl().getBinder(). Shim TelecomService.onBind at DEX code address 0x00059c calls initializer.initialize and returns its result. Legacy createTelecomService is at 0x0b8f4c in the inspected APK. These identities follow the image hashes above, rather than mutable source assumptions. [B7; F6,F7]

## All 14 exported projects and all 19 patch files

BASES names exact evox16 export parents; it does not guarantee all those parents are pure upstream. Soong and native include additional local base changes addressed below. Every patch hash and base/final tree identity was verified. [S2-S4]

| Project | Evox16 export base | Evox16 derived head | Patch count |
|---|---|---|---|
| frameworks/base | `d84fa40043bca5caddd86325e95a85f932d5e7b7` | `f60f8d1357b56a5f0b946926defe13deae943d31` | 1 |
| build/soong | `1ac47f839dbb998440f558d886ba03a61954cfe8` | `ffe1ef057ccd96e9db801e3fb12860c67d9fb71f` | 1 |
| frameworks/native | `49687694bd18a4a2df972f89b6717dbfce610721` | `2341752da7cc47dfb8ca54af82e8ae825bc53d5e` | 1 |
| libcore | `4ebfb391ee0109d16abe6e2bc965724b940928c5` | `77b7dba97fe8eb92d66654f2a7cf981ef75a1ca1` | 1 |
| system/sepolicy | `c3997bf608b40a7217d0eb2257af887afa78617b` | `5bcb7c60218b3fe43d81520ff634ba4d949f5965` | 1 |
| packages/apps/Settings | `bab27c819a81c53900d5fc4f7cc785c099324346` | `b0e5928b750c5493bff1b53b4b5dbe4959878070` | 1 |
| packages/modules/Bluetooth | `9c3b6fb69cc0ba55ed6814fa04fd36744ca91547` | `9f64386a675bc73bd2a34fe41da4e099338b8800` | 1 |
| packages/services/Telecomm | `3be358b7a129fb6486913c8125e2301c906f7deb` | `1029477e8adee7b35ca154e34b770fe61c5cf25d` | 2 |
| system/memory/libdmabufheap | `57925b760460430b1424bf0fa4cb0ffe001b9cfd` | `22d1435f67bda2c5f7a881b7671406c868c52603` | 1 |
| packages/apps/Sandbox | `fda7e163893dac66381594806cec1f80d00b146c` | `515ba24d62b89a795d31ca80033469ae5c2ec5c6` | 2 |
| packages/apps/ThemeStore | `d96bfe6e6b52236ac5845ac4ed5ac4c93b5fad65` | `1c4ab6d86eab2f34617e1792825f547168dbd15f` | 4 |
| packages/apps/AppLocker | `065f2f5553bcf297fe503b28ef15433447df92a5` | `34d03ec0a4c33d82079f1a4688575a061776f1dd` | 1 |
| hardware/xiaomi | `af5766acc6d6766eddeb52574996247128428ff6` | `f8f00fcc11b8bf5a5ea82ddaae9a3c62b120861a` | 1 |
| packages/apps/Seedvault | `f47750d208dc69bdd65744e49ceb287b43aa5c00` | `30c6534aa6c2fd5974c5b00d5273491e9e0b6afb` | 1 |

### REVERT - frameworks/base/0001-Sandbox-Enforce-privileged-per-user-configuration-mu.patch

Revert the eleven Sandbox mutation permission/user checks: general ROM security/API redesign, not a demonstrated Klimt dependency. Remove the companion application permission changes with it. No phone failure requires this adaptation.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/frameworks/base/0001-Sandbox-Enforce-privileged-per-user-configuration-mu.patch:1`; `frameworks/base@f60f8d1357b56a5f0b946926defe13deae943d31:services/core/java/com/android/server/am/ActivityManagerService.java:21348`.

### KEEP - build/soong/0001-klimt-Retain-MIUI-boot-jar-package-allowance-on-Evox.patch

Keep only the miui package allowance. Klimt explicitly puts miui-framework-stub in PRODUCT_BOOT_JARS_EXTRA; upstream boot-jar package validation has no matching miui expression. Removing the allowance breaks the boot-jar package check while retaining the existing eSIM integration. This carries forward a required baseline fix.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/build/soong/0001-klimt-Retain-MIUI-boot-jar-package-allowance-on-Evox.patch:1`; `build/soong@ffe1ef057ccd96e9db801e3fb12860c67d9fb71f:scripts/check_boot_jars/package_allowed_list.txt:279`.

### REVERT - frameworks/native/0001-libui-Preserve-the-supported-SMPTE2094_50-metadata-g.patch

Revert SMPTE2094_50 capability suppression. The unmodified getter already returns UNKNOWN_TRANSACTION when metadata cannot be fetched. The archived README identifies per-draw log noise, not a demonstrated graphics failure requiring this fork on 12.3.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/frameworks/native/0001-libui-Preserve-the-supported-SMPTE2094_50-metadata-g.patch:1`; `frameworks/native@2341752da7cc47dfb8ca54af82e8ae825bc53d5e:libs/ui/Gralloc5.cpp:333`.

### REVERT - libcore/0001-libcore-Preserve-the-current-Unix-file-visibility-po.patch

Revert UnixFileSystem visibility filtering: it hides /system/addon.d and selected su/busybox/magisk paths using a RootBeer stack scan. This is generic detection policy, not necessary for Klimt build/hardware operation; no integrity verdict proves necessity.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/libcore/0001-libcore-Preserve-the-current-Unix-file-visibility-po.patch:1`; `libcore@77b7dba97fe8eb92d66654f2a7cf981ef75a1ca1:ojluni/src/main/java/java/io/UnixFileSystem.java:63`.

### REVERT - system/sepolicy/0001-sepolicy-Preserve-user-build-su-gating-and-root-poli.patch

Revert the four-file su/root-policy rewrite under the upstream-first scope. Upstream explicitly permits su and exempts root-installed policy from this host check; changing that is general security policy, not a demonstrated Klimt build fix. This restores upstream permissive-su behavior, which must be reported honestly.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/system/sepolicy/0001-sepolicy-Preserve-user-build-su-gating-and-root-poli.patch:1`; `system/sepolicy@5bcb7c60218b3fe43d81520ff634ba4d949f5965:Android.bp:683`; `system/sepolicy@5bcb7c60218b3fe43d81520ff634ba4d949f5965:build/soong/policy.go:576`; `system/sepolicy@5bcb7c60218b3fe43d81520ff634ba4d949f5965:prebuilts/api/34.0/private/su.te:0`; `system/sepolicy@5bcb7c60218b3fe43d81520ff634ba4d949f5965:private/su.te:0`.

### REVERT - packages/apps/Settings/0001-Settings-preserve-carrier-scan-error-and-cancellatio.patch

Revert visible-cell fallback, error/cancellation and executor rewrite. No Klimt modem failure or 12.3 build dependency demonstrates necessity. Cached visible cells are not evidence of a full available-network scan.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/packages/apps/Settings/0001-Settings-preserve-carrier-scan-error-and-cancellatio.patch:1`; `packages/apps/Settings@b0e5928b750c5493bff1b53b4b5dbe4959878070:src/com/android/settings/network/telephony/scan/NetworkScanRepository.kt:22`.

### REVERT - packages/modules/Bluetooth/0001-Bluetooth-tolerate-absent-accessory-device-class.patch

Revert absent-device-class guard in the accessory workaround: a possible generic null dereference, with no Klimt/accessory crash proving necessity. Distinct from the old AVRCP security fix already upstream.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/packages/modules/Bluetooth/0001-Bluetooth-tolerate-absent-accessory-device-class.patch:1`; `packages/modules/Bluetooth@9f64386a675bc73bd2a34fe41da4e099338b8800:android/app/src/com/android/bluetooth/btservice/BondStateMachine.java:564`.

### REVERT - packages/services/Telecomm/0001-Telecomm-cancel-call-flash-by-session-and-retain-acc.patch

Revert incoming-call torch session/accessibility rewrite. It changes optional call-flash behavior, not TelecomService.onBind or TelecomLoaderService. Remove its logging-repair follow-up together with it; reverting only that repair recreates the observed javac failure.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/packages/services/Telecomm/0001-Telecomm-cancel-call-flash-by-session-and-retain-acc.patch:1`; `packages/services/Telecomm@1029477e8adee7b35ca154e34b770fe61c5cf25d:src/com/android/server/telecom/Ringer.java:32`.

### REVERT - packages/services/Telecomm/0002-Telecomm-use-android.telecom.Log-overloads-for-torch.patch

Revert together with 0001: this repairs Log.e/Log.w overloads introduced by the optional torch rewrite. Precheck04:34982-34988 proves the compile error, but removing the complete rewrite removes the need for this repair.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/packages/services/Telecomm/0002-Telecomm-use-android.telecom.Log-overloads-for-torch.patch:1`; `packages/services/Telecomm@1029477e8adee7b35ca154e34b770fe61c5cf25d:src/com/android/server/telecom/Ringer.java:32`.

### REVERT - system/memory/libdmabufheap/0001-libdmabufheap-select-allocator-compatibility-indepen.patch

Revert the independent legacy selector together with d8bc99b. Upstream default allocator and wrapper retain old binary entry points and the default header retains legacy data members. Vendor imports of those methods do not prove the fork necessary. Keep libion backend selection unchanged and validate graphics/media/camera on the eventual authorized test.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/system/memory/libdmabufheap/0001-libdmabufheap-select-allocator-compatibility-indepen.patch:1`; `system/memory/libdmabufheap@22d1435f67bda2c5f7a881b7671406c868c52603:Android.bp:24`.

### REVERT - packages/apps/Sandbox/0001-Sandbox-Restore-app-configuration-for-the-saved-Andr.patch

Revert saved-user restore and cross-user permission additions: general application behavior coupled to the local framework permission rewrite; no Klimt build/hardware requirement established.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/packages/apps/Sandbox/0001-Sandbox-Restore-app-configuration-for-the-saved-Andr.patch:1`; `packages/apps/Sandbox@515ba24d62b89a795d31ca80033469ae5c2ec5c6:AndroidManifest.xml:14`; `packages/apps/Sandbox@515ba24d62b89a795d31ca80033469ae5c2ec5c6:src/com/android/axion/sandbox/io/BackupManager.kt:138`.

### REVERT - packages/apps/Sandbox/0002-Sandbox-Declare-the-required-cross-user-administrati.patch

Revert saved-user restore and cross-user permission additions: general application behavior coupled to the local framework permission rewrite; no Klimt build/hardware requirement established.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/packages/apps/Sandbox/0002-Sandbox-Declare-the-required-cross-user-administrati.patch:1`; `packages/apps/Sandbox@515ba24d62b89a795d31ca80033469ae5c2ec5c6:AndroidManifest.xml:14`; `packages/apps/Sandbox@515ba24d62b89a795d31ca80033469ae5c2ec5c6:src/com/android/axion/sandbox/io/BackupManager.kt:138`.

### REVERT - packages/apps/ThemeStore/0001-ThemeStore-Wait-for-terminal-install-status-after-us.patch

Revert the four theme callback/icon-preservation adaptations: general application fixes without a Klimt dependency. Keep upstream ThemeStore supplied by 12.3.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/packages/apps/ThemeStore/0001-ThemeStore-Wait-for-terminal-install-status-after-us.patch:1`; `packages/apps/ThemeStore@1c4ab6d86eab2f34617e1792825f547168dbd15f:src/com/android/axion/axthemestore/engine/ThemeEngineProxy.kt:86`; `packages/apps/ThemeStore@1c4ab6d86eab2f34617e1792825f547168dbd15f:src/com/android/axion/axthemestore/install/ThemeInstaller.kt:32`.

### REVERT - packages/apps/ThemeStore/0002-ThemeStore-Isolate-callbacks-for-concurrent-install-.patch

Revert the four theme callback/icon-preservation adaptations: general application fixes without a Klimt dependency. Keep upstream ThemeStore supplied by 12.3.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/packages/apps/ThemeStore/0002-ThemeStore-Isolate-callbacks-for-concurrent-install-.patch:1`; `packages/apps/ThemeStore@1c4ab6d86eab2f34617e1792825f547168dbd15f:src/com/android/axion/axthemestore/engine/ThemeEngineProxy.kt:86`; `packages/apps/ThemeStore@1c4ab6d86eab2f34617e1792825f547168dbd15f:src/com/android/axion/axthemestore/install/ThemeInstaller.kt:32`.

### REVERT - packages/apps/ThemeStore/0003-ThemeStore-Preserve-per-app-icon-pack-assignments-du.patch

Revert the four theme callback/icon-preservation adaptations: general application fixes without a Klimt dependency. Keep upstream ThemeStore supplied by 12.3.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/packages/apps/ThemeStore/0003-ThemeStore-Preserve-per-app-icon-pack-assignments-du.patch:1`; `packages/apps/ThemeStore@1c4ab6d86eab2f34617e1792825f547168dbd15f:src/com/android/axion/axthemestore/engine/ThemeEngineProxy.kt:86`; `packages/apps/ThemeStore@1c4ab6d86eab2f34617e1792825f547168dbd15f:src/com/android/axion/axthemestore/install/ThemeInstaller.kt:32`.

### REVERT - packages/apps/ThemeStore/0004-ThemeStore-Isolate-callbacks-for-each-uninstall-oper.patch

Revert the four theme callback/icon-preservation adaptations: general application fixes without a Klimt dependency. Keep upstream ThemeStore supplied by 12.3.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/packages/apps/ThemeStore/0004-ThemeStore-Isolate-callbacks-for-each-uninstall-oper.patch:1`; `packages/apps/ThemeStore@1c4ab6d86eab2f34617e1792825f547168dbd15f:src/com/android/axion/axthemestore/engine/ThemeEngineProxy.kt:86`; `packages/apps/ThemeStore@1c4ab6d86eab2f34617e1792825f547168dbd15f:src/com/android/axion/axthemestore/install/ThemeInstaller.kt:32`.

### REVERT - packages/apps/AppLocker/0001-AppLocker-Declare-permissions-for-the-guarded-per-us.patch

Revert WRITE_SECURE_SETTINGS/INTERACT_ACROSS_USERS_FULL additions with the local framework guards. They are not independently needed once those guards are removed.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/packages/apps/AppLocker/0001-AppLocker-Declare-permissions-for-the-guarded-per-us.patch:1`; `packages/apps/AppLocker@34d03ec0a4c33d82079f1a4688575a061776f1dd:AndroidManifest.xml:15`; `packages/apps/AppLocker@34d03ec0a4c33d82079f1a4688575a061776f1dd:privapp_whitelist_com.android.applocker.xml:7`.

### REVERT - hardware/xiaomi/0001-sensors-Terminate-bounded-UDFPS-status-reads.patch

Revert bounded UDFPS sysfs read/terminator fix and the new fork. Defensible generic parser repair, but no malformed/full-read Klimt capture or 12.3 failure establishes necessity. Use previously working upstream af5766acc6d6.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/hardware/xiaomi/0001-sensors-Terminate-bounded-UDFPS-status-reads.patch:1`; `hardware/xiaomi@f8f00fcc11b8bf5a5ea82ddaae9a3c62b120861a:sensors/v2/Sensor.cpp:381`.

### REVERT - packages/apps/Seedvault/0001-Seedvault-Classify-WebDAV-out-of-space-errors-from-t.patch

Revert WebDAV HttpException import change. It corrects 507 classification for okhttp, but both ktor/okhttp exception classes exist in the pinned dav4jvm jar, so it is not a compile fix. Optional remote-backup classification is outside the Klimt minimum.

Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/packages/apps/Seedvault/0001-Seedvault-Classify-WebDAV-out-of-space-errors-from-t.patch:1`; `packages/apps/Seedvault@30c6534aa6c2fd5974c5b00d5273491e9e0b6afb:core/src/main/java/org/calyxos/seedvault/core/backends/BackendProperties.kt:12`.

### Allocator necessity versus baseline equivalence

Immutable reads through the parked old Git directory named in PARKED.json confirm that evox15 libdmabufheap e2b775649fa5c08d488796a2e299a0f67d7f3352 matches the new legacy implementation in all five implementation/header files. BufferAllocator.cpp hashes to `201016a821d71133707698d477372dc74a80a11a5d99cc0c7041f2752eff8cde`; BufferAllocator.h hashes to `c7a68f28c433ff96ee500565cd8a934e426fa7443e2e23195edbb374da8e6e0d`. This proves preservation of a baseline, not that upstream lacks its required ABI. [PARKED.json:system/memory/libdmabufheap; old pinned blobs; checker references.json:allocator_legacy_files]

Upstream default is explicitly compatible: at `57925b760460430b1424bf0fa4cb0ffe001b9cfd`, BufferAllocator.cpp:74-84 retains construction/destruction and MapNameToIonHeap; :159-162 retains the legacy AllocSystem overload; :180-196 retains callback-bearing CpuSyncStart/End; :215-218 retains CheckIonSupport returning false. BufferAllocatorWrapper.cpp:55-65 retains old C entry points. Default header:118-145 retains ion_fd_, ion_heap_info_, heap_name_to_config_ and the other legacy data members. Thus it would be incorrect to justify KEEP simply by saying old symbols or object fields disappeared. [same pinned default files]

Readelf independently finds old constructor/Alloc/MapNameToIonHeap/CpuSync imports in vendor `hw/mt6991/mapper.mediatek.so`, the graphics allocator and codec2 plugins. The mapper calls the constructor at instruction address 0x1b334. But the upstream default supplies those entry points too. The unresolved question is actual ION fallback/custom-sync behavior, not merely import presence. Legacy BufferAllocator_legacy.cpp:114-117 directly opens /dev/ion, so proving the linked ion_open is a stub does not prove that no legacy code accesses ION. No captured upstream-default failure demonstrates that this behavior is necessary. [vendor@74d378be proprietary ELF dynamic symbols; allocator source; checker private_compatibility:454-461]

Under the brief's rule, revert the selector fork and d8bc99b together, keep normal libion selection unchanged, then validate graphics/media/camera under load. A concrete failing heap/caller or missing ABI in that default would reopen this decision. Do not enable libion.legacy_impl merely as a shortcut. This is a scope verdict with runtime follow-up, not a claim of already demonstrated default-allocator hardware equivalence. [BRIEF.md:Background; allocator sources above]

### Extra base changes, all device commits, explicit forks and existing lights

- **REVERT `base:build_soong:BuildSystemDesc`**: BASES 1ac47f8 carries gen_build_prop.py changes relative to upstream ce8adbbb: preserve generated BuildSystemDesc and use it for system while other partitions use BuildDesc. Klimt sets BuildDesc, not BuildSystemDesc. This is identity policy, not required compile/boot repair. Evidence: `build/soong@1ac47f839dbb998440f558d886ba03a61954cfe8:scripts/gen_build_prop.py:125`; `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:lineage_klimt.mk:42`.

- **REVERT `base:frameworks_native:always-dmesg`**: BASES 4968769 contains an extra dumpstate change on top of upstream ddf96e8: always run do_dmesg even with kernel logcat enabled. Generic diagnostic change, not a Klimt requirement. Evidence: `frameworks/native@49687694bd18a4a2df972f89b6717dbfce610721:cmds/dumpstate/dumpstate.cpp:1813`.

- **REVERT `device:1767eb4`**: Revert independent doze double-tap support: observing DOZE_TRIGGER_DOUBLETAP and OR-ing it with wake expands panel activation policy. New unvalidated feature; working baseline TouchBridge can build 12.3. Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:apps/TouchBridge/src/org/lineageos/klimt/touchbridge/TouchBridgeApp.java:43`.

- **REVERT `device:d8bc99b`**: Revert with the allocator fork: it selects libdmabufheap.legacy_impl=true without a demonstrated failing caller on the upstream compatibility implementation. Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:BoardConfig.mk:41`.

- **REVERT `device:0590205`**: Revert product-overlay priority insertion and config_dozeSupportsAodWallpaper=false: preserving a visual preference against the new common overlay is not a build/boot/hardware requirement. Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:lineage_klimt.mk:28`.

- **REVERT `device:c2ff11b`**: Replace this export content with a regenerated minimal bundle rather than replaying all evox16 adaptations. Export machinery is provenance, not a runtime repair. Preserve historical content in existing Git history; do not blindly revert commits in an actively changing tree. Evidence: `device/xiaomi/klimt@c2ff11bcd784b8dac3954db4eca356ad2cd49a4c:patches/tree/PATCHES.json:1`; `device/xiaomi/klimt@c2ff11bcd784b8dac3954db4eca356ad2cd49a4c:patches/tree/BASES:1`.

- **REVERT `device:ddd3d12`**: Replace this export content with a regenerated minimal bundle rather than replaying all evox16 adaptations. Export machinery is provenance, not a runtime repair. Preserve historical content in existing Git history; do not blindly revert commits in an actively changing tree. Evidence: `device/xiaomi/klimt@ddd3d125eba2fc1ae08e332cff67d902f07260fd:patches/tree/PATCHES.json:1`; `device/xiaomi/klimt@ddd3d125eba2fc1ae08e332cff67d902f07260fd:patches/tree/BASES:1`.

- **REVERT `device:a80d3d1`**: Replace this export content with a regenerated minimal bundle rather than replaying all evox16 adaptations. Export machinery is provenance, not a runtime repair. Preserve historical content in existing Git history; do not blindly revert commits in an actively changing tree. Evidence: `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/PATCHES.json:1`; `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/BASES:1`.

- **KEEP `baseline-lights:c9498a7`**: Keep source light@2.0 removal for existing vendor-prebuilt integration. Upstream declares a system HIDL interface with the same name as the preferred vendor prebuilt; partition/variant conflict prevents using both unchanged. Existing evox15 compatibility. Evidence: `hardware/interfaces@c9498a7e9095af013de1fa31b94480ca538fcc95:light/utils/Android.bp:25`; `vendor/xiaomi/klimt@74d378be9f0b832f2c83284474a0f5da72062ca2:Android.bp:524`; `hardware/interfaces@51053bbf834e3468ada97010cfa42e9b942b94b3:light/2.0/Android.bp:15`.

- **KEEP `baseline-lights:11087c5`**: Keep AIDL-only blank_screen with the source HIDL removal. Otherwise the utility requests a system HIDL light@2.0 dependency that the retained vendor-only prebuilt cannot supply. Existing working lights route. Evidence: `hardware/interfaces@11087c5b9457e65346d0324f5452c647fc080a7c:light/utils/Android.bp:25`; `vendor/xiaomi/klimt@74d378be9f0b832f2c83284474a0f5da72062ca2:Android.bp:524`; `hardware/interfaces@51053bbf834e3468ada97010cfa42e9b942b94b3:light/2.0/Android.bp:15`.

- **REVERT `fork:iowaz/android_hardware_xiaomi:evox16`**: Revert the new fork; only the optional sensor-read repair differs. Evidence: `FINAL_SOURCE.json:derived_heads[hardware/xiaomi]`; `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/BASES:1`.

- **REVERT `fork:iowaz/packages_apps_Settings:evox16`**: Revert the new fork; use upstream carrier-scan behavior. Evidence: `FINAL_SOURCE.json:derived_heads[packages/apps/Settings]`; `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/BASES:1`.

- **REVERT `fork:iowaz/android_system_memory_libdmabufheap:evox16`**: Revert the fork and d8bc99b together; use the Lineage source with its default allocator, keeping libion selection unchanged. Evidence: `FINAL_SOURCE.json:derived_heads[system/memory/libdmabufheap]`; `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/BASES:1`.

- **REVERT `fork:iowaz/build_soong:evox16`**: Replace the aggregate evox16 branch with upstream plus MIUI allowance only; drop gen_build_prop.py policy. Evidence: `FINAL_SOURCE.json:derived_heads[build/soong]`; `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/BASES:1`.

- **REVERT `fork:iowaz/frameworks_native:evox16`**: Revert aggregate fork: remove Gralloc logging guard and extra dumpstate change. Evidence: `FINAL_SOURCE.json:derived_heads[frameworks/native]`; `device/xiaomi/klimt@a80d3d101e7d19f6f5460c36cfeabc7b980b5886:patches/tree/BASES:1`.

### hardware/interfaces freshness

At the audited upstream 12.3 target `51053bbf834e3468ada97010cfa42e9b942b94b3`, the retained fork has **no missing upstream code**. Fork tip `11087c5...` is that base plus c9498a7/11087c5. Full-tree comparison shows only the intended lights source removal and blank_screen changes (14 files), not a 12.3 audio/interface backlog. The upstream AXFX AIDL-audio integration is already beneath the fork. Local evo/cnb and m/cnb refs agree on that target. This is a statement about the audited pin, not later remote movement. [hardware/interfaces pinned commit/tree comparison; FORKS.json; S1]

## Old picks and the superseded claims

Eleven archived patch files are content-superseded by pinned upstream targets. The twelfth, native metadata suppression, is absent upstream and reintroduced locally; remove it as an explicit REVERT, not because it was superseded. The bundle README itself distinguishes that exception. Each nonblank added line of the other eleven patches was checked against actual upstream-base file content, not just a derived evox16 HEAD or a commit subject. The init assignment stays removed. Exact old postimage blob matches are identified below. [device@a80d3d1:patches/tree/README.md:5; archived patches and pinned blobs]

| Archived patch | Upstream decision | Pinned file / blob evidence |
|---|---|---|
| `bionic/0001-evox9-Sync-custom_rom_hide-from-upstream-zygote-exem.patch` | Present: KEEP omission of replay; upstream `3d4169372eaccc2e1ebf5467e1da8bc1d0e31fca` | `libc/bionic/custom_rom_hide.cpp` blob `fc87302da670263c101c929403ebfb15a0ae7fc8` (exact old postimage) |
| `bionic/0002-evox9-Complete-the-custom_rom_hide-sync-statfs-hooks.patch` | Present: KEEP omission of replay; upstream `3d4169372eaccc2e1ebf5467e1da8bc1d0e31fca` | `libc/bionic/custom_rom_hide.h` blob `6d116aa20321d1f52910f8f4a2ead625db425541` (exact old postimage); `libc/bionic/sys_statfs.cpp` blob `3594daee5011846c09ae498665631dd2493504f3` (exact old postimage) |
| `frameworks/av/0001-stagefright-Hide-emitting-non-AOSP-symbol.patch` | Present: KEEP omission of replay; upstream `7eaa22020c6a7196de4c5d1004651ea7498bb0f0` | `media/libstagefright/include/media/stagefright/ANetworkSession.h` blob `401c529f874b98051b4525d07709333044fe71b4` (exact old postimage) |
| `frameworks/base/0001-evox9-Sync-spoof-profile-repo-and-default-PIF-select.patch` | Present: KEEP omission of replay; upstream `d84fa40043bca5caddd86325e95a85f932d5e7b7` | `core/java/com/android/internal/util/evolution/PixelDeviceRepository.java` blob `885f6c8e6b2380439be5f5877a84205522c48e95` (exact old postimage); `services/core/java/com/android/server/spoof/AxSpoofManager.java` blob `62dfde61b0828c2c96f131ded9900388bb76475d` (exact old postimage) |
| `frameworks/base/0002-Fix-security-vulnerabilities-in-PduParser.java.patch` | Present: KEEP omission of replay; upstream `d84fa40043bca5caddd86325e95a85f932d5e7b7` | `telephony/common/com/google/android/mms/pdu/PduParser.java` blob `3ad9cb93f9eb2c9b7b21e14b27c2c0d749d760a0` |
| `frameworks/base/0003-Fix-potential-OOM-in-PduParser-by-using-stream-skip.patch` | Present: KEEP omission of replay; upstream `d84fa40043bca5caddd86325e95a85f932d5e7b7` | `telephony/common/com/google/android/mms/pdu/PduParser.java` blob `3ad9cb93f9eb2c9b7b21e14b27c2c0d749d760a0` (exact old postimage) |
| `frameworks/base/0004-custom_rom_hide-Hide-ROM-packages-on-core-UIDs-from-.patch` | Present: KEEP omission of replay; upstream `d84fa40043bca5caddd86325e95a85f932d5e7b7` | `services/core/java/com/android/server/pm/AppsFilterBase.java` blob `02e7af4416eef17d08ce20385691e64de282bacd` (exact old postimage); `services/core/java/com/android/server/pm/ComputerEngine.java` blob `3517f542b347f0c6b6edccf4de99dba2710aed41` |
| `frameworks/native/0001-libui-Skip-SMPTE-2094-50-on-mappers-that-don-t-list-.patch` | Absent: REVERT nonessential guard; upstream `49687694bd18a4a2df972f89b6717dbfce610721` | `libs/ui/Gralloc5.cpp` blob `d4ec87d53536393def1a62aeba0148ffa7997435` |
| `frameworks/opt/telephony/0001-RESTRICT-AUTOMERGE-Fix-remote-DoS-in-decodeWapPdu-b-.patch` | Present: KEEP omission of replay; upstream `2a7c5f7541a1b286ff967eb67a34c7c984d01458` | `src/java/com/android/internal/telephony/InboundSmsHandler.java` blob `9ddee30ff4833df99b10fac4b0bd59bfb5b455e7` (exact old postimage); `src/java/com/android/internal/telephony/WapPushOverSms.java` blob `ef692a9dc610d0eccefb8b488e8af45404f4b1f9` (exact old postimage); `tests/telephonytests/src/com/android/internal/telephony/WapPushOverSmsTest.java` blob `23b11266d47ee3ebe6e51010f26ff12b44c81900` (exact old postimage); `tests/telephonytests/src/com/android/internal/telephony/gsm/GsmInboundSmsHandlerTest.java` blob `77121d9fc8e6ad1796b772ab86b2c558aaddd6c4` (exact old postimage) |
| `packages/apps/Evolver/0001-evox9-Follow-the-frameworks-PIF-default-in-PlayInteg.patch` | Present: KEEP omission of replay; upstream `a6d361fb258460466c9bd62b548034247333692a` | `src/org/evolution/settings/fragments/miscellaneous/PlayIntegrityFix.kt` blob `17b3caf565a3bbbae14a3b5d0a0360c2a176b7aa` (exact old postimage) |
| `packages/modules/Bluetooth/0001-Remove-unused-ext_attrs-from-playerapplicationsettin.patch` | Present: KEEP omission of replay; upstream `9c3b6fb69cc0ba55ed6814fa04fd36744ca91547` | `android/app/jni/com_android_bluetooth_avrcp_controller.cpp` blob `22a236d44dfff82164dc00d6f0991cf4bde0a947` (exact old postimage); `system/btif/src/btif_rc.cc` blob `c9ef573c6d05a5e7f02c64997ecd5e1a67f14c15` (exact old postimage); `system/btif/test/btif_rc_test.cc` blob `2fb6b81e200daa509f7abf375f18e31b8cb18434` (exact old postimage); `system/include/hardware/bt_rc.h` blob `dee592a3da04caf028d2d23902b709050a1411ca` (exact old postimage) |
| `system/core/0001-init-Remove-sys-property-triggering-custom-rom-detec.patch` | Present: KEEP omission of replay; upstream `ee96af1583278d5c4a32b7ddc6665d0e81e04090` | `init/property_service.cpp` blob `40a76b0cd3c7ea89033e88319b04819ef41d15cb` (exact old postimage) |

PduParser's second patch changes the first patch's intermediate postimage; final blob 3ad9cb9... retains the guards and skip/read checks from both. The WAP fix is present in InboundSmsHandler/WapPushOverSms and both test files. AVRCP JNI/btif/header signatures remove ext_attrs and preserve the changed cleanup ordering. Bionic cpp/header/statfs and stagefright visibility files match old patch postimages exactly. PIF repository/manager/Evolver and framework ROM package hiding are also present. Retiring separate picks therefore preserves the relevant upstream behavior/security fixes. [table source blobs; JSON blob_checks]

The old vendor_evolution commits are **content-superseded, not literally in upstream ancestry**. aea608c6's cp2a security patch is already 2026-10-01; 538db33e's exact bluejay canary fingerprint is already in upstream config/evolution.mk. Both read-only merge-base --is-ancestor checks return false. Thus saying the exact commits are ancestors is false, while saying their relevant content is upstream is true. [vendor/lineage@12eed86:release/flag_values/cp2a/RELEASE_PLATFORM_SECURITY_PATCH.textproto:3; config/evolution.mk:13; old commit diffs]

## Complete manifest delta: all 86 changed project records

This ledger exhausts project/pin/metadata differences between the two requested snapshots. KEEP for ordinary upstream migration means accept the requested coherent release, not assert a proven Klimt failure for every individual upstream commit. Local adaptations are judged separately. Metadata-only records have identical revisions; three repository-source switches also keep the same code SHA. The JSON preserves complete old/new project attributes. [S1,S5; MIGRATION.json]

| Project | Delta | evox15 pin | evox16 pin | Verdict / evox17 target |
|---|---|---|---|---|
| bionic | revision | `cf6e2a93fe4a38d3ab76d99d6c01ef90398b9d8f` | `3d4169372eaccc2e1ebf5467e1da8bc1d0e31fca` | **KEEP** `3d4169372eaccc2e1ebf5467e1da8bc1d0e31fca` |
| bootable/recovery | revision | `9f1765955e4d0b69c17c98ba571238a054522c3a` | `7f7a7931ed6e5d1eda50a096917f766b17d59f6b` | **KEEP** `7f7a7931ed6e5d1eda50a096917f766b17d59f6b` |
| build/make | revision | `2fa923193db876e5be71f6094761600e7ade8b9f` | `646e5671fe2617107d12ec56b1ef11ad12bc087f` | **KEEP** `646e5671fe2617107d12ec56b1ef11ad12bc087f` |
| build/soong | revision | `8babfb68d80f58ed6becd132d5b5f9b29fb5ae2b` | `ffe1ef057ccd96e9db801e3fb12860c67d9fb71f` | **KEEP** `ce8adbbbafd7376385a1fbcb5176563907e8010f + MIUI allowance` |
| device/lineage/sepolicy | revision | `ce2dd8f40f181f7c23db5eaec325fbe825356d2a` | `fe4d5dd55e30bc68cc56b7b9b3fa295389640691` | **KEEP** `fe4d5dd55e30bc68cc56b7b9b3fa295389640691` |
| device/xiaomi/klimt | revision | `a528622c4f52e603a1f3cfa4d998b60da6e0e5c9` | `a80d3d101e7d19f6f5460c36cfeabc7b980b5886` | **REVERT** `a528622c4f52e603a1f3cfa4d998b60da6e0e5c9 + regenerated minimal patch metadata` |
| evolution/OTA | revision | `d8882bf1b63eedd520d754190e5478402fc0debf` | `3885ccff33f8ac1ad5771b482dc6f6464ac3c17d` | **KEEP** `3885ccff33f8ac1ad5771b482dc6f6464ac3c17d` |
| evolution/manifest | revision | `b3001cf680bf348f47bc3d5a76362eb93efcc8a9` | `bc6d0f9172fec886ef2a60d559a2516fd24499ef` | **KEEP** `bc6d0f9172fec886ef2a60d559a2516fd24499ef` |
| external/bash | metadata-only | `1094f161361ad75af92c968da680f2f5b3cf752b` | `1094f161361ad75af92c968da680f2f5b3cf752b` | **KEEP** `1094f161361ad75af92c968da680f2f5b3cf752b` |
| external/exfatprogs | revision | `2914cbb8e7514e824a4792dc3389913c1c4a76ac` | `3379ed50f76459f84e3859aa679942e9daced46c` | **KEEP** `3379ed50f76459f84e3859aa679942e9daced46c` |
| external/htop | metadata-only | `ff411eb6f0b716294440dbb5b24a090a1ad67af9` | `ff411eb6f0b716294440dbb5b24a090a1ad67af9` | **KEEP** `ff411eb6f0b716294440dbb5b24a090a1ad67af9` |
| external/libncurses | metadata-only | `cf8d1a3f3b0ab6f9385c3361e1aada7ecc635ad6` | `cf8d1a3f3b0ab6f9385c3361e1aada7ecc635ad6` | **KEEP** `cf8d1a3f3b0ab6f9385c3361e1aada7ecc635ad6` |
| external/nano | metadata-only | `b83fc23d564c5377fc7c3322e5f75e81d8dad37e` | `b83fc23d564c5377fc7c3322e5f75e81d8dad37e` | **KEEP** `b83fc23d564c5377fc7c3322e5f75e81d8dad37e` |
| external/ntfs-3g | metadata-only | `e2415df401538976fb89aa20370903e0c46e51ff` | `e2415df401538976fb89aa20370903e0c46e51ff` | **KEEP** `e2415df401538976fb89aa20370903e0c46e51ff` |
| external/openssh | metadata-only | `60ca88651d39f699932f63d41409facc18c5ad19` | `60ca88651d39f699932f63d41409facc18c5ad19` | **KEEP** `60ca88651d39f699932f63d41409facc18c5ad19` |
| external/rsync | metadata-only | `6a2e628ca95b172243abfdad1e86b88fb895fb3f` | `6a2e628ca95b172243abfdad1e86b88fb895fb3f` | **KEEP** `6a2e628ca95b172243abfdad1e86b88fb895fb3f` |
| external/unrar | metadata-only | `140cfb9e8fc984cab5060cd09983e6d33a2fae41` | `140cfb9e8fc984cab5060cd09983e6d33a2fae41` | **KEEP** `140cfb9e8fc984cab5060cd09983e6d33a2fae41` |
| external/vim | metadata-only | `f31199df8fca8148b61ae94bbfcb834021f5bdd9` | `f31199df8fca8148b61ae94bbfcb834021f5bdd9` | **KEEP** `f31199df8fca8148b61ae94bbfcb834021f5bdd9` |
| frameworks/av | revision | `c4c4dc7608a3fe0d6a5f18df551a6ad6edf8730e` | `7eaa22020c6a7196de4c5d1004651ea7498bb0f0` | **KEEP** `7eaa22020c6a7196de4c5d1004651ea7498bb0f0` |
| frameworks/base | revision | `5f381df28726f865acd0333cb436d17419ab6265` | `f60f8d1357b56a5f0b946926defe13deae943d31` | **KEEP** `d84fa40043bca5caddd86325e95a85f932d5e7b7` |
| frameworks/hardware/interfaces | metadata-only | `9de6d032a248523c22d0bd86e224d1762355c41e` | `9de6d032a248523c22d0bd86e224d1762355c41e` | **KEEP** `9de6d032a248523c22d0bd86e224d1762355c41e` |
| frameworks/libs/systemui | revision | `bbdabb45579be65fe802330f6cf4651333b967ae` | `25fdfb3dc77cbe9876c43656b75d297a6da08054` | **KEEP** `25fdfb3dc77cbe9876c43656b75d297a6da08054` |
| frameworks/native | revision | `75e2cc6363936395299f10577e765a2425509316` | `2341752da7cc47dfb8ca54af82e8ae825bc53d5e` | **KEEP** `ddf96e8644294cacbd955dd6358f4f3cd84f5ccd` |
| frameworks/opt/telephony | revision | `a0aa60e8014152a704dd64f84f78e2dc0b87a5ae` | `2a7c5f7541a1b286ff967eb67a34c7c984d01458` | **KEEP** `2a7c5f7541a1b286ff967eb67a34c7c984d01458` |
| hardware/google/interfaces | metadata-only | `a36774a8665b72a64cb495501984e8fa0cbb0e53` | `a36774a8665b72a64cb495501984e8fa0cbb0e53` | **KEEP** `a36774a8665b72a64cb495501984e8fa0cbb0e53` |
| hardware/interfaces | metadata-only | `11087c5b9457e65346d0324f5452c647fc080a7c` | `11087c5b9457e65346d0324f5452c647fc080a7c` | **KEEP** `11087c5b9457e65346d0324f5452c647fc080a7c` |
| hardware/lineage/compat | revision | `9a7a916bb5d88514d66014bb3f753fa834a16b31` | `1f286a02837632c4ed352c50c0ff3c1cf00368fe` | **KEEP** `1f286a02837632c4ed352c50c0ff3c1cf00368fe` |
| hardware/qcom/sm7250/display | metadata-only | `d3fae6913731a30c135a6cd1fab803913da06998` | `d3fae6913731a30c135a6cd1fab803913da06998` | **KEEP** `d3fae6913731a30c135a6cd1fab803913da06998` |
| hardware/qcom/sm7250/gps | metadata-only | `c0e0375f06c0335062f19e3d87cb84d3c27cbc57` | `c0e0375f06c0335062f19e3d87cb84d3c27cbc57` | **KEEP** `c0e0375f06c0335062f19e3d87cb84d3c27cbc57` |
| hardware/xiaomi | revision | `af5766acc6d6766eddeb52574996247128428ff6` | `f8f00fcc11b8bf5a5ea82ddaae9a3c62b120861a` | **KEEP** `af5766acc6d6766eddeb52574996247128428ff6` |
| kernel/xiaomi/klimt | metadata-only | `b13ac15b32e25368f70859fff986e07c18d9d5a5` | `b13ac15b32e25368f70859fff986e07c18d9d5a5` | **KEEP** `b13ac15b32e25368f70859fff986e07c18d9d5a5` |
| libcore | revision | `015f87dfc4ed76b269374f4ed375de7a67d4400b` | `77b7dba97fe8eb92d66654f2a7cf981ef75a1ca1` | **KEEP** `4ebfb391ee0109d16abe6e2bc965724b940928c5` |
| lineage-sdk | revision | `c3efc4ee11e2348a058f71b021e2ab4c403fdc64` | `2be2443660a55a6d7534e6bd622422a72f758aa5` | **KEEP** `2be2443660a55a6d7534e6bd622422a72f758aa5` |
| packages/apps/Aperture | revision | `f7c0a93f787cc9e0db4193b6094bd51575567898` | `36b3be3487b5154b1950ed2120225acdca6c51de` | **KEEP** `36b3be3487b5154b1950ed2120225acdca6c51de` |
| packages/apps/AppLocker | revision | `93f26734c6720de000db1e9168fedf9dd8903115` | `34d03ec0a4c33d82079f1a4688575a061776f1dd` | **KEEP** `065f2f5553bcf297fe503b28ef15433447df92a5` |
| packages/apps/AudioFX | revision | `2dbd5919f5736d0737f8d95a2618f0f05b835a4e` | `193fdf7d81eccfefa0f438e1d18386a7fd92f572` | **KEEP** `193fdf7d81eccfefa0f438e1d18386a7fd92f572` |
| packages/apps/Backgrounds | metadata-only | `b087d2df6601aa25939e654028321bb59857d12e` | `b087d2df6601aa25939e654028321bb59857d12e` | **KEEP** `b087d2df6601aa25939e654028321bb59857d12e` |
| packages/apps/Camelot | metadata-only | `ef9cfc2fcced48ff46f6be580f3f653b05bae08e` | `ef9cfc2fcced48ff46f6be580f3f653b05bae08e` | **KEEP** `ef9cfc2fcced48ff46f6be580f3f653b05bae08e` |
| packages/apps/Canvas | added | `(absent)` | `115bed958a82fb9bcc3a770e23eedf40a3442978` | **KEEP** `115bed958a82fb9bcc3a770e23eedf40a3442978` |
| packages/apps/Catapult | revision | `922ab7ddee9b3ed0106b148feaf3ff1ad88db727` | `554ba69fc5aed8bac353a2d226fa2871918552b1` | **KEEP** `554ba69fc5aed8bac353a2d226fa2871918552b1` |
| packages/apps/ColumbusService | revision | `a37be7db6fe0260cf2a137975df447e55261144e` | `b8167ad9c86adebdf54fe3bba0e03f37ee112ed6` | **KEEP** `b8167ad9c86adebdf54fe3bba0e03f37ee112ed6` |
| packages/apps/DeskClock | revision | `616807bba7008e460a714bc4e122b842c12dd0e1` | `5e49fdf15c5fae64cc6c23f6ab4a66d62b0a7a73` | **KEEP** `5e49fdf15c5fae64cc6c23f6ab4a66d62b0a7a73` |
| packages/apps/Dialer | revision | `6da8042323a97d5b3cba1fd975709cc42f29916f` | `3f51f16031ea82f82606a080f418d924b87b7966` | **KEEP** `3f51f16031ea82f82606a080f418d924b87b7966` |
| packages/apps/Etar | revision | `3cda65da396e64c3ac936512816ad4c35c9a4958` | `8173ec802ed046d1670ec03962e686e393a85335` | **KEEP** `8173ec802ed046d1670ec03962e686e393a85335` |
| packages/apps/EuiccPolicy | revision | `7232f94f1a908272d4b72bf13277a54c889f9f2c` | `3b3c28e8e537ffd182def2dedde3987b01a60f0f` | **KEEP** `3b3c28e8e537ffd182def2dedde3987b01a60f0f` |
| packages/apps/Evolver | revision | `1b4360f1fb666a9951aad0679eea5c881edd1af1` | `a6d361fb258460466c9bd62b548034247333692a` | **KEEP** `a6d361fb258460466c9bd62b548034247333692a` |
| packages/apps/ExactCalculator | revision | `153847a298160cbf10c50bdbcdfbc956ae9400c9` | `108f08bd85aadab42c231a7df94770370aea9d08` | **KEEP** `108f08bd85aadab42c231a7df94770370aea9d08` |
| packages/apps/FMRadio | metadata-only | `095ae21580f2893b1f00f0bd9b503dc766899ad1` | `095ae21580f2893b1f00f0bd9b503dc766899ad1` | **KEEP** `095ae21580f2893b1f00f0bd9b503dc766899ad1` |
| packages/apps/FlipFlap | metadata-only | `0e9b6f6bc7991e3689348bc295ebd12e4b2e78ea` | `0e9b6f6bc7991e3689348bc295ebd12e4b2e78ea` | **KEEP** `0e9b6f6bc7991e3689348bc295ebd12e4b2e78ea` |
| packages/apps/Gallery2 | metadata-only | `73803da5c066e0d6f67319d28087c965234b7850` | `73803da5c066e0d6f67319d28087c965234b7850` | **KEEP** `73803da5c066e0d6f67319d28087c965234b7850` |
| packages/apps/Glimpse | revision | `c7b5e8cfbb4e941473f3179322ec8513d83b4ca9` | `8caac09fe1fe0cadb2fa828ac5755c8fb9481eb5` | **KEEP** `8caac09fe1fe0cadb2fa828ac5755c8fb9481eb5` |
| packages/apps/Jelly | revision | `1bb5edd564f2adb475fb565373426166f3ca252a` | `8ba5afd7b9d4319f263dfeb9ce744924ad137812` | **KEEP** `8ba5afd7b9d4319f263dfeb9ce744924ad137812` |
| packages/apps/LineageCustomizer | metadata-only | `84b03919bfb15aa3c72bacdd28c1f900df9385db` | `84b03919bfb15aa3c72bacdd28c1f900df9385db` | **KEEP** `84b03919bfb15aa3c72bacdd28c1f900df9385db` |
| packages/apps/LineageParts | revision | `e08d880bc4bab9e0ac690867e27b0dfb060b78c3` | `7a094594a77e06396f97396316dfa46e6c6c33c9` | **KEEP** `7a094594a77e06396f97396316dfa46e6c6c33c9` |
| packages/apps/Messaging | revision | `6d131ed8e7249b0ece41169e17d8d0162beae7e0` | `e8d54f169338b16d545d175868645ead8c83e979` | **KEEP** `e8d54f169338b16d545d175868645ead8c83e979` |
| packages/apps/Profiles | metadata-only | `0abb3a177f1532b6b85621a7250a6431027f02a6` | `0abb3a177f1532b6b85621a7250a6431027f02a6` | **KEEP** `0abb3a177f1532b6b85621a7250a6431027f02a6` |
| packages/apps/Recorder | revision | `4650818fbc158d996263b4a21b378af4deb9970a` | `624957ca18496e7b63df3d5e4e040f8c99ca72b7` | **KEEP** `624957ca18496e7b63df3d5e4e040f8c99ca72b7` |
| packages/apps/Sandbox | revision | `8c1e9fdb0d9965f4c0c5e48df8e147f8888da093` | `515ba24d62b89a795d31ca80033469ae5c2ec5c6` | **KEEP** `fda7e163893dac66381594806cec1f80d00b146c` |
| packages/apps/Seedvault | revision | `29301617a99030c3ae0e14de64eadbc73bd2bd63` | `30c6534aa6c2fd5974c5b00d5273491e9e0b6afb` | **KEEP** `f47750d208dc69bdd65744e49ceb287b43aa5c00` |
| packages/apps/Settings | revision | `9ea49ef11849ad2f4c64c380010b36c04cdd6620` | `b0e5928b750c5493bff1b53b4b5dbe4959878070` | **KEEP** `bab27c819a81c53900d5fc4f7cc785c099324346` |
| packages/apps/SimpleDeviceConfig | removed | `a3f56e8b82558fecbea96137c092f22b051199ad` | `(absent)` | **KEEP** remove |
| packages/apps/SimpleSettingsConfig | metadata-only | `4e6f18165761c7833967597bfe02d0f43273f91a` | `4e6f18165761c7833967597bfe02d0f43273f91a` | **KEEP** `4e6f18165761c7833967597bfe02d0f43273f91a` |
| packages/apps/ThemeStore | added | `(absent)` | `1c4ab6d86eab2f34617e1792825f547168dbd15f` | **KEEP** `d96bfe6e6b52236ac5845ac4ed5ac4c93b5fad65` |
| packages/apps/Twelve | revision | `45dc00e20ba4ee560a1dabd60b72e5a788747aec` | `de4ff1b687f9bb53a229d60e61bfd563f3bad383` | **KEEP** `de4ff1b687f9bb53a229d60e61bfd563f3bad383` |
| packages/modules/Bluetooth | revision | `2daafd384d5985cc84654da5ae299bff85d5929c` | `9f64386a675bc73bd2a34fe41da4e099338b8800` | **KEEP** `9c3b6fb69cc0ba55ed6814fa04fd36744ca91547` |
| packages/modules/Wifi | revision | `bd162a1d735a03baa98a5015eb697097c70b52ec` | `a45b3c140b9ff68b6e082e2efe3009603f2bdfa1` | **KEEP** `a45b3c140b9ff68b6e082e2efe3009603f2bdfa1` |
| packages/resources/apps | revision | `eb5bf8bf77717974a9ef9cdfbcf44b8a9f991076` | `91d835b073de0f3208430467a217a14549777cc8` | **KEEP** `91d835b073de0f3208430467a217a14549777cc8` |
| packages/resources/devicesettings | revision | `b3556d4d8bb517fd9bd44f53d4cff9078a247829` | `661fc4036da370a73e56dbd2949c18f8ab464b9b` | **KEEP** `661fc4036da370a73e56dbd2949c18f8ab464b9b` |
| packages/services/OmniJaws | revision | `22c7c89d7c12e0a379e83d0474ef49b7e2f564e2` | `83f9fb29597f91e6b3685d46c3068449af440e2a` | **KEEP** `83f9fb29597f91e6b3685d46c3068449af440e2a` |
| packages/services/Telecomm | revision | `fb585fcd9648898bbbe2a6f3871987ad6dc8b9c9` | `1029477e8adee7b35ca154e34b770fe61c5cf25d` | **KEEP** `3be358b7a129fb6486913c8125e2301c906f7deb` |
| packages/services/Telephony | revision | `2a6ef7d3ed54f0e4d3de3a48d122b40e3e74ef3f` | `b07a812762ff58516a7014c58d3b5b8b8819f19e` | **KEEP** `b07a812762ff58516a7014c58d3b5b8b8819f19e` |
| system/core | revision | `39f6732ee8c3ec0fa6daefa0fd38e833a519a6d5` | `ee96af1583278d5c4a32b7ddc6665d0e81e04090` | **KEEP** `ee96af1583278d5c4a32b7ddc6665d0e81e04090` |
| system/fs/fs_mgr | revision | `6db70ed0b12a6da338dfa652913c03b5524e216e` | `6be2394ed00fdc4ba2ff9cd7037e0a7a2d4d8656` | **KEEP** `6be2394ed00fdc4ba2ff9cd7037e0a7a2d4d8656` |
| system/memory/libdmabufheap | revision | `e2b775649fa5c08d488796a2e299a0f67d7f3352` | `22d1435f67bda2c5f7a881b7671406c868c52603` | **KEEP** `57925b760460430b1424bf0fa4cb0ffe001b9cfd` |
| system/sepolicy | revision | `1facbe510fdd0ed771bd04b16e891045f7f73112` | `5bcb7c60218b3fe43d81520ff634ba4d949f5965` | **KEEP** `c3997bf608b40a7217d0eb2257af887afa78617b` |
| system/update_engine | revision | `5b9591570c6603d73ab86f8526f4280ccfea1849` | `1ef2cbc4f6f3fee374b9124b005da6eab13f8880` | **KEEP** `1ef2cbc4f6f3fee374b9124b005da6eab13f8880` |
| system/usb | metadata-only | `4a587a2ffcf50a483ae93eab2221c0ba692c0b15` | `4a587a2ffcf50a483ae93eab2221c0ba692c0b15` | **KEEP** `4a587a2ffcf50a483ae93eab2221c0ba692c0b15` |
| vendor/extras | revision | `a1c0dff051071eb3596deb7f949a120ab917a4f9` | `0b8438de544ae36793ed3a2955aeaa27e9e97c16` | **KEEP** `0b8438de544ae36793ed3a2955aeaa27e9e97c16` |
| vendor/gms | revision | `ccd9f9a924cd7cc35ae648f90dac26ff3bb954be` | `3e0987a856ee8bdd21b9ff1983a8e182873a64ad` | **KEEP** `3e0987a856ee8bdd21b9ff1983a8e182873a64ad` |
| vendor/google/overlays/ThemeIcons | removed | `f31418902bd408e8f00b5e72bb6d187aacbddff5` | `(absent)` | **KEEP** remove |
| vendor/lineage | revision | `aea608c6f6d1e81203e30a5db472e3b3dbb23a48` | `12eed86fe35dfac19e229bd6c383031e304311e0` | **KEEP** `12eed86fe35dfac19e229bd6c383031e304311e0` |
| vendor/pixel-style | revision | `7bfb22daa4d7e1349acc11ac96b36988f68170da` | `70094c9d50313e34fcd4e82b433494fe92a3cac6` | **KEEP** `70094c9d50313e34fcd4e82b433494fe92a3cac6` |
| vendor/themes | added | `(absent)` | `7d8236cf8495ea673652c5cfa3a3eaf773f39542` | **KEEP** `7d8236cf8495ea673652c5cfa3a3eaf773f39542` |
| vendor/unbundled_google/packages/SettingsGoogle | revision | `512aed92509f0a489547901178781f00b9c97fa6` | `e7466bd103f9c605ef9af776dd41fbaddc30eeec` | **KEEP** `e7466bd103f9c605ef9af776dd41fbaddc30eeec` |
| vendor/unbundled_google/packages/SystemUIGoogle | revision | `d6d8d19ecb3d9b3718dd4c520edbe39c06029c3f` | `a852b90cee67be987b5754161bb5b6db9c246e38` | **KEEP** `a852b90cee67be987b5754161bb5b6db9c246e38` |
| vendor/xiaomi/klimt | metadata-only | `74d378be9f0b832f2c83284474a0f5da72062ca2` | `74d378be9f0b832f2c83284474a0f5da72062ca2` | **KEEP** `74d378be9f0b832f2c83284474a0f5da72062ca2` |

Kernel source b13ac15..., kernel prebuilt a2d1dae..., proprietary vendor 74d378be..., and MediaTek vendor-policy 117a8de... are unchanged. Existing device Health/Wi-Fi/eSIM/UDFPS/vendor-policy integration is part of the working baseline, not a new evox16 experiment. Keep those baseline routes for this upgrade. [S1,S5; local manifest @29f5fa0]

## Process findings and concrete evox17 changes

P1: Precheck contract explicitly included unselected legacy Telecom (PRECHECK_READY.json:modules; precheck05/precheck.log:36,425). Use graph-selected TelecomShim in mainline prechecks; isolate optional legacy probes from product staging.

P2: Shared incremental staging was not cleaned to selected install closure. Full build installed TelecomShim, but target-files META/filesystem_config.txt:2449-2460 and raw image contain both. Recreate staging or run controlled installclean in a future authorized build, then verify actual filesystem equals selected install closure.

P3: Accepted checker recorded duplicate com.android.server.telecom yet passed. check_image.py:483-507 explicitly treats duplicates as evidence only. Fail closed on duplicate application identities unless an exact reviewed split/overlay exception applies; this pair is not one.

P4: ZIP freshness/hash and source pin checks do not prove every installed member selected/current (controller.py:309-316; verify.py:118-130,159-178). A freshly generated ZIP can include stale/unselected APKs. Bind actual partition files to graph-selected targets and exact producer bytes.

P5: Obsolete-file absence fixture only covered seven GMS paths (checker:503-507). Cover all retired/unselected install paths, including legacy Telecom and removed manifest projects; check inside delivered images.

P6: No gate checked flag-dependent Telecom protocol pairing. Verify frozen RELEASE_TELECOM_MAINLINE_MODULE, loader variant, selected app manifest/onBind contract, required mainline dependencies and exactly one installed com.android.server.telecom.

P7: Gates enforced optional Gralloc/libcore/allocator/su/Doze changes as mandatory acceptance. Proving a patch installed does not prove necessity. Rebase requirements on minimal accepted configuration and report deliberate security/preference changes explicitly.

P8: Precheck04:34982-34988 caught wrong Log overloads in our Ringer rewrite. docs/evox16.md reports a host stub with the wrong signature. Use actual production APIs for compile validation; removing the optional rewrite eliminates this repair.

P9: VERIFIED.txt literally said runtime pending, so it did not claim successful boot. Nevertheless an already-recorded fatal duplicate was accepted as image verified. Distinguish build-complete/static-image-pass/boot-pass/functional-pass; static labels must not imply bootability.

P10: Preserve original artifacts/rechecks and retain useful source freeze, hashes, signing-certificate, AVB, kernel, VINTF and producer gates. Checker repairs must not waive real defects; the new duplicate/selection gate must reject the known-bad evox16 image.

P11: Before evox17 is boot-validated, separately authorized device testing must reach sys.boot_completed=1 with stable system_server, one Telecom package, no incorrect-interface crash, lockscreen/basic calls. Then validate SIM/eSIM, graphics/media/camera, fingerprint/AOD, radios and charging. No phone operation was performed by this review.

The useful controller safeguards should remain: frozen source/tree and tool identities, archive/producer hash checks, resource/VINTF/policy inspection, AVB/layout/kernel verification, process ownership and preserved failed/recheck artifacts. Their absence was not the demonstrated cause. The missing enforcement boundary is the complete selected install set and its runtime interface contracts. Fresh ZIP timestamps do not make every packaged member fresh or selected. [P2-P5; B3-B7]

### Required negative and final-image checks

- The new duplicate/selection gate must reject the known-bad evox16 inventory even when source/producer/ZIP hashes all pass. Exact reviewed split/overlay rules may explain a duplicate identity; a blanket exemption may not. The old report has three duplicate identities, including font/wallpaper overlays: do not indiscriminately delete unrelated packages. [B6]
- Read the delivered partition images and inventory package/split identities across all partitions. Assert exactly one selected com.android.server.telecom; for mainline, legacy Telecom.apk absent and TelecomShim present with matching loader/onBind contract. Bind files to the product-selected dependency closure and producers. installed-files.txt and apkcerts.txt alone are insufficient: the former missed the packaged legacy APK and the latter includes definitions for unselected buildable modules. [B3-B7; F3-F7]
- Replace hardcoded mandatory local-patch assertions with requirements matching this minimal set: upstream default allocator producer, no demanded Gralloc guard/libcore filter/new Doze overlay, explicit reporting of upstream su policy. The checker currently proves accepted-patch installation, not hardware necessity. Security behavior changes must remain visible. [checker patch_packaging:417-443/private_compatibility:454-461; per-patch sepolicy verdict]
- Recreate clean partition staging after prechecks/graph changes or use a separate output directory. An authorized installclean may be sufficient without erasing all compiler caches, but prove stale APK absence rather than assuming a command name guarantees it. This report executes no cleanup/build. [P1-P3; B3-B7]
- Production API compilation must reject wrong Log overloads; optional host stubs must match the real API. Precheck04 was a real failure in the local torch rewrite, not evidence upstream needed our patch. [precheck04/precheck.log:34982-34988; D1 process narrative]
- Generic emulator/interface tests can supplement offline checks; they do not qualify Klimt vendor hardware. A separately authorized real-device boot must reach boot_completed, stable system_server, one Telecom package and basic calls before the image is called boot-validated. Then test SIM/eSIM, AOD/fingerprint, graphics/media/camera, radios and charging. [BRIEF.md hard rules; P9/P11]

## Minimal evox17 set

1. Use coherent pinned Evolution X 12.3 cnb manifest and declared AOSP/Lineage dependencies; preserve existing hardware device/kernel/proprietary/vendor-policy baseline identities.

2. Retain evox15 device implementation a528622 (eSIM/MIUI stub, Wi-Fi shim, UDFPS/TouchBridge, Health, SELinux and vendor/camera integration). Drop 1767eb4/d8bc99b/0590205 and replace full evox16 export with regenerated minimal metadata.

3. On build/soong upstream ce8adbbbafd7376385a1fbcb5176563907e8010f retain only miui boot-jar allowance; drop BuildSystemDesc policy.

4. Retain hardware/interfaces 11087c5b9457e65346d0324f5452c647fc080a7c: upstream 51053bb plus existing c9498a7/11087c5 lights compatibility. No audited 12.3 upstream gap.

5. Use upstream frameworks/native ddf96e8644294cacbd955dd6358f4f3cd84f5ccd, hardware/xiaomi af5766acc6d6766eddeb52574996247128428ff6, Settings bab27c819a81c53900d5fc4f7cc785c099324346 and Lineage libdmabufheap 57925b760460430b1424bf0fa4cb0ffe001b9cfd with default selector and unchanged libion selection.

6. Use BASES upstream frameworks/base/libcore/sepolicy/Sandbox/AppLocker/ThemeStore/Telecomm/Bluetooth/Seedvault; none of their evox16 patches remain. Use vendor/lineage upstream 12eed86 with already present security-patch/fingerprint values.

7. Do not replay superseded old picks. Deliberately drop the native metadata guard as nonessential, not superseded. Defer optional fixes to separate observed-regression work.

8. Build-process prerequisite: recreate clean partition staging after install-graph changes; mainline precheck uses TelecomShim; reject duplicate Telecom, prove legacy APK absent and flag/loader/onBind contract coherent inside delivered image. No framework workaround needed.

Only the MIUI boot-jar allowance and the existing lights pair are justified common-tree local compatibility changes at these pins; the remaining retained hardware implementation is the known-working device/kernel/vendor baseline. The other 18 exported patches and both extra base changes are excluded. Nothing in this review justifies modifying upstream Telecom binder contracts or forcing legacy release flags. [individual verdicts; F3-F7]

## Limits and deciding future evidence

- No rebuild or phone test performed. Removing nonessential patches is a scope verdict, not proof the resulting ROM works.

- hardware/interfaces comparison is to audited 12.3 pin 51053bb, not later remote movement.

- Full project/manifest ledger does not claim line-by-line runtime approval of every upstream feature.

- Default allocator preserves compatibility entry points/data members; graphics/media/camera behavior after selector rollback still requires validation. No captured default-path Klimt failure establishes necessity of the fork.

No local adaptation is silently retained as UNSURE. Where necessity was not established, the owner's explicit rule makes the current verdict REVERT. A real build error at the accepted upstream pin, a captured hardware regression tied to the changed API/heap/parser, or an explicit expanded feature/security requirement would justify reopening a specific decision. Static parity/review alone does not. In particular, the default allocator still needs graphics/media/camera testing; upstream user-build su behavior needs transparent security acceptance; the source-minimal candidate has not been built or booted by this review. [BRIEF.md:Background; per-change evidence]
