# evox17 independent source and tooling review

Review date: 2026-10-15. Target: Xiaomi 15T Pro / klimt, Evolution X 12.3 cnb, lineage_klimt-cp2a-user with GMS.

## Decision

**The frozen source matches the stated minimal local-adaptation plan. The verifier still needs three corrections: one high and two medium findings.** I found no demonstrated source-level boot blocker and no reason to restore the reverted optional evox16 patches. Keep the black-AOD overlay and SMPTE 2094-50 guard; use upstream libdmabufheap and upstream su policy. These are source decisions, not a bootability approval. [S1-S8, F1-F3]

The recorded evox16 contamination is addressed directly: build.sh now runs installclean before updatepackage, checks that the eight staged partitions disappeared, and launch.py no longer exposes a focused-precheck mode. The saved negative control rejects evox16's four stray files. That control exits before the new APK/duplicate/Telecom gates, and those later gates have the gaps demonstrated below. No conclusion here says that the running evox17 attempt actually contains a bad APK or stale allocator. [T1-T5, N1]

## Scope, method and limits

Only this report and EVOX17_FINDINGS.json were created or modified by this review. I did not run a build, repo, patch application, checkout, reset, fetch, process-control operation, extraction or phone command. I did not read signing keys. The changing out directory was not inspected or used as candidate-image evidence. Existing source commits, Windows-side records, saved evox16 reports and read-only GitHub APIs supplied the evidence. Python checks used -B and either pure helpers or an entirely in-memory filesystem. [BRIEF.md; Appendix A]

Initial WSL Git reads succeeded for the device history/diff and build/make install-list generation. A later WSL invocation failed with Wsl/Service/WSAETIMEDOUT. I did not restart WSL or intervene in the build; subsequent source reads used immutable GitHub commits. Accordingly, the full live 1,263-project clean-worktree claim comes from FINAL_SOURCE.json and its inspected producer, not a second independent live status sweep. The frozen identities themselves were independently compared. [S1, S2, P1]

This review does not run the seven production image modes against an incomplete evox17 output. The saved 41-test Linux result is identified and checked, but its filesystem-writing test runner was not rerun. Twenty-five read-only helper tests passed on Windows; the system-as-root helper also passed with POSIX path semantics. Its direct Windows execution initially failed because pathlib produces backslashes. That is not a production WSL failure: the production commands invoke python3 in WSL, and the supplied Linux result has no skips. [T4, T5; Appendix A]

## Evidence map

Paths below use forward slashes. Source references name immutable commits; line numbers in tooling references refer to the inspected evox17 files.

| ID | Evidence |
|---|---|
| S1 | C:/XiaomiBuilds/debug/evox17/evox17-frozen.xml; FINAL_SOURCE.json; FROZEN_CHANGES.json; BUILD_READY.json |
| S2 | C:/Users/diogo/Documents/Codex/2026-10-14/ru/work/evox17/final_source17.py; make_build_ready17.py; semantic_checks.json |
| S3 | device/xiaomi/klimt@43b71ecbde010c3444dfb297e9dbd755b1b443c5, compared through Git with a528622c4f52e603a1f3cfa4d998b60da6e0e5c9 and confirmed through GitHub compare |
| S4 | C:/XiaomiBuilds/build-setup/evox/evox17/make-frozen.py:13-29, 38-103 |
| S5 | C:/Users/diogo/Documents/Codex/2026-10-14/ru/android_custom_rom_building_klimt/manifests/snapshots/evox15.xml; evox17.xml; manifests/local_manifests/klimt.xml |
| S6 | ../EVOX16_REVIEW_DISPOSITION.json; ../codex-review/EVOX16_INDEPENDENT_REVIEW.md; build repository docs/evox16-review.md |
| S7 | GitHub immutable source and compare endpoints linked in the source verdicts below |
| S8 | device/xiaomi/klimt@43b71ec:patches/tree/PATCHES.json, BASES, apply.py; archived tree-evox15 SMPTE patch |
| T1 | C:/XiaomiBuilds/build-setup/evox/evox17/build.sh:24-50; launch.py:49-67; corresponding evox16 copies |
| T2 | Same directory, controller.py:125-156, 175-210, 259-335; verify.py:69-89, 95-221 |
| T3 | Same directory, image-checks/check_image.py:302-442, 556-663; references.json; corresponding evox16 copies |
| T4 | Same directory, image-checks/tests.py; TEST_RESULTS.linux.json; IMAGE_CHECKS.json |
| T5 | Independent SHA256 checks, AST parsing, read-only helper execution and in-memory execution described here and in Appendix A |
| N1 | C:/XiaomiBuilds/debug/evox17/install-integrity-negative-evox16/supplemental-install_integrity.json; staged-not-installed.json |
| P1 | ../final_source17.py; ../make_build_ready17.py; C:/XiaomiBuilds/debug/evox17/MANIFEST_MANAGER.json |

