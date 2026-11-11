Publication note: the owner later authorized implementation and source publication for review. Phone flashing/reboots remain withheld. This is the archived reviewed plan; local diagnostic paths refer to private build-machine evidence, which is not included here.

# Klimt device and kernel change plan

Version 3, 2026-11-11. Claude Opus 5.5 High reviewed versions 1 and 2; its second verdict was **APPROVE with conditions**. This version applies its C1-C6 clarifications and minor notes. Opus explicitly said C1-C4 needed no further review round. See `OPUS_REVIEW.md`, `OPUS_RECHECK.md` and `REVIEW_DISPOSITION.md`; both submitted versions are preserved. Strategy approval is distinct from implementation/flash gates still requiring evidence and owner authorization.

This is a complete proposed implementation and validation sequence. This request authorizes planning and independent review; it does not execute source changes, builds, publication or phone operations. The phone has no root. Nothing in this plan depends on obtaining it.

## 1. Decision

Make a conservative kernel maintenance release first. Follow it with a separate, measured device-property candidate for high-refresh SurfaceFlinger scheduling. Correct misleading renderer/tracing configuration and the stale build documentation as small, separately recorded device-tree commits. Do not bundle speculative memory, compiler, architecture, module-pruning, AVB or thermal changes into that release.

Every Fable item has a disposition below. "Deferred" means there is a specified investigation and admission gate, not an undocumented omission. The kernel update is conditional on actual source/KMI review; the display values are experimental until comparison testing succeeds. Neither a higher version nor an enabled optimization proves a device benefit.

## 2. Evidence and fixed baseline

Use build `20261108` as the boot-tested baseline, not the older Windows device checkout, which is behind origin. As of this planning pass, the two public owner heads still match the baseline:

| Component | Baseline |
|---|---|
| Device, `cnb` | `dd6cb60867de159231a9430cbecabfb6eb78d09f` |
| Kernel, `17.0` | `f6a5b29f9fe59e4849680d50232f8b5758aa8c11` |
| Kernel build/prebuilts, `17.0` | `a2d1dae44726c14b1295f4042cddd9fedacd39e0` |
| Private vendor, `cnb` | `5ee96dc9f52651fffc241a5ede2722cfe8c350ee` |
| Frameworks/native upstream base | `cb8303a432fc2eb4ea3bf57ec450501e18f2cced` |
| Frozen manifest | `repositories/android_custom_rom_building_klimt/manifests/snapshots/20261108.xml` |
| Current build-tool checkout | `f459fcda77745f7ed103f0b45278b35d3509a146`; freeze its chosen implementation-time revision separately |
| Actual source platform SPL | 2026-11-01, recorded by `docs/20261108.md`; distinguish this from reported identity properties |
| Reported platform/vendor SPL | 2026-10-05; extract emitted image properties and all boot/AVB rollback fields from the baseline artifacts for the mechanical comparison |

The live phone on 2026-11-11 reports kernel `6.6.142-android15-8-gf6a5b29f9fe5-ab20261108`, slot b, Android 17/user, shell UID 2000, SELinux enforcing. Runtime platform/vendor patch properties report 2026-10-05; these are part of the owner's personal identity layer and do not establish the actual upstream patch inventory.

Relevant measured facts:

- atrace flags and tracefs `tracing_on` are both zero;
- `skiagl` is set, but the renderer already runs through a RenderEngine thread;
- late app/SF work durations remain 20/15.6 ms at both 60 and 120 Hz; early/early-GL remain 20/27.6 ms;
- the exact frozen framework reads numeric per-rate suffixes, such as `debug.sf.late.sf.duration.120`; those keys are unset;
- AutoFDO is disabled; `CONFIG_LTO_NONE=y`; MGLRU is compiled in but runtime-enabled mask is zero;
- 574 modules are loaded, including all four `pkvm_*` modules. All 252 vendor_boot list entries are present. `ptp_kvm` and `mtk_swpm_isp_dbg_v6991` are absent from the other load lists; causes are unproven;
- the AIDL 3 thermal HAL supplies changing CPU/GPU/SoC and other temperatures, thresholds and cooling devices;
- one Settings scroll interval produced 5 new modern janky frames / 6,362 new frames, about 0.079%. This is one current-build baseline, not proof of optimal latency.

Evidence: `diagnostics/reviews/20261110-fable52/CLAUDE_REVIEW.md`, its updated `DISPOSITION.md`, and `device-verification-20261111/DEVICE_VERIFICATION.md`. Raw dumps are local/private; do not publish them or provide them wholesale to the reviewer. Three downloaded framework files and their hashes are available in that evidence directory.

