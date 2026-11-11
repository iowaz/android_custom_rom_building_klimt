# Independent implementation review — Sol

Reviewed on 2026-11-11 against PLAN.md v3 and recipe HEAD `fd4bfccab487cf038d587e6de31b2d16dd69c20a`, comparing recipe base `f459fcda77745f7ed103f0b45278b35d3509a146` with that HEAD.

## Verdict

**REVISE: one P2 pipeline completeness finding.** No incorrect current kernel payload or configuration was demonstrated. In fact, this review independently established that the existing verified boot payload equals the preserved audited release ELF's generated Image and contains the audited configuration. The missing part is making that relationship a mandatory, recorded pipeline gate rather than a one-off review observation.

The narrow K source implementation otherwise matches the plan. Queued D/S changes are excluded from the current frozen graph. The current delivery remains **image-checked only**. This verdict does not authorize flashing, phone operations or publication. Runtime prerequisites and the serial K -> K+D -> K+D+S admission remain outstanding.

## Finding

### P2 — Bind the compiled-config/ABI checks to the packaged kernel payload

**Location:** `repositories/android_custom_rom_building_klimt/build-setup/evox/pipeline/verify.py:184-188`, especially line 188. Related implementation: `candidate_gates.py:59-64`, `machine_gates.py:94-97`.

The new verification check calls `validate_compiled_config()` on the mutable build-output `obj/KERNEL_OBJ/.config`. The audit validator separately checks the preserved audit `.config` and debug ELFs. Neither check proves that the kernel bytes in the archive's `boot.img` came from those audited inputs. The existing legacy kernel checks read the packaged banner (`legacy/fixcheck20.sh:71-80`), and the packaged module CRC check uses the output-tree `Module.symvers` (`legacy/musthold.sh:37-38`); neither supplies this missing payload-to-ELF/config equality.

A stale same-label kernel payload, or a packaging step selecting another same-banner Image, can therefore preserve the expected banner, module contracts, SPL and rollback metadata while the new config/ABI gates continue validating the good output-tree inputs. The successful build/ZIP hash checks prove which archive was produced, but do not connect its kernel payload to the ELF whose types were audited. The release `analysis-invocation.json:21` records the archive digest; it is a provenance assertion rather than a comparison of the packaged payload with the audited ELF. This leaves a gap in PLAN.md K1/K2/K3's generated-config and compiled-contract admission requirements.

**Requested change:** fail verification if the kernel payload in the verified archive differs from the audited release kernel, and compare its embedded IKCONFIG with the reviewed configuration, allowing only the explicitly permitted label normalization. Record the archive/boot/payload/audited-ELF/config digests and comparison result in hash-bound RESULTS evidence, and revalidate that evidence at promotion. Add a focused negative regression in which the output `.config` remains correct but the packaged payload/config is stale or changed. Preserve all existing checks.

**Current artifact and feasible correction:** this finding does not demonstrate an incorrect current ZIP. The existing outputs support the missing comparison without a build or a fresh image extraction:

- Preserved release `.config` has `CONFIG_IKCONFIG=y` and `CONFIG_IKCONFIG_PROC=y` (lines 162-163).
- The exact kernel rule is `llvm-objcopy -O binary -R .note -R .note.gnu.build-id -R .comment -S vmlinux Image` (`kernel/xiaomi/klimt/arch/arm64/boot/Makefile:17-22` and existing output `arch/arm64/boot/.Image.cmd`).
- Using `/mnt/wsl/evox/src/prebuilts/clang/host/linux-x86/clang-r596125/bin/llvm-objcopy` with flags `-O binary -R .note -R .note.gnu.build-id -R .comment -S`, input below and output `-` (captured entirely in memory), the transformation from `/mnt/wsl/build/klimt-kernel-audit-20261111/release/vmlinux` produced exactly the same 36,866,560 bytes as the current output Image and the decompressed, already-unpacked verifier kernel. All three have SHA256 `bb5ade05551cf173f3202f4d4d0b9272eb7b785a08609b2010d482d39eefb53d`.
- The existing verifier path is `/mnt/wsl/build/compare/20261111/20261111-attempt02/rechecks/recheck01/tmp/evx20_boot/kernel`. Its compressed bytes equal the kernel region read directly from the existing v4 `img/boot.img`: offset 4096, kernel_size 17,355,599. That boot image's digest equals the recheck image inventory: `83dc00ada3174440c3551e8045259a30683f08e7b71b0a21df4c32c3126b70fc`.
- Decompressing the existing payload in memory and reading its IKCFG_ST gzip member yielded a config byte-identical to preserved release `.config`. Its normalized SHA256 is `303df908798c01e5836509a9d282a6f4c3cbbd921cdb5017c22afc1d3d604444`, exactly the release audit expectation.

These observations close the uncertainty for the inspected current kernel bytes; they do not repair the pipeline for future verification or promotion. A verifier-only correction/recheck can persist and enforce this relationship on the unchanged archive.

## Source and scope checks