### Identities independently checked

- The frozen manifest contains 1,263 unique project paths with immutable revisions. Its path/revision mapping equals FINAL_SOURCE.json.heads, BUILD_READY.json.reviewed_project_heads and the public evox17 snapshot. Frozen SHA256: da33162329999b1a675e5dc88ba17509860aed2d8134be812c8dec121cc07c7b. [S1, S5, T5]
- FROZEN_CHANGES.json contains 54 records and 50 revision changes. Every recorded new_line's project attributes equal the actual frozen project. Comparing evox16 and evox17 FINAL_SOURCE head maps independently also gives 50 revision changes. The public snapshot differs in its introductory comment and adds upstream/dest-branch metadata for kernel/xiaomi/klimt and vendor/xiaomi/klimt; it does not change project revisions. [S1, S5, T5]
- The evox15 snapshot has 1,262 projects; 96 revision mappings differ across the union with evox17. Thus evox17 is an upstream release/update move with fewer local patches, not a byte-equivalent evox15 rebuild. [S5, T5]
- The actual checker hash equals every readiness/registration script hash and the saved Linux test's checker hash. references.json equals the checker's hardcoded reference digest. All five inspected Python entrypoints/checker/test files parse. [T2-T5]

| File under build-setup/evox/evox17 | SHA256 |
|---|---|
| build.sh | 94e8b6f2b7dadeb6ff60b7cbd9dcc32bd0ee0e790dc2ecc4f6a6cb48c5ec291d |
| launch.py | c0ec9c7dab1d42d79f7f9fdbc2e2a55aa541bf215778481556b3349d27d429ed |
| verify.py | 62a8e0160aba2892d3f1efa36c28e0eac9731dea121578f659c8f3382680b476 |
| controller.py | d7cfb9ff9f60b99ddd30a5e204fa47c4b2a5dfb3abdbe58ff8fc1387cf750756 |
| image-checks/check_image.py | bc5576486c065705d30688963737afd99ec49ac3be691fdba8141412b54a6d8b |
| image-checks/references.json | cb444f1020791291bb72f3e80523c0c795653e25cd6014396528effffbb0376f |
| image-checks/tests.py | 273798e48a38aecaae18a63ba110b9782989be57fa4f0e9bf0fe903af12ee3b1 |

## Source review

### Minimality and remaining local changes

The three commits above a80d3d1 are exactly 1e31192 (remove the extra Doze observer), 6339c91 (remove the allocator selector), and 43b71ec (reduce the active patch export). Against evox15's a528622, the only non-patch-bundle file changes are five lines in lineage_klimt.mk and the new five-line overlay-product config.xml. TouchBridge, BoardConfig, UDFPS, Health and the other device runtime files have no net diff in that comparison. The remaining patch-directory changes are the two active exports, exact-tree application tooling and the archived evox15 bundle. [S3, S8; [device comparison](https://github.com/iowaz/android_device_xiaomi_klimt/compare/a528622c4f52e603a1f3cfa4d998b60da6e0e5c9...43b71ecbde010c3444dfb297e9dbd755b1b443c5)]