## 3. Scope and repository rules

Keep the owner repositories on their default branches: device `cnb`, kernel `17.0`, vendor `cnb`. No per-build branches. Use separate commits and date-based build tags, `docs/<build>.md`, `docs/history.md` and `manifests/snapshots/<build>.xml`. Resolve available `YYYYMMDD[.N]` build names when execution starts; do not reserve or label fictitious builds now.

ROM projects remain upstream. Any indispensable klimt-specific ROM fix must use the existing device `patches/` bundle and `patches/apply.py`; do not create ROM-source forks. This plan currently needs no new ROM patch. Keep the existing personal identity layer exactly as requested, including keys, reported identity and patch-level policy.

The source disk is not mounted in this planning session. Actual source work must go through WSL shell from `D:/android_rom_building`, never a Windows source-tree folder link or app file editor. Before execution, verify mounted paths, disk capacity, source lock and active attempts, clean heads and exact existing patches. Preserve the unrelated untracked `docs/designs/` content in the build repository. No pipeline edits while a build runs.

## 4. Stage K — kernel maintenance, first release

### K0. Resolve and audit the target before changing the build tree

Primary fixed candidate: official `android15-6.6-lts` commit **`1c39bb5f635a741f90a5ecb4535e7bd264083a80`**, reviewed by Opus as 6.6.144. This retains the owner's existing LTS lineage. The owner's history contains `b13ac15` (take the android15-6.6-lts tree, upstream parent `c3dd858`, 2026-09-09), followed by the four-file klimt compatibility change `8935932` and the localversion/config change `f6a5b29`. Resolve the full parent and local commit SHAs and define the net klimt delta mechanically as `c3dd858..f6a5b29`; require it to match the expected four-file set and the later config adjustment, investigating any additional path rather than ignoring it. Take the audited target tree while replaying/adapting the actual complete delta with the established owner integration approach, rather than switching release branches.

Reference only: Google's `android15-6.6-2026-10_r3` release, listed as 6.6.143 and released 2026-11-07. Live official `git ls-remote` resolved:

- annotated tag object: `b4216da3e023cb6f74b4a85ba1f6e286c0a614bd`;
- peeled kernel commit: `1a04d7d18c1d8ba591bc372781ddbe5bf49a30f0`.

The r3 release is a reference, not the implementation target. Google's certified binary status does not transfer to this source-built, trimmed klimt kernel. Opus verified KMI generation 8, branch android15-6.6 and declared Clang r510928 on the owner kernel and r3; check the same fields on the pinned LTS target and verify the actual build compiler, which can differ from the declared build.config value. Do not choose arbitrary mainline, 6.12, 16 KiB pages or replacement vendor modules. A GitHub mirror returned a different LTS head; use the official fixed object.

In an isolated audit checkout, retrieve enough history to identify the true ACK base, all local commits and the target's ancestry. Store `KERNEL_DELTA.md`, `kernel-refs.json`, config/type/protected-export reports and the preflight source hashes under this plan directory's future `kernel-audit/` subdirectory, with release copies under `diagnostics/builds/<build>/`. Classify every local delta as keep, upstream-equivalent, adapt or reject; use patch IDs/tree diffs where histories differ. List actual imported upstream fix areas and any verifiable security fixes; do not invent a CVE gap from dates or release numbers.

Budget the audit before cloning. The distro VHDX is physically on D:, even though its guest root reports about 950 GiB free. Live host free space in this planning pass was about 63.4 GiB on C: and 62.3 GiB on D:; the review's older capacity numbers are not current. Prefer a named bare object store on C: (no Windows kernel worktree, which fails on aux.c), with an isolated WSL worktree and explicit allowance for its D:-backed VHDX growth. Reserve up to 12 GiB for audit objects initially, check both real host drives and guest capacity during retrieval, and stop before compromising build reserves. Increase the budget only after checking physical headroom. Retain required local objects/bundles until they are published and reproducibly referenced; then remove only the explicitly generated audit cache after preserving the ledger.

Budget analysis outputs separately from those 12 GiB of git objects: start with at least another 12 GiB for old/new kernel type-analysis output, refine the estimate from the actual baseline build and stop if it cannot fit while preserving the physical host and guest build reserves. Multiple debug analysis builds can need more. No packaged output/config or its source lock is reused for these analysis jobs.

If the pinned LTS target drops already present fixes, changes the GKI/KMI generation or fails the vendor contracts below, stop it. Select and re-review another fixed official same-generation LTS commit, or a justified compatible fix subset, updating the exact SHA and rationale. An unresolved ancestry/KMI/EL2 question blocks implementation.

