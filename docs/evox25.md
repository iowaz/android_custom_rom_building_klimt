# Evox25 — restore hardware identity for radio diagnosis

Authorized on 2026-10-21. The gated build attempt is `evox25-attempt01`.
Status: attempt01 built successfully in 1h 1m 11s and passed static image verification on 2026-10-21.
Dirty-flashed to slot b and booted on 2026-10-21; eSIM connectivity recovered. Protected-app refusals remain unresolved.

Evox24-full booted with global Pixel 6a identity but lost mobile registration. The eSIM profile remained
loaded while the modem repeatedly reported NV signature errors, set vendor.ril.imei.check=fail and
rejected radio power-on. This build tests the identity regression hypothesis. The later authorized flash recovered connectivity, as recorded below.

The runtime source delta restores PRODUCT_BRAND/MODEL/MANUFACTURER to Xiaomi / 2506BPN68G / Xiaomi,
removes DeviceName=bluejay, restores DeviceProduct=klimt_global, and restores the SKU-selected model
in libinit. Explicit genuine attestation IDs and the existing canary fingerprint/PIF configuration remain.
No kernel, vendor-blob, modem firmware, telephony, bionic or framework runtime source was changed.

Device source `91d84a9db2c1f4d248ef47523eda3a6245c768fc` includes those changes and an exact-base
bundle export of the PIF-config seed already present in Evox24. Its parent
`0eefef3578eacc6dd1b4955bb7a660291954d6a4` preserves Evox24's prior local full-identity changes.
Both commits are included in the published evox26 device branch. Frameworks/base remains `829dab06450fd192e7fb0115b639b8066052be89`.

`manifests/snapshots/evox25.xml` pins the 1,263 live source projects. Pre-build readiness confirmed clean
worktrees, exact revision agreement, four final patch-bundle trees, five security/source semantics,
registered image-check tests, and capacity. The build runs installclean before updatepackage, then the
single attempt-owned verifier. No source sync or phone operation was issued.

Private evidence and build records live under `D:\android_rom_building\diagnostics\builds\evox25`;
the preceding raw phone captures remain outside this public repository. The current retained ZIPs
include Evox23, Evox24 and Evox24-appsafe. The owner separately freed disk space before this attempt.

Successful static verification will not establish mobile recovery or app compatibility. After a separately
authorized flash, check radio ON/registration, absence of the NV signature-error storm, operator scan,
ordinary call/SMS/mobile data/5G, eSIM persistence, camera, AOD/UDFPS and fresh integrity reports.
eTitulo and Bradesco Saude's protection-policy refusals remain unresolved and are not claimed fixed.

## Delivery and checks

`output-zips/evox25/lineage_klimt-evox25-img.zip`: 5,661,644,458 bytes.
SHA256: `c354796eb3bfaddee314b16fab428db4a02ced1d0f051fc20b3575b1d72c3f8f`.

The producing attempt exited 0. Frozen pre/post build and verification manifests agree. AVB/layout,
saved slot-b DTB/DTBO references, all 888 kernel-module CRCs, 194/194 historical regression checks,
and all seven supplemental image tracks pass. The existing unresolved mtk_drm_gateic_set_backlight
symbol is retained, as in the checked baseline. Static checks are not a boot test.

Focused radio image evidence confirms all ten inspected vendor/ODM identity properties are genuine
Xiaomi/klimt values, and libmtkrilutils.so, libmtkmipc-ril.so and libmtk-ril.so are byte-identical to the
Evox24 investigation's copies. The archive contains no modem/NV partition images. Evidence:
`diagnostics/builds/evox25/RADIO_IMAGE_CHECKS.json` and `reports/evox25-attempt01/RESULTS.json`.

The delivery includes the ZIP, Windows/Linux flash helpers, SHA256SUMS, VERIFIED.txt, RESULTS.json,
COMPARISON.md and the source manifests. The original delivery checks preceded the authorized flash below.