The active PATCHES.json contains only build/soong and frameworks/native. Each fork is one commit ahead of its stated upstream base, with only the intended allowance or guard diff. Both bases are also the current official Evolution-X cnb heads at review time; the earlier review's claim that the bases were hidden local changes is withdrawn. hardware/interfaces is exactly two commits ahead and zero behind official cnb, covering the existing HIDL-light removal and AIDL-only blank_screen route. [S7, S8; [Soong comparison](https://github.com/iowaz/build_soong/compare/1ac47f839dbb998440f558d886ba03a61954cfe8...ffe1ef057ccd96e9db801e3fb12860c67d9fb71f), [native comparison](https://github.com/iowaz/frameworks_native/compare/49687694bd18a4a2df972f89b6717dbfce610721...2341752da7cc47dfb8ca54af82e8ae825bc53d5e), [lights comparison](https://github.com/iowaz/hardware_interfaces/compare/Evolution-X:cnb...11087c5b9457e65346d0324f5452c647fc080a7c)]

Read-only official-repository commit queries confirmed the frozen heads for frameworks/base, AppLocker, Evolver, Sandbox, Settings, ThemeStore, Bluetooth, Telecomm, Seedvault, system/sepolicy, libdmabufheap, hardware/xiaomi and vendor_evolution. There is no remaining iowaz fork routing for the reverted app/framework/allocator/policy work. This verifies the reviewed derivation/routing set; it is not an independent review of every ordinary upstream commit in all 1,263 projects. [S1, S4, S5, S7, T5]

| Adaptation | Current decision and evidence |
|---|---|
| MIUI boot-jar allowance | KEEP. The only local Soong diff permits miui and miui.*; klimt's boot jar remains selected. [S6, S8; T3:380-390] |
| SMPTE 2094-50 guard | KEEP, explained below. [S3, S6-S8] |
| Existing lights pair | KEEP. Exactly the two required compatibility commits remain. [S6, S7; T3:409-415] |
| Black-AOD product overlay | KEEP, explained below. [S3, S5-S7] |
| TouchBridge extra Doze setting | Leave REVERTED. The bridge equals evox15; separate-Doze-setting support remains a known integration limitation, not a demonstrated boot requirement. [S3; T3:556-573] |
| Independent legacy allocator selector/fork | Leave REVERTED. Upstream retains the binary interfaces and layout; strengthen the vendor producer gate. [S3-S7; F3] |
| frameworks/base + Sandbox + AppLocker changes | Leave REVERTED; frozen projects are official upstream commits. [S1, S6, S7] |
| ThemeStore's four patches | Leave REVERTED; official upstream head, no demonstrated klimt necessity. [S1, S6, S7] |
| Telecomm's two call-flash patches | Leave REVERTED; the source protocol variants are coherent, and module-goal staging caused the recorded boot loop. [S6, S7] |
| Bluetooth missing-device-class patch | Leave REVERTED; no recorded device failure requiring it. [S6, S7] |
| Seedvault WebDAV classification | Leave REVERTED; optional behavior, upstream source restored. [S6, S7] |
| libcore root hiding | Leave REVERTED; frozen AOSP pin 4ebfb391ee0109d16abe6e2bc965724b940928c5 follows the stated 12.3 choice. [S1, S4, S6] |
| Local user-build su gating | Leave REVERTED; upstream policy is deliberate and the exact permissive inventory is checked. [S6, S7; T3:302-378] |
| Settings carrier scan + fork | Leave REVERTED; frozen official upstream source, no observed scan regression supplied. [S1, S6, S7] |
| hardware/xiaomi UDFPS parser + fork | Leave REVERTED; af5766acc6d6766eddeb52574996247128428ff6 is exactly the evox15 pin. [S1, S5-S7] |
| vendor_evolution fork | Keep upstream; no additional local fork remains. [S1, S4-S7] |
| Superseded evox15 purposes | No replay. The saved five semantic records bind the two PduParser fixes, Bluetooth ext_attrs removal, WAP DoS fix and SMPTE guard to frozen heads. I checked those bindings, not a fresh reverse-apply run of every historical patch. [S1, S2, S6] |