### K1. Preserve the vendor contract

Retain 4 KiB pages, Android15-6.6 KMI generation, header v4 and current image compression/layout, DTB/DTBO payloads, stock OS3.0.335 vendor/firmware, module loading/aliases, GKI exported symbol policy and existing required symbols. Preserve `__counted_by` exclusion under `__GENKSYMS__` in `include/linux/compiler_types.h` (or verified equivalent), the klimt ABI symbol whitelist, trim/retain logic, existing vendor-facing adaptations and protected-mode boot arguments. Do not re-sign vendor modules as trusted GKI modules.

Keep the resolved running configuration for this first update: no AutoFDO, LTO, MGLRU, architecture, debug-option or module-pruning experiments. Compare generated `.config`, not only defconfig text; explicitly review new upstream defaults. The two absent baseline modules are not a reason to remove them, and the 574 live count is not interchangeable with 888 packaged instances.

**Additional mandatory ABI gates beyond CRC equality:**

1. Classify every old-base-to-target change in `arch/arm64/kvm/hyp/`, `arch/arm64/include/asm/kvm_pkvm_module.h` and related pKVM headers and call paths. Specifically investigate the review's E2H initialization, SCTLR_EL1 initialization, hypervisor stack-page transfer and `used_lrs` bound changes against the stock EL2 modules. CRC equality does not cover this interface.
2. Compare old and new `pkvm_module_ops` layout, callback signatures and interface semantics. Require unchanged field offsets/sizes and compatible calls using baseline/candidate vmlinux DWARF/BTF/STG with pahole or equivalent type analysis. If the necessary type data is absent, use separately scoped, analysis-only old/new builds in isolated output directories with any debug information needed for type extraction. Never add those debug options to the packaged configuration or contaminate the release staging tree. Preserve relevant compiler/ABI flags and review analysis-versus-release differences. If compatibility remains unresolved, stop rather than infer it from module loading.
3. Run a type-aware old/new ABI comparison (`stgdiff` or the supported Android ABI tool) restricted to the complete klimt retained/imported symbol contract. The in-tree `.stg` is reference data, not itself a command. Record the actual tool/version, inputs and all differences. Changes hidden from genksyms must still be reviewed. Confirm every klimt-whitelist entry's membership in Google's tracked symbol sets; explicitly identify out-of-contract symbols and block unreviewed changes to their provider types/semantics.
4. Compare Google's protected-exports and protected-modules policies old/new against every stock vendor module name and its undefined symbols. A newly restricted import is a blocker even when symbol CRCs match. Keep this check distinct from normal export presence and module signatures.

These are new checks; the current pipeline is not claimed to implement them. Their reports must become readiness/verification inputs before the candidate is called ready.

### K2. Exact implementation surfaces

| Location | Intended change |
|---|---|
| `kernel/xiaomi/klimt`, default `17.0` | Integrate the audited ACK changes with all necessary local compatibility deltas retained; record old/base/target/final heads. No unrelated tuning. |
| `device/xiaomi/klimt/configs/kernel/metadata.config` | Replace the actual source SHA comment and `-g<kernel-head[:12]>` with the final owner kernel HEAD; retain the preceding build token until the existing `prepare.py label` changes the build label. The label step checks the kernel hash and fails if this is missed. |
| `device/xiaomi/klimt/BoardConfig.mk` | Correct the stale "kernel source is unchanged" comment for the newly audited source. Preserve ABI copy-to-OUT_DIR behavior, external modules and existing metadata identity fields. Change metadata.config's corresponding wording too, retaining `relabel()`'s previous-name and old-label cardinalities. |
| Build repository `build-setup/evox/pipeline/report-gates.py` and `check-metadata26.py` | Replace hard-coded 6.6.142/f6a5 kernel expectations with a frozen-source-derived expected release, while keeping historical release-profile checks valid. These are known required changes, not optional execution-time investigation. |
| Build repository `build-setup/evox/pipeline/tests.py`, readiness/controller inputs and tooling hash map | Cover new/old release profiles, bad source SHA, wrong version/KMI/build label, tampered inputs and stale evidence. Bind new ABI/pKVM/rollback evidence to source/build hashes and make missing/failing gates stop readiness/promotion. Include all modified verifier/tool files in attempt provenance. |
| Build repository preparation path | Add and review a minimal explicit frozen-candidate preparation mode, described below, instead of bypassing live-head checks or pretending upstream/sync accepts moved local kernels. |
| Build repository records | New frozen manifest, date-named record and history entry; source/ABI/config comparison and gate results. No broad acceptance-rule weakening. |