## Authorized dirty flash and runtime checks

On 2026-10-21 the owner authorized rebooting from ADB, flashing slot b without any wipe, and rebooting
Android for retests. The delivered SHA256SUMS and retained Evox23 fallback hash were rechecked first.
The command used explicit `--slot=b update --skip-reboot`, without `-w`. Fastboot exited 0 with
111 OKAY, zero FAILED, no erase/format operations and no slot-a writes recorded. Android booted with
the expected build timestamp 1792587938, slot _b, device klimt and model 2506BPN68G.

All 233 checked third-party package/UID pairs, Android ID hash and two preexisting VD Infos Downloads
hashes match the preflash capture. The file audit was deferred until the owner unlocked credential
storage. These checks support data retention; they are not an exhaustive audit of every user file.

The eSIM remained LOADED. The first captures show the active subscription registered for voice/data,
LTE with NR_NSA display state, and no repeated NV-signature-error storm. The owner confirmed Wi-Fi
and mobile connectivity and requested that further network investigation stop. No network setting,
eSIM profile, NV partition, app data or keybox was reset by this investigation.

Both affected apps still refuse startup. eTitulo stays alive showing its root-policy refusal; Bradesco
Saude terminates and shows the insecure-environment screen. The precise app-side triggering checks are not identified by these logs.

Runtime attestation and spoofing settings were inspected privately. Their per-app target lists and
configuration remain outside this public repository. No attestation-service change accompanies Evox26.

Fresh VD Infos 2.22 exports from 11:38 (Evox24) and 12:04 (Evox25), same day, show 13 -> 15 mismatches.
The partition-device split is resolved. Three new comparisons expose genuine Xiaomi/klimt
Java/native/shell identity versus Pixel identity in attestation. Remaining build metadata, settings and
attestation discrepancies persist. The model row is MATCH even though its attested Pixel 6a value has
compare=false; this illustrates why verdict counts alone are insufficient.

Fresh Duck build 1042 exports from 11:38 and 12:04 both report 1 Danger / 4 Warning / 18 Ready.
Generation versus getKeyEntry certificate materials differ in both cycles, while owner/grant chain
comparisons agree. This is current evidence, replacing the earlier stale-Duck limitation. Source review
finds the existing persistence fix in AndroidKeyStoreKeyPairGeneratorSpi; KeyStoreSecurityLevel.generateKey
still directly returns the underlying service response. This is a candidate coverage gap, not yet a
confirmed app-block cause. No certificate implementation was changed after this flash.

The owner subsequently authorized app-setting experiments and screen control. Adding Pixel Props for
eTitulo, removing it for Bradesco Saude, and testing TrickyStore SKIP and explicit LEAF_HACK separately
for each app did not resolve either refusal. The owner also tested both with Developer options off and
reported no change. Original settings were restored; no app data was cleared. Preliminary lock-screen
captures were excluded and replaced with unlocked app captures.

The automatic attempt to turn debugging off stopped with the adbd child before app launch; the owner
restored ADB and completed that test manually. Its failed automation is recorded separately and disabled.

Inspection of Duck's exact installed source commit 41b35fec8838961c64437a90333c6bc49779a71c confirms
that the failing comparison captures the generation Binder reply before the ROM's later certificate
persistence update. Stored owner/grant agreement therefore does not establish generation/readback
agreement. This remains separate from the unknown protected app-side refusal criteria.

Detailed local evidence: `diagnostics/builds/evox25/flash-runtime-20261021/FINDINGS.md`, FLASH_RESULT.json,
REPORT_COMPARISON.json, SPOOF_CONFIG.json, app-test RESULT files and FINAL_CONFIG_AUDIT.json. Raw
logs, screenshots, QR payloads, settings and app artifacts remain private outside this repository.
NEXT_DIAGNOSTIC_BUILD.md records source-level evidence targets, not an implemented or built fix.