make-frozen.py intentionally refreshes other GitHub branch heads while preserving the reviewed device/kernel/vendor/MediaTek-policy pins and restoring upstream routes. Its output is not merely a patch rollback: FROZEN_CHANGES includes upstream WebView, IMS, Launcher, policy and other moves. These are upstream changes, not evidence of extra local adaptations. The frozen snapshot, rather than the floating convenience local manifest, is the reproducible input for this attempt. [S1, S4, S5]

### Four requested verdicts

**black_aod: KEEP.** The a528622 device resource already sets config_dozeSupportsAodWallpaper=false. The frozen 12.3 common product overlay sets it true. The retained device product overlay restores false and is prepended to PRODUCT_PACKAGE_OVERLAYS after common-product inheritance. This preserves the device capability/default across the overlay precedence change; it is not an unrelated new policy. The prior device-tested panel-Doze account is supplied by the disposition; the resource values and net device diff were independently checked. Effective packaged resolution still has to pass doze_packaging after the build. [S3, S6; [device resource](https://github.com/iowaz/android_device_xiaomi_klimt/blob/a528622c4f52e603a1f3cfa4d998b60da6e0e5c9/overlay/frameworks/base/core/res/res/values/config.xml), [common overlay](https://github.com/Evolution-X/vendor_evolution/blob/12eed86fe35dfac19e229bd6c383031e304311e0/overlay/common/frameworks/base/core/res/res/values/config.xml)]

**smpte_guard: KEEP.** All 23 added code lines match the preserved evox15 patch exactly. The guard asks listSupportedMetadataTypes once, avoids an unlisted/non-gettable SMPTE2094_50 request, and returns the same UNKNOWN_TRANSACTION class of result; if metadata enumeration fails, it keeps querying normally. The archived patch and merged review report the observed MediaTek error spam and successful carry through evox15. That historical runtime account makes this a carried device workaround, correcting the earlier characterization as an untested evox16 addition. [S6-S8; [archived patch](https://github.com/iowaz/android_device_xiaomi_klimt/blob/43b71ecbde010c3444dfb297e9dbd755b1b443c5/patches/tree-evox15/frameworks/native/0001-libui-Skip-SMPTE-2094-50-on-mappers-that-don-t-list-.patch)]

**allocator_upstream: OK for this source decision.** The default ION-free source retains the legacy Alloc overload, sync overloads, mapping/query functions and C wrapper APIs needed by the fixture. Its header also deliberately preserves the old private fields for ABI layout, not just symbol names. MapNameToIonHeap becomes a no-op, CheckIonSupport returns false, and legacy sync callbacks are ignored in favor of DMA_BUF_IOCTL_SYNC: this is not a promise of ION semantic equivalence. The saved 57-library/14-ion-caller survey supports linkage compatibility but is not a runtime heap test. [S6; T3:429-442; [allocator implementation](https://github.com/LineageOS/android_system_memory_libdmabufheap/blob/57925b760460430b1424bf0fa4cb0ffe001b9cfd/BufferAllocator.cpp), [preserved layout](https://github.com/LineageOS/android_system_memory_libdmabufheap/blob/57925b760460430b1424bf0fa4cb0ffe001b9cfd/include/BufferAllocator/BufferAllocator.h)]

The libion pin equals evox15 and its backend is a stub. Also, the legacy allocator opens /dev/ion directly; merely checking ion_open would not prove it lacks an ION path. Its QueryIonHeaps would fail its CHECK if it reached the current stub's failing heap query. This weakens a theory that the working baseline depended on successful legacy ION allocation, but remains an inference about an unobserved runtime path. There is no supplied evidence warranting restoration of the independent legacy selector. F3 concerns the checker proving what vendor library was packaged, not the legitimacy of upstream's source. [S5, S6; [legacy constructor/query](https://github.com/LineageOS/android_system_memory_libdmabufheap/blob/57925b760460430b1424bf0fa4cb0ffe001b9cfd/BufferAllocator_legacy.cpp), [libion stub](https://github.com/LineageOS/android_system_memory_libion/blob/abd899da1a42064c66067bc84f427bf27edd81f9/ion.c)]

**su_upstream: OK.** c3997bf608b40a7217d0eb2257af887afa78617b is official upstream and was identical to cnb at review time. Its private/su.te declares permissive su outside userdebug_or_eng. The reference sets expect exactly {'su'} in both normal and recovery policy, and policy() invokes the analyzer on both packaged/reconstructed policies. Additional permissive domains fail. This is an accepted upstream domain exception; the image must not be described as having zero permissive domains. [T3:326-335; [upstream su policy](https://github.com/Evolution-X/system_sepolicy/blob/c3997bf608b40a7217d0eb2257af887afa78617b/private/su.te)]

## Findings

### F1 / E17-001 — HIGH — Telecom pathname is not a payload/protocol check

install_integrity binds the Soong release flag to a selected module name, package identity and expected pathname. It never binds the actual Telecom APK to that module's producer. Its image/staging comparison is a set of names; image hashes are used only to cache aapt2 badging. Both real Telecom variants have the same package identity, so legacy bytes at the shim pathname satisfy the logical gate. No other mode invokes module() for Telecom. [T3:637-663; S6]

The in-memory execution passed all eight assertions with different staged/image payload markers at the expected shim path. The wrong-path control failed. The fixture demonstrates the missing byte comparison; it does not parse a real DEX or claim to have built a second bad image. This is high priority because a passing checker can still miss the exact Binder incompatibility the new Telecom protection is meant to prevent. [Appendix A]

Bind the selected Telecom module to the current install graph and require producer/staging/image hash equality, using the existing module()/installed_target() pattern. Prefer producer binding for every ordinary product APK. Add an end-to-end negative fixture with legacy bytes at the shim path. [T3:234-252]

### F2 / E17-002 — MEDIUM — APK symlinks disappear from duplicate accounting

The scan includes symlinks in its path set, then skips them at line 642 before badging and inventory insertion. The duplicate and Telecom gates consume inventory, not the complete path set. Thus an install-listed symlink alias of another APK can pass path equality while its duplicate identity is never considered. The in-memory regular duplicate failed; the equivalent symlink duplicate passed all eight assertions. [T3:632, 639-663; Appendix A]

Either reject APK symlinks or explicitly resolve them within the extracted Android partition namespace and include their package identities. An unqualified host resolve() would mishandle absolute Android links such as /system/...; also cover dangling links, cycles and escaped targets. The existing obsolete-artifact symlink tests do not cover this path. [T3:45-54, 639-649; T4:106-117]

### F3 / E17-003 — MEDIUM — Vendor allocator implementation lacks producer binding

private_compatibility proves the system libdmabufheap module consumes BufferAllocator.cpp and matches its image bytes. The actual proprietary-facing vendor/lib64/libdmabufheap.so receives only an ELF architecture check and a 15-name export subset check. A stale legacy implementation with those same intentionally retained exports would pass that vendor assertion. It would not prove the stated ION-free vendor producer is packaged. [T3:432-439; references.json:allocator_vendor_abi]

Find the actual vendor module variant in the generated metadata, prove its producer/staging/image hash equality and trace it to BufferAllocator.cpp. Keep the 15-symbol check separately; do not replace it with an exact export-set equality that would reject valid additional upstream exports. Vendor libion also lacks the backend producer proof currently applied to the system variant, so extend the same approach if claiming that vendor backend has been verified. [T3:234-252, 435-442]

## Build process, checks and readiness assessment

| Area | Assessment |
|---|---|
| installclean | Correctly ordered after lunch/target checks and before updatepackage. Eight partition roots are checked, including all three dlkm partitions. This addresses the demonstrated precheck contamination. A broken-link root could evade test -e, but it is not a demonstrated current staging condition or a directory that packs the original stray APK. [T1:33-50] |
| Launcher/supervision | Focused-precheck entry removed. Attempt naming, independent-session handshake, source lock, immutable tooling snapshot and archive exit-record binding remain. No launcher was invoked by this review. [T1; T2] |
| .installable_files | The pinned build/make core/main.mk:1208-1210 writes whitespace-separated PRODUCT_OUT-relative paths; split() and the optional out/target/product/klimt/ prefix removal are appropriate. The attempt owner timestamp check also covers recheck inputs by searching parent directories. No partial live listing was read. [T3:626-632; build/make@646e567:core/main.mk; T5] |
| System-as-root paths | image_relative converts system/system/... to system/...; the POSIX helper test passes. Other partition paths are unchanged. [T3:62-65; T4:44-45; T5] |
| Symlinks | Staged stray detection includes broken/file symlinks; package identity is skipped for APK symlinks. Fix F2. [T3:632, 639-649] |
| Kernel exception | Regex is constrained to direct .ko files and named modules.* metadata in vendor/system/odm dlkm/lib/modules. Nested paths and unrelated files are rejected. The saved negative set has 621 exceptions, including 613 .ko files, so the >=600 check fits that recorded layout. Separate historical gates require 888 total modules, zero CRC mismatches and the one named unresolved symbol. This is still an allowance for known copied module trees, not per-file install provenance. [T3:13, 66-69, 633-636; N1; legacy/musthold.sh:25-58; report-gates.py:13-23] |
| Duplicate allowlist | Exact package-to-sorted-path-set equality permits only the two named Poppins/wallpaper overlay pairs. A third member or changed path fails. This is appropriately narrower than allowing a package name unconditionally. The fixture records their evox15 presence; no new exception is justified. F2 can bypass inventory formation before this correct helper runs. [T3:57-61, 653-655; references.json:allowed_duplicate_packages; T4:46-52] |
| Telecom flag | Both true/false branches, missing flag and ordinary duplicates behave correctly in memory. It reads ANDROID.release_telecom_mainline_module and cross-checks selected modules, consistent with the pinned product switch. F1 and F2 concern the actual APK. [T3:657-663; Appendix A; build/make@646e567:target/product/handheld_system.mk] |
| Policy | Normal packaged CIL is reconstructed using the producer's secilc arguments and compared with the compiled policy; recovery is taken from the extracted ramdisk and analyzed separately. Exact {'su'} is consistent with upstream. Removing the local root-installed analyzer fix does not remove the explicit supplemental analyzer of recovery. Reference policy hashes/source_image labels are historical metadata, not current policy equality gates. [T3:302-378; references.json:policy_reference] |
| Patch packaging | MIUI jar/allowlist and native producer/source/codegen checks remain. Replacing the libcore baseline-tree assertion with the frozen upstream head is consistent with the deliberate AOSP reversion. Exact compiler instruction matching can require reviewed adaptation, but this review found no demonstrated new false alarm on the frozen target. [T3:380-418] |
| Allocator ABI | Fifteen required names are a subset assertion against the vendor library, not a blanket old/new export equality. Necessary linkage evidence, incomplete implementation provenance: F3. The system libion stub check alone does not prove every vendor caller's runtime allocator behavior. [T3:429-442] |
| Doze packaging | Updated two-observer, two-active-user-read expectations match the restored bridge. The forbidden third setting is absent from its pinned source. Existing effective-overlay resolution still checks black AOD after packaged RRO precedence. No current image resolution was executed. [S3; T3:556-619] |
| verify.py | Registers all seven modes, checks reviewed script hashes and fails on nonzero exit. Per-attempt archive copies, pre/post source checks and final static-only labels remain. Findings are inside coverage implementations, not omitted mode registration. [T2:69-89, 118-218] |
| Readiness | Snapshot/head and script hash bindings agree. Its upstream-head statement at make_build_ready17.py:22 checks consistency with FROZEN_CHANGES, not independent upstream ancestry. Its negative-image statement at lines 32-34 checks only the saved stray list. The actual saved report fails there, before APK examination. Interpret these labels narrowly. [P1; N1] |
| Readiness side effect | make_build_ready17.py:24 invokes apply.py, which can run git am on a matching base before the readiness generator rejects non-skip output. On the recorded final trees it skips, but readiness generation is not intrinsically read-only. For future review-only readiness generation, compare recorded HEAD/tree identities directly. This is not evidence of an extra mutation in the recorded attempt. [P1; S8:apply.py] |

The saved negative check used reference digest 3bb3f559... and a synthetic owner start value (the preserved ii_neg scripts set started_ns=0); the final fixture digest is cb444f102.... The report still establishes the early stray-file rejection, because that logic and the four offending paths are present. It does not certify every assertion of the final, later checker/reference combination. The Linux 41-test record matches the final checker hash, but its additions exercise helpers rather than an entire positive/negative install_integrity pipeline. The in-memory whole-function cases in this review expose the resulting coverage gaps. [N1; T4; ../ii_neg.sh; Appendix A]

The public snapshot's generic header says patch projects are pinned to BASES and should be patched after syncing. Its actual project revisions are final heads; apply.py skips an already-final full tree, so the instruction is harmless for this snapshot but the comment should say the pins already include the two patches. The floating local manifest also deliberately follows branches, including lineage-24.0 dependencies; it cannot promise the exact reviewed frozen pins on a later sync. [S5, S8]

## Remaining runtime uncertainty

The source diff preserves evox15's device runtime implementation apart from the justified overlay routing, while the upstream release and numerous project heads change. Static checks cannot establish boot, telephony, graphics, AOD, fingerprint, camera or charging behavior on this release. Unchanged device implementations and retained blob inputs do not establish a camera or charging runtime fix. [BRIEF.md; S3, S5, S6; T2:186-211]

The reverted Doze observer means the bridge mirrors DOUBLE_TAP_TO_WAKE and SCREEN_OFF_UNLOCK_UDFPS_ENABLED only; UdfpsHandler writes touch mode 14 from the mirrored DT2W property. Independent doze_trigger_doubletap changes therefore do not independently arm that bridge path. Treat this as a known feature/integration limitation to evaluate, not as proof of a boot failure or justification for speculative gesture changes. [S3; [bridge](https://github.com/iowaz/android_device_xiaomi_klimt/blob/43b71ecbde010c3444dfb297e9dbd755b1b443c5/apps/TouchBridge/src/org/lineageos/klimt/touchbridge/TouchBridgeApp.java), [handler](https://github.com/iowaz/android_device_xiaomi_klimt/blob/43b71ecbde010c3444dfb297e9dbd755b1b443c5/udfps/UdfpsHandler.cpp)]

After the running attempt finishes, correct/re-review the tooling findings and run the final image gates using the existing named-recheck/tool-review mechanism if needed; preserve the original logs and reports. No source rollback or build interruption follows from this review. A separately authorized phone validation should first establish boot_completed, stable system_server, the selected Telecom package and absence of the incorrect-interface crash, then calls/SIM/eSIM, graphics, camera, fingerprint, AOD/wake and charging. If the lit/unresponsive AOD state occurs, capture it before power-button recovery. None of those phone actions was performed or authorized by this review brief. [T2:112-139, 219-220; S6; BRIEF.md]

## Appendix A — read-only reproduction of the install-integrity gaps

The following runs the actual function with a virtual filesystem stored in a Python dictionary. It creates no temporary files, does not instantiate Check, and never accesses the build output. Run with python -B. A payload marker represents bytes the checker never compares; the symlink fixture models an alias to a second Telecom identity. Badging is mocked, so this tests gate logic, not Android's runtime handling of a particular symlink layout.

Observed results:

| Case | Result |
|---|---|
| Mainline product, correct shim | PASS, eight assertions |
| Platform product, correct legacy pathname | PASS, eight assertions |
| Mainline product with legacy pathname | Defect at Telecom variant assertion |
| Missing release flag | ToolFailure |
| Ordinary duplicate Telecom identity | Defect at duplicate assertion |
| Symlink duplicate Telecom identity | PASS, eight assertions — F2 |
| Legacy payload marker at shim pathname, staging has shim marker | PASS, eight assertions — F1 |

~~~python
import pathlib, types

b = pathlib.Path("C:/XiaomiBuilds/build-setup/evox/evox17/image-checks")
m = types.ModuleType("review_check_image")
m.__file__ = str(b / "check_image.py")
exec(compile((b / "check_image.py").read_text(), m.__file__, "exec"), m.__dict__)
fs = {}

class V(pathlib.PurePosixPath):
    def resolve(self): return self
    def is_file(self): return str(self) in fs
    def is_symlink(self): return fs.get(str(self), {}).get("link", False)
    def is_dir(self): return any(x.startswith(str(self) + "/") for x in fs)
    def read_text(self): return fs[str(self)].get("text", "")
    def write_text(self, text): fs[str(self)] = {"text": text}
    def stat(self): return types.SimpleNamespace(st_mtime_ns=1000)
    def rglob(self, pattern):
        return [V(x) for x in sorted(fs)
                if x.startswith(str(self) + "/")
                and (pattern == "*" or x.endswith(".apk"))]

m.Path, m.P = V, V("/P")
m.os = types.SimpleNamespace(environ={"EVOX_READY": "/attempt/BUILD_READY.json"})

class C:
    def __init__(self, flag):
        self.fs, self.report, self.rows = V("/fs"), V("/report"), []
        self.ref = {"allowed_duplicate_packages": {}}
        self.vars = {"VendorVars": {"ANDROID": {
            "release_telecom_mainline_module": flag}}}
        self.flag = flag
    def identify(self, p): return fs[str(p)].get("digest", "d")
    def need(self, name, condition, details=None):
        self.rows.append((name, bool(condition)))
        if not condition: raise m.Defect(name)
    def tool(self, name): return name
    def run(self, argv, label):
        return "package: name='%s'" % fs[argv[-1]]["package"]
    def selected(self):
        return {"TelecomShim" if self.flag == "true" else "Telecom", "A"}

def fixture(kind="baseline", flag="true"):
    fs.clear()
    fs["/attempt/owner.json"] = {"text": '{"started_ns":1}'}
    app = "Telecom" if flag == "false" or kind == "wrong_variant" else "TelecomShim"
    tele = "system/priv-app/" + app + "/" + app + ".apk"
    paths = [tele, "product/app/A/A.apk"]
    fs["/P/.installable_files"] = {"text": " ".join(paths)}
    for p in paths:
        fs["/P/" + p] = {"digest": "staged-shim" if "TelecomShim" in p else "staged"}
    for i in range(600):
        fs["/P/vendor_dlkm/lib/modules/m%d.ko" % i] = {}
    fs["/fs/system/" + tele] = {
        "package": "com.android.server.telecom",
        "digest": "legacy-payload" if kind == "samepath_legacy" else "staged-shim"}
    fs["/fs/product/app/A/A.apk"] = {
        "package": "com.android.server.telecom"
                   if kind in ("duplicate_regular", "duplicate_symlink") else "p",
        "link": kind == "duplicate_symlink"}
    c = C(flag)
    m.install_integrity(c)
    return len(c.rows)

for label, kind, flag in [
    ("mainline-positive", "baseline", "true"),
    ("platform-positive", "baseline", "false"),
    ("wrong-variant", "wrong_variant", "true"),
    ("missing-flag", "baseline", None),
    ("regular-duplicate", "duplicate_regular", "true"),
    ("symlink-duplicate", "duplicate_symlink", "true"),
    ("legacy-bytes-at-shim-path", "samepath_legacy", "true"),
]:
    try: print(label, "PASS", fixture(kind, flag))
    except Exception as e: print(label, type(e).__name__, str(e))
~~~

The 25 read-only helper tests covered health evaluator positive/negative cases, query parsing, manifest/resource/property parsing, duplicate helpers, kernel exception handling, static overlay ordering, broken-symlink absence semantics and the bound reference digest. The system-as-root helper was tested separately with PurePosixPath. Tests creating TemporaryDirectory fixtures and the stock tests.py main runner were excluded to honor the two-output-files-only rule.