Do not blindly regenerate `klimt_defconfig` from upstream. Preserve config initially; handle indispensable upstream necessities explicitly. Remove `MEMFD_ASHMEM_SHIM` cleanup from this first candidate entirely; it belongs in the later config ledger, if useful.

**Frozen-candidate preparation contract:** the current upstream step rejects non-device live-head drift, and a normal sync follows the remote shallow kernel branch. Do not disable those protections globally. Implement a narrowly scoped preparation entry point requiring the baseline frozen manifest, an exact local candidate kernel SHA and local audit-repository path, and an allowlist of only the kernel/device changes plus reviewed pipeline tooling. Fetch the candidate through WSL into the existing kernel repository and check out that exact SHA detached, without moving its local `17.0` branch. Advance the default `17.0` branch only in the audit repository; advance the remote only after validation and owner-approved publication. A rejected local candidate is abandoned by a clean detached checkout of the preserved baseline, losing no commits and requiring no reset or giant merge revert. Deepen only the audit history as needed; do not merge in the shallow build checkout. Confirm every non-allowlisted project and patch bundle still matches control, apply/check existing patches, update metadata, label/freeze and bind the resulting manifest/heads to readiness. A sync or unexpected head drift invalidates readiness. Missing candidate objects or extra dirty projects stop preparation.

Derive expected kernel major/patch/sublevel/extraversion and KMI suffix from the files at the frozen kernel SHA, append the device metadata's real SHA/build label, and cross-check the resulting built `kernel.release`, banner and image against that expectation. Do not derive expected values from the untrusted artifact being tested or replace one hard-coded SHA with another. Test this preparation/expectation code before any build starts, with the existing legacy profiles preserved. Keep the builder/host/fixed timestamp identity fields as previously requested; truthful version/source SHA changes are not a new identity-spoofing extension.

The candidate and baseline commits must remain in the local audit object store with a source bundle and exact refs. No pre-validation push to the owner kernel branch is necessary. A local frozen manifest is an experimental record until publication; after phone validation and owner-authorized push/tag, verify that the unchanged final commits can be fetched from the intended remotes and only then call the distributed manifest independently retrievable. Publication is not a prerequisite for building a locally pinned candidate.

### K3. Kernel acceptance gates

Before packaging, require a clean provenance record, reviewed config delta, expected generated release, unchanged DTB/DTBO/firmware and vendor module hashes, and build success through the full pipeline. Never run `m <module>` in the tree that will be packaged.

Run all existing historical and image gates, install integrity, AVB chain/layout checks, exported-symbol and module-CRC checks across every packaged copy. Baseline is 888 packaged module instances, zero CRC mismatches and the explicitly documented unresolved `mtk_drm_gateic_set_backlight`. Explain any count change instead of silently updating a number. No new unresolved symbol or mismatch is accepted. Audit the existing `module_layout` exclusion and baseline unresolved exception; do not claim they are proved safe merely because the checker excludes them, and do not add further exclusions to pass the new kernel.

Only intentional metadata/source expectations may change, with before/after evidence and focused verifier tests if code changes. A broken checker is distinguished from a broken artifact; no bypass as a kernel-port technique.

Before a candidate flash, establish what unrooted dumpstate can expose on 20261108. Collect a private ADB bugreport soon after a normal boot separately started/authorized by the owner, before the kernel ring buffer wraps; an aged capture cannot settle capability. Inspect kernel log and pstore/last-kmsg sections and any pKVM initialization/load signals. Define the baseline-observable contract explicitly: for example protected-mode initialization, the four module-load signals, accessible panic indicators, and protected-video/camera/display functionality. Per-module "EL2 initialized" messages may not exist; do not invent a requirement for messages the baseline never emits. Trim/redact only relevant excerpts; raw bugreports stay local/private and are not sent to the model.

The image is only "image-checked" until phone validation. After a separately authorized no-wipe slot-b flash and the section 9 preflight, require successful boot, matching release/config, expected services/module sets, all four pKVM host modules and the same observable protected-mode contract, captured at a comparable early-boot point. Also require charging, suspend/resume, AOD/Goodix, refresh switching, touch, photo/video, audio/calls, modem/eSIM, data, Wi-Fi/Bluetooth/GNSS, thermal readings and normal app checks. Accessible panic logs must not show a new failure; inaccessible logs are unknown, never a clean result. If the baseline exposes no per-module EL2 evidence, present the actual positive signals, static ABI analysis and residual uncertainty for an explicit owner go/no-go rather than block forever waiting for nonexistent strings. Do not weaken a signal the baseline actually supplies. A proven EL2 ABI mismatch still blocks regardless of owner workload results. No root is needed or assumed. Early recovery cannot depend on ADB.