1. Inspected actual WSL source through shell only. Kernel HEAD is detached at `08c56166f1883020396e8e95570671407f00ba04`, with the exact old-owner and official-target parents specified by the plan. Its worktree is clean.
2. Mechanically compared the owner delta `c3dd858dcf5843346c0a5b9c031ae0e9e0664277..f6a5b29f9fe59e4849680d50232f8b5758aa8c11` with the target-to-candidate delta. Both contain exactly `android/abi_gki_aarch64_klimt`, `android/klimt_gki_modules`, `arch/arm64/configs/klimt_defconfig`, and `include/linux/compiler_types.h`; every added/removed delta line is preserved exactly. The pKVM module-ops header is unchanged between owner control and candidate.
3. Compared frozen 20261108 and 20261111 manifests. Their only changed projects are kernel `f6a5b29... -> 08c5616...` and device `dd6cb60... -> 1b1b1cc...`; all other project pins are unchanged. Inspected actual device diff: only source-description comments and truthful SHA/date/kernel label metadata changed in K.
4. Inspected the separate device preview changes: supported `skiaglthreaded`, updated Evolution X owner build instructions, and exactly six numeric `.120` properties. Existing vendor-named keys and the 60/90/144 tables remain intact. These are queued, absent from the K snapshot, and cannot be treated as runtime-admitted changes.
5. Tracing retain-and-document is honestly conditional: `implementation/TRACING_DECLARATION.md` does not invent an unconditional property reset or claim a measured improvement. The responsible boot writer remains unknown. No tracing change was bundled.
6. Reviewed preparation, readiness, controller, verifier, promotion, kernel identity, rollback, ABI and machine-gate changes against the original recipe revision. Normal live-head protections remain present; the explicit candidate route checks the exact two-project allowlist, unchanged ROM patch bundle, full effective control heads and detached kernel. Reviewed-tooling and verifier-only audit replacement preserve source/control bindings and prohibit launching a build from effective verifier-only readiness.
7. Reviewed the pKVM semantic ledger alongside `kernel-audit/pkvm-changes.patch` and `gitiles-arm64-headers.diff`. CPU initialization, stack ownership, LR bounds, IOMMU identity-domain rejection and guest-memory changes are explicitly distinguished from unchanged module interface signatures. Runtime CPU/resume/protected-camera/video behavior remains unresolved rather than being inferred from CRC equality.

## Independently rechecked evidence

These checks were read-only and did not rerun image extraction or compilation.

- Called the implemented `candidate_gates.validate_audit()` against the actual release audit and frozen heads. Every listed proof digest revalidated, all nested machine gates passed, retained-symbol coverage was checked from the frozen whitelist, and the actual old/new STG comparison returned zero. This covers 9,273 retained symbols, including the GKI module providers and explicit untyped assembly declaration/provider evidence.
- The release audit's pKVM 688-byte ops layout, nine callback argument layouts, 517 unique vendor-module contract, module_layout equality, generated protection headers and symbol-membership checks all passed their implemented nested validation. No new exception was introduced for this candidate.
- Called `candidate_gates.validate_ready()` on the actual attempt02/recheck01 effective readiness. Its control-freeze anchor is `2026-11-11T15:04:25Z`; the deadline was valid at review. Baseline archive hash, source/control bindings, audit proof hashes and actual source SPL passed.
- Recomputed the frozen-source kernel expectation and matched effective readiness: `6.6.144-android15-8-g08c56166f188-ab20261111`, Android15-6.6/KMI generation 8, fixed owner metadata identity.
- Rehashed the delivered archive `output-zips/20261111/lineage_klimt-20261111-img.zip`: SHA256 `035de568db84563c79442b70d119fd97dcaa1e4b7e00e334faa11417e00df544`, matching recheck RESULTS and PROMOTED. Rehashed the baseline archive through readiness validation.
- Revalidated both rollback/security report digests and compared candidate metadata with the baseline security object: equality passed. The actual-source SPL remains distinct from reported SPL.
- Read the saved successful full image records: 195 historical checks; metadata result has 112 passing assertions; all seven supplemental coverage records have exit zero; runtime validation is explicitly false. The image report retains 888 packaged module instances, zero CRC mismatches and only the baseline unresolved `mtk_drm_gateic_set_backlight`.
- Read the recorded 89-test result and inspected the associated new/changed test code. Did not rerun the test suite because the review permits only the requested report write and the suite creates test outputs.
- Recipe HEAD matched the requested revision; its only visible untracked entry was the preserved unrelated `docs/designs/`.

Primary evidence: `kernel-audit-release/kernel-audit.json`, `abi-RESULT.json`, `analysis-config-reviewed.json`, `analysis-invocation.json`, `preserved-release-inputs.json`; `implementation/VERIFIER_RECHECK.md`, `PIPELINE_TESTS.json`, `source-bundles.json`, `device-static-checks.json`; `diagnostics/builds/20261111/reports/20261111-attempt02/rechecks/recheck01/{RESULTS.json,metadata26.json,image-files.json,rollback-security-candidate.json,rollback-security-equality.json}`; and `diagnostics/builds/20261111/PROMOTED.json`.

## Remaining admission boundaries

The complete implementation is not a completed runtime change series. Before a first K trial, retain the early baseline unrooted observation contract, concrete slot-a fallback/interception decision, recovery artifact/hash/rollback check and separate owner flash authorization. After K boots, hardware, pKVM-observable behavior and overnight/normal-use checks remain required. D can follow only after K passes; S uses validated K+D as control, with the identical control ZIP for the third block and the plan's objective benefit/non-regression measurements. None of these are replaced by this review or by the positive payload comparison.

Only this review report was written. No source/tooling edits, build, image extraction, phone operation, key/raw-phone-log access, publication or subagent invocation was performed.

