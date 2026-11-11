# Independent implementation recheck — Sol

Reviewed 2026-11-11. Scope: recipe delta `fd4bfccab487cf038d587e6de31b2d16dd69c20a..66d3b07293ff56b35bc8ae33cb3c75b8e2620677`, review disposition, permanent proof corpus and attempt02/recheck02 evidence. The initial `SOL_IMPLEMENTATION_REVIEW.md` is preserved.

## Verdict

**APPROVE the corrected source/pipeline implementation and static K delivery. No remaining actionable findings in this focused rereview.**

The initial Sol P2 is resolved: packaged kernel/config equality with audited release inputs is now enforced, persisted and checked at promotion. I independently reran the read-only artifact comparison on the existing recheck02 extraction; its result matches the saved binding receipt field-for-field. All 96 packaged GKI modules also match their audited debug ELFs under the reviewed stripping/signature-envelope rules.

Approval is limited to implementation and static evidence. The candidate remains image-checked, unbooted and unvalidated at runtime. It does not admit a flash, publication, D/S packaging before preceding runtime gates, or performance claims.

## Disposition of the original finding

- `build-setup/evox/pipeline/kernel_artifact.py:24-64` reads the actual v4 boot payload, validates bounds/header layout and supported compression, compares complete raw Image bytes with the audited ELF conversion, and validates embedded IKCONFIG. This replaces the original output-tree-only `.config` check.
- `kernel_artifact.py:112-149` obtains the Image conversion rule from the frozen kernel commit, requires the reviewed flags, and uses the pinned `clang-r596125` objcopy/strip tools. Each packaged source-built GKI module is compared with its individually hash-bound audited ELF after debug stripping and structurally bounded removal of appended signature envelopes. A signature cryptographic-verification claim is correctly absent.
- `verify.py:188-213` runs the gate on the verified archive extraction and hashes `kernel-artifact-binding.json`, `image-files.json` and `filesystem-files.json` into RESULTS. The delivery copies those records. `promote.py:48-59` rechecks report/delivery hashes and invokes `kernel_artifact.validate_receipt()` (`kernel_artifact.py:152-174`) to enforce the archive, source, boot/config/audited ELF and packaged-module relationships.
- `verify.py:171-174`, `kernel_artifact.py:103-109` and `legacy/musthold.sh:38-40` now route packaged module CRC checks through the preserved, hash-validated release Module.symvers. They no longer depend on the mutable current KERNEL_OBJ table for a candidate.
- Inspected `test_kernel_artifact.py`: negative coverage includes changed same-banner payload bytes, embedded config drift, malformed/truncated boot headers, signature-envelope bounds and inconsistent promotion receipts. The prior failure mode is directly represented.

## Preservation and carry review

`preserve_kernel_audit.py:13-78` preserves the proof corpus by content digest, rewrites dereferenced nested input/declaration records and preserves historical argv. `machine_gates.py:51-75` now requires nested ELF/declaration dependencies to match bound path and digest, rather than accepting only digest membership. The preservation regression removes original test inputs and then reads preserved dependencies successfully. Actual packaged verification rejects top-level proof paths outside release diagnostics.

`kernel_carry.py:15-62` checks the exact verified parent audit, control manifest/archive, passing historical/supplemental coverage, contract/config equality and control artifact receipts. The construction path permits only the device project to differ from the control; recursive audit validation is depth-bounded in `candidate_gates.py:26-47`. It does not grant runtime acceptance. A new label still requires its own release ELF/artifact comparison: old Image bytes are not accepted as proof for a differently labeled image. `docs/kernel-candidate-evidence.md` states that sequence and its storage/build requirements clearly.

The added ancestry/local-delta machine checks constrain the reviewed fixed target and exact local path set (`machine_gates.py:34-44`); they supplement the retained manual source/semantic review. The additional frozen-candidate orchestration tests cover the normal fetch/detach/record flow, dry preflight, competing ownership and step gating.

## Independently checked evidence

Executed only read-only checks, using WSL shell and existing images/extractions:

1. Revalidated the final permanent audit referenced by recheck02 RESULTS. All top-level proof hashes, nested ELF/declaration paths and digests, complete retained-symbol coverage, actual STG comparison, source/config/CRC/pKVM/protection and lineage machine gates passed.
2. Called `kernel_artifact.validate()` directly against the permanent audited inputs and the existing recheck02 boot/system_dlkm extraction. Its complete return object equals saved `kernel-artifact-binding.json`. Then called `validate_receipt()` against recheck02 inventories successfully.
3. Exact raw Image digest is `bb5ade05551cf173f3202f4d4d0b9272eb7b785a08609b2010d482d39eefb53d`; normalized embedded config digest is `303df908798c01e5836509a9d282a6f4c3cbbd921cdb5017c22afc1d3d604444`; all 96 module comparisons passed. The receipt binds archive `035de568db84563c79442b70d119fd97dcaa1e4b7e00e334faa11417e00df544` and boot image `83dc00ada3174440c3551e8045259a30683f08e7b71b0a21df4c32c3126b70fc`.
4. Recursively revalidated the actual carry CLI output `diagnostics/builds/20261111/kernel-carry-smoke.json`, including its control archive hash and parent artifact receipt. This is a static contract check, not proof of runtime admission.
5. Rehashed all artifact and rollback evidence records in both recheck02 reports and the promoted delivery. Compared emitted rollback/security data with the sealed baseline: equality passed. The inherited campaign freeze deadline remains valid at review and was not reset.
6. Read recheck02 RESULTS: 195 historical checks and seven successful supplemental tracks. Metadata result records 112 passing assertions and `runtime_validated: false`. PROMOTED selects recheck02 and records runtime unvalidated.
7. Inspected the new/changed tests and saved `implementation/reviews/post-review-tests.log`: 108 tests, exit zero. Did not rerun the suite because the review permits only this report write and the suite creates test outputs.
8. Confirmed recipe HEAD `66d3b07293ff56b35bc8ae33cb3c75b8e2620677`; unrelated untracked `docs/designs/` remains present.

## Remaining gates

The updated runtime checklist and delivered `RUNTIME_PENDING.md` retain early baseline observability, exact uname/config checks where accessible without root, 574-loaded versus 888-packaged module distinction, known baseline absences, all four pKVM host modules, hardware/normal-use tests, explicit residual EL2 uncertainty and a hard block for proven incompatibility. Slot-a fallback/recovery and separate owner go/no-go remain prerequisites. Tracing cleanup is explicitly deferred. K then K+D then K+D+S remains serial, with S's validated K+D control and objective benefit/non-regression requirements unchanged. Campaign deadline remains 2026-11-18 15:04:25 UTC.

Only `SOL_IMPLEMENTATION_RECHECK.md` was written. No compilation, fresh image extraction, source/tooling mutation, phone operation, key/raw-phone-log access, publication or subagent invocation occurred.