Observe overnight/normal-use stability before using this as the control for performance experiments. Any reproducible new functional failure, new missing required module, kernel restart/panic or unexplained material drain blocks promotion and triggers source/artifact investigation.

## 5. Stage D — small device-tree corrections

Make these separate commits with explicit purpose. They may be packaged after the kernel-only candidate has been validated; combining them before that would weaken attribution.

### D1. Renderer configuration

In `configs/props/vendor.prop`, change `debug.renderengine.backend=skiagl` to `skiaglthreaded`. Keep GLES/Ganesh and the Mali blob stack. The frozen framework already always creates a threaded renderer, so this is supported-configuration cleanup, not a new threading optimization. Verify the selected backend, RenderEngine thread, normal composition, blur, rotation, screenshot/screen recording, HDR and protected video. If final upstream source changes the selection semantics, re-review this small change before applying it.

### D2. Tracing declaration and documentation

First audit the exact boot-time property readers/writers, init triggers and tracing-service startup to explain why runtime is zero despite the conflicting source declaration. Then change the vendor atrace value `0x4040e` to explicit `0`, matching system.prop and measured runtime, if it is only declaration cleanup. Do not claim a simple load-order explanation until verified. If a hidden dependency is found, keep the current behavior and document it. Do not remove atrace support or change GED/FPSGO hooks. No current overhead reduction is promised. Verify default flags zero and tracefs off after a normal boot; an explicitly started developer trace may legitimately enable them.

Update the device README's build section from the old WitAqua/misakazip recipe to the actual Evolution X owner manifest/pipeline, default branches, source-built kernel with stock vendor modules, patches and private-blob extraction requirements. Retain useful hardware/extraction material. Link to the build repository as the canonical process. Do not duplicate stale verifier counts or expose private URLs/keys.

## 6. Stage S — high-refresh scheduling candidate

This is the strongest device-specific performance configuration mismatch, but its benefit is still an experiment. The serial default-branch sequence is K, then K+D, then K+D+S. **Use the validated K+D build as the control for S**, changing only timing properties plus unavoidable date/build labeling. Do not compare K+D+S directly to K and attribute all differences to timing. Keep 60 Hz base durations unchanged initially as a conservative experimental choice, not as a claim that they are the vendor's intended 60 Hz values.

For the first 120 Hz candidate, add these supported properties in `configs/props/odm.prop` next to the existing vendor-derived display table, with a comment explaining the exact frozen framework's suffix convention:

```properties
debug.sf.early.app.duration.120=11600000
debug.sf.early.sf.duration.120=10300000
debug.sf.earlyGl.app.duration.120=11600000
debug.sf.earlyGl.sf.duration.120=10300000
debug.sf.late.app.duration.120=11600000
debug.sf.late.sf.duration.120=10300000
```

These values are supported by both the existing high_fps table and `vendor.prop:846-878`'s MediaTek `vendor.debug.sf.dynamic_duration.*` table, whose switch is 1. The latter supplies 120 Hz app/SF 11.6/10.3 ms, 90 Hz 13.6/13.1 ms and 60 Hz 16.6/13.6 ms for early/earlyGl/late. They are starting candidates, not measured optima. AOSP's reader does not consume those vendor keys directly. Keep all original vendor-named keys until a consumer audit proves no proprietary component needs them; adding numeric keys need not delete them. Confirm property ownership/duplicate resolution and integer rate lookup from the implementation-time framework. No framework patch is planned.

After 120 Hz passes, test 144 Hz separately using app 10,500,000 ns and SF 8,900,000 ns for each of early/earlyGl/late, with suffix `.144`. The hardware exposes this rate, but the owner currently selects a 120 Hz maximum. Do not change the owner's setting merely to make a test pass. An explicitly agreed manual 144 Hz session is needed before shipping that table. Keep 90 Hz on baseline initially; the vendor mapping is known (13.6/13.1 ms), but unvalidated on the current phone. A `.90` table needs its own trial. Evaluate the known vendor 60 Hz table only as a later independent experiment; the initial 60 Hz control remains unchanged.

### S acceptance

Confirm live SF dumps actually select the new durations at the intended rate and retain the baseline at 60 Hz. Capture actual refresh rate throughout; a configured peak is not proof of active mode. Recheck idle transitions, scrolling, AOD/wake/Goodix, screen-off animations, demanding UI, camera viewfinder/video, blur, rotation, recording, HDR and protected video.

Use reproducible scripted scrolling only with authorization for input injection; otherwise record a matched manual protocol and its greater variance. Include Settings plus at least one heavier repeatable UI/composition workload, without clearing app data. Prefer separately authorized control-candidate-control flashes: the third block reuses the **identical validated K+D ZIP and SHA256**, not a newly rebuilt/reverted approximation. The artifact rollback-equality gate and recovery preflight apply to every transition and reduce known risks without guaranteeing all TEE state. After every flash, wait until boot jobs, app compilation and thermal conditions have settled, using the same recorded readiness criteria before measurement.

Plan an initial 200,000 new frames per arm per low-jank workload, with budget for 400,000 or more when clustering/variance requires it; 80,000 is insufficient to establish the tight bound near the observed 0.079% rate. Measure repeated blocks with comparable charge/temperature/cooldown and unchanged statistics epochs. Use trial/block-level uncertainty rather than assuming every adjacent frame is independent. If the required precision is unaffordable, leave the timing change unpromoted.

The named benefit metric is p50/p95 **app-frame wake/start to actual presentation** for matched frame identifiers in a bounded unrooted Perfetto/FrameTimeline plus scheduler capture, if those events are available. This is a scheduling-latency proxy, not touch-to-photon. Require a repeatable p50 reduction of at least 5% and 1 ms, with confidence excluding no improvement across matched trials, while p95 and protected workloads do not regress. If the trace cannot support that correlation, agree a specific alternative objective metric before S starts; do not select whichever metric improves after seeing results.

Use modern jank rates, FrameTimeline missed deadlines and p95/p99 durations as non-regression measures. The provisional limit is a one-sided 95% upper confidence bound for candidate-minus-control modern jank of at most the larger of 0.02 percentage points or 20% of the matched control rate, and no repeatable greater-than-5% p95 frame-time regression. Report uncertainty and correlated-block effects; collect more evidence if needed. Any functional/visible regression rejects the candidate. No touch-to-photon claim comes from subtracting duration sums. **Stage S does not ship solely as "configuration alignment" when no objective benefit is demonstrated**; keep baseline timings in that case. D1/D2 remain separately described configuration/documentation cleanup.

## 7. Deferred work with explicit admission gates

| Item | Investigation and exact condition before a change |
|---|---|
| AutoFDO | After the updated kernel is stable, inspect `scripts/Makefile.autofdo`, compiler version/support, target profile provenance and config dependencies. Candidate surfaces: device external kernel config and `TARGET_KERNEL_ADDITIONAL_FLAGS` with a correctly expanded `CLANG_AUTOFDO_PROFILE` path. Require isolated output, confirmation that the profile is actually consumed, full ABI/image gates and repeatable device benefit. Do not quote Pixel gains as MT6991 gains. No on-phone ETM/kernel profiling or root requirement is imposed. |
| LTO | Keep off in the maintenance update. Evaluate separately only if justified by measured needs and vendor ABI/CFI/toolchain compatibility. AutoFDO must not silently enable or change LTO/CFI. One compiler-policy change per attributable candidate. |
| MGLRU | Keep the existing `write .../lru_gen/enabled n`. First identify which MT6991 reclaim/unfairmem/scene_swappiness components and lmkd/task-profile policies are active. Admission requires a demonstrated app-retention/reclaim problem, compatibility review and a build-time init change with a few days of matched usage per side. Accessible vmstat and app-exit evidence can help; kernel oom counts alone do not count lmkd kills. No privileged sysfs/device_config toggles are assumed available. |
| Architecture | Keep `armv8-a`/generic and current ART runtime variant initially. Inspect actual compiler/Soong and ART consumers, supported variants and binary feature requirements. A future `armv8-2a`/appropriate scheduling target needs a separately measured full rebuild and app/native compatibility checks; `cortex-a76` is not automatically the right tuning target for X925/X4/A720. |
| Module pruning | First explain the two missing baseline entries, audit dependencies/aliases, VINTF and possible userspace consumers. Evaluate `kheaders` first as a possible bounded memory/attack-surface cleanup, not a broad guest/network/NFC removal list. If approved, remove the intended package/load producer consistently and update expected inventory with evidence. Never unload modules on the owner's unrooted phone. Zero refcount alone does not admit removal. |
| Kernel config drift | Build a named upstream/local config ledger. Preserve required stock contracts, TLS and actual ashmem until consumer and ABI analysis proves a particular change. Do not enable CONNECTOR/WRAPFD/SAFESETID/HID/PCI options or drop TLS solely to match another defconfig. Missing config options are not automatically missing phone features. |
| Thermal / power HAL migration | Retain current stock HALs, firmware and policies. Fresh thermal readings already exist. A source-HAL replacement needs a demonstrated defect and coordinated providers/blobs/VINTF/policy/ABI review. No thermal limit, powerhint, FPSGO/GED, undervolt or overclock tuning is planned. |
| AVB / verity | No enforcement-flag changes in this series. Separately compare artifact vbmeta flags, fstab and current signing/boot flow before proposing any enforcement change. Runtime green/locked/enforcing props cannot settle cryptographic state. Do not relock the bootloader or probe writes. |
| KeyMint / rollback / SPL | Add a mandatory mechanical artifact gate: every controlled candidate must exactly match baseline AVB rollback indices/locations in all vbmeta descriptors, boot/init_boot/vendor_boot header os_version and os_patch_level where present, and actual/reported system/vendor patch levels. Equality applies to these rollback/security fields, not every identity property: validate build dates, incremental/build labels and real kernel version/source against their expected per-build values instead. Any unexpected security/rollback difference blocks the flash; warnings are insufficient. No reset/lowering of indices, TEE-state inference from properties, key-generation, wipe or downgrade experiment. A legitimate security-policy change needs its own reviewed series and fallback assessment. |
| odex / dex2oat | Confirm `ro.cp_system_other_odex` consumer and whether system_other is produced; inspect task profiles and ART scheduling, not just missing cpu-set properties. Change the property or background affinity only for a concrete packaging/performance need with idle/thermal measurements. |
| Broader missing features / MT6991 patches | Keep an evidence ledger for future upstream fixes, tied to this handset's exact interfaces and firmware. No new missing feature was demonstrated by the current check. Do not import foreign MTP, Bluetooth, camera, display or policy changes merely because they share MT6991. |

## 8. Build, provenance and release sequence

1. Finish independent Opus review, merge findings into a disposition, revise this plan and identify any blockers. Obtain execution authorization for the concrete reviewed scope; this document itself is not a build command.
2. Mount the existing disk using the established Windows script if needed, maintain WSL keepalive, verify no owned build/extraction is active, inventory dirty state, save exact heads/frozen baseline and check host/ext4 budgets. Do not alter the existing untracked design document.
3. Freeze all non-kernel projects at the control snapshot for the kernel experiment. Record the control-freeze UTC timestamp when the campaign's manifest/heads are first sealed before the K build; the seven-calendar-day campaign clock starts there, not at the last candidate build. Do not combine a general sync with the first port. Reassess earlier if an applicable urgent security fix appears. If the window expires, create/revalidate a refreshed control as its own stage, including SPL/rollback review, before restarting comparisons. Keep signing material in place and offline.
4. Make reviewed kernel/device metadata commits on default branches and preserve local audit objects/bundles. Record final heads, patch-bundle hashes and tooling revision. Do not push an untested kernel merely to make repo sync find it. Fetch the exact candidate from the local audit repository using the reviewed frozen-candidate path in K2. Push/tag only after phone validation and owner authorization; distinguish local experimental manifests from publicly retrievable release records.
5. Implement/test the specified pipeline changes first, then use its reviewed frozen-candidate entry point plus existing patch/label/freeze/readiness/controller/start/promote primitives, with full installclean. Existing upstream/live-head drift protections remain in effect for ordinary builds. Do not call upstream/sync after installing the local candidate and pretend its readiness pin survives.
6. Existing readiness requires at least 45 GiB host, 10 GiB source and 45 GiB output at start; preserve current supervisor/verifier thresholds and their checks. Space budgets come from the execution-time pipeline, not this document if they later change. One build at a time; use attempt-owned paths and normal watchdogs.
7. Generate normal ZIP, no-wipe flash helpers, SHA256SUMS, source/config/ABI comparison, RESULTS and VERIFIED records. Require all image gates before delivery. No partial-module staging or stale ZIP reuse. Document each real build using its actual date name.
8. Before any flash, present exact changes, static results, rollback implications and runtime tests to the owner. Flash only when separately asked, using the existing slot-b no-wipe helper (`--skip-reboot`, never `-w`) with identity/slot/hash checks. Follow the helper's reboot handoff; do not independently issue an unrequested reboot.
9. Validate K, then K+D; use the identical validated K+D ZIP as S's control and any third control block. Every experiment has immutable source records and full image gates, without per-build branches. Source repositories advance only their default branches; the build-tree kernel consumes exact detached candidate SHAs. Rejected unpublished kernel candidates stay recorded in the audit clone and are abandoned in the build checkout by clean detached checkout of the preserved baseline. Published device experiments use explicit revert commits where needed; historical tags and reverts are expected evidence. No destructive reset is used.
10. Only after comparisons succeed, produce the final combined release from the exact validated commits without upstream sync, with a newly generated manifest of those same heads and full gates; repeat integrated runtime regressions. A later ROM sync is a separate stage and restarts any comparisons affected by its changes. Rejected/deferred content stays out.

## 9. Recovery and data preservation

Keep the exact 20261108 ZIP, hashes and flash helpers, plus the last validated candidate, available. Retain apps, data, Wallet/card state, firmware, signing keys and the current unrooted user route. A prior ZIP is a recovery resource, not a guarantee that rollback remains allowed: compare actual emitted rollback indices and patch fields before any newer flash. If the chosen kernel target or legitimate security update requires advancing irreversible state, stop and explain how that affects the fallback before asking for that flash. Do not fake lower indices or patch metadata to preserve a fallback.

### First-kernel-trial slot and early-failure preflight

The candidate replaces currently running slot b. `docs/history.md` records slot a firmware as OS3.0.302 versus b's OS3.0.335; slot a's current system contents and bootability are not established. Automatic fallback to that slot must not be treated as recovery.

During the separately authorized pre-flash fastboot session, record current slot and every available successful/unbootable/retry-count field for both slots, with exact output. Establish slot-a system/firmware provenance from backups/records or read-only inspection if possible. Unsupported getvars are unknown, not passes. Do not boot slot a just to identify it. Expect this gate to need an owner decision: fallback may be enabled and stock fastboot may lack a mark-unbootable command. Before the first kernel trial, require an explicitly agreed concrete fallback-prevention/recovery strategy, potentially rehearsed physical-key interception with the owner accepting its limitations. If no acceptable strategy exists, the flash stays blocked. No unrequested slot-state write, slot-a flash, firmware sync, mark-unbootable operation or relock is implied.

Prepare the owner before the authorized trial: keep USB connected and the verified recovery ZIP/helper ready; use Power + Volume Down to enter bootloader fastboot (Xiaomi's documented combination). At the first spontaneous reboot/loop, enter fastboot immediately rather than consuming repeated boot attempts. For a single uninterrupted boot with no ADB, use a conservative maximum of 90 seconds to regain fastboot; the prior normal boot was about 36 seconds. A reboot loop is not granted 90 seconds of retries. Verify the physical-key procedure is understood before the flash; software recovery does not assume early ADB.

In fastboot, recheck identity and slot state, explicitly select the approved slot-b recovery target under the recovery authorization if it changed, and use the existing 20261108 no-wipe helper with hashes and rollback compatibility rechecked. Do not flash the fallback ZIP to an unexpectedly selected slot. Leave the reboot to the same authorized helper/handoff procedure. If recovery offers "Factory data reset", do not accept it. If fastboot cannot be reached, stop and seek device-specific recovery assistance; do not improvise an erase.

Physical-key reference: [Xiaomi fastboot FAQ](https://www.mi.com/uk/support/faq/details/KA-550626/). The timing cutoff above is a conservative procedure, not a hardware guarantee or a substitute for the preflight fallback gate.

If a candidate regresses, preserve diagnostic evidence and identify the smallest source revert. Restore only through the already established no-wipe path and the owner's explicit device-operation authorization, after checking compatibility of the recovery artifact. No factory reset, keybox change, root installation or app-data clear is part of this plan.

## 10. Completion criteria and current open gates

The strategy received Opus's conditional approval, and this version incorporates its stated textual conditions. Implementation starts with the authorized K0 audit and preparation/verifier work; no candidate build is ready until those code changes are tested and its required source/KMI/type/protected-export ledgers exist. The first flash separately requires the baseline-observable protected-mode evidence contract, mechanical rollback equality, the slot-fallback preflight and owner go/no-go. The full WSL framework/vendor tree and candidate artifacts have not been examined during this planning pass; those remain checks, not assumed passes.

A completed change series has: an audited fixed kernel target; preserved stock vendor contracts; exact final owner heads; proven numeric refresh-rate property selection; per-change and integrated regression results; honest performance measurements; no unexplained ABI/install failures; frozen manifests and date-named records; and a clear list of rejected/deferred items. An image-only result is never called boot-tested.

Reference for the pinned release: [Google android15-6.6 release builds](https://source.android.com/docs/core/architecture/kernel/gki-android15-6_6-release-builds). The live official tag resolution is recorded separately with this plan.
