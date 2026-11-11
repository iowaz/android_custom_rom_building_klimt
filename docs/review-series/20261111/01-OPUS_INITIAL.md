The kernel-only 20261111 candidate is approved for the owner-gated runtime steps. The pipeline needs revision before the D and S builds can be admitted. I found no correctness defect in the candidate itself. I couldn't save a report file (Write and plan-file tools are disabled in this session), so the full review is below.

## What I checked myself (all reads through WSL; nothing built, flashed or published)
- **Kernel delta:** commit `08c56166` merges the old owner kernel `f6a5b29` with official `1c39bb5`, which is LTS 6.6.144. The new delta (`1c39bb5..08c56166`) and the old one (`c3dd858..f6a5b29`) produce the same `git patch-id` (`1e588c1f…`) and touch the same 4 files. `c3dd858` is an ancestor of `1c39bb5`, so no existing fixes are dropped.
- **Snapshot:** 20261111 differs from 20261108 only in the kernel and device revisions. Its SHA256 matches the frozen copy used by the build.
- **Device changes:** the build checkout changes only the metadata SHA/label and the BoardConfig comment. The separate preview series holds exactly D1, the README and the six `.120` keys, and none of these are in the K build.
- **SurfaceFlinger timing keys:** the framework reads `<key>.<rounded Hz>` (`VsyncConfiguration.cpp:290-320`, `Fps::getIntValue` uses `std::round`), so the `.120` keys will be picked up.
- **Renderer:** `skiagl` asks for a non-threaded renderer, but RenderEngine forces threaded anyway (`SurfaceFlinger.cpp:908-913`, `RenderEngine.cpp:65-70`). D1 is cleanup only.
- **Kernel config:** the release config differs from baseline only by `HAVE_BUILDTIME_MCOUNT_SORT=y`. That setting does nothing here because `FUNCTION_TRACER` is off. Rust stays disabled.
- **ABI evidence:** the old and new STG type graphs hash identically, covering all 9,273 retained symbols. The pKVM layout output is byte-identical. The protected-export policy files and generated headers are unchanged.
- **Rollback/security fields:**
  - AVB chains are the same as the control: boot at location 3, vbmeta_system at 2, vbmeta_vendor at 4.
  - The rollback indices and the v4 boot/init_boot OS fields also match.
  - Reported patch levels (2026-10-05) and the actual source patch level (2026-11-01) are the same in candidate and control.
- **Tests:** `tests.py:755-757` imports the three new test files, so all 89 tests really run.

## Findings, by priority

**M1 — The D and S builds can't currently pass readiness.**
- `kernel_contract.BASELINE` is hard-coded to `f6a5b29`, so `ready.py` treats any later build using kernel `08c56166` as a changed kernel.
- `candidate_gates.validate_audit` (line 28) then requires the kernel audit to be bound to that build's own control snapshot. The only existing audit is bound to 20261108 (`49fd…`).
- So the K+D and K+D+S builds will be blocked unless a full new audit is produced, and there is no tool or test for carrying forward an unchanged, already-audited kernel. The remote `17.0` stays at `f6a5` until publication, so these builds must also go through `frozen_candidate`.
- **Fix:** add an explicit "kernel unchanged vs control" rule that reuses the control's verified audit for the same SHA through a hash-bound record, with tests. Otherwise, document a full re-audit for each stage and budget for it.

**M2 — The release audit points at files that will change or be deleted.**
- `kernel-audit-release/kernel-audit.json` binds the generated protection headers in the live build output folder (`/mnt/wsl/build/evox-out/...`), which the next build overwrites.
- Its type and config proofs sit in `/mnt/wsl/build/klimt-kernel-audit-20261111/`, which the plan allows to be deleted after publication.
- `diagnostics/builds/20261111/kernel-audit/` holds only the pre-build audit, not `kernel-audit-release`.
- Any later recheck, promotion or carry-forward (see M1) will then fail revalidation.
- **Fix:** copy the headers, release `.config`, `Module.symvers` and both `.stg` files into immutable diagnostics, and never reference the output folder in future audits.

**M3 — Nothing mechanically ties the packaged image to the analyzed kernel files.**
- `musthold.sh:38` checks module CRCs against `Module.symvers` from the build output folder, and `verify.py` reads `.config` from the same place.
- The release audit uses ELFs copied from that folder. Only the banner string comes from the packaged `boot.img`.
- **Fix:** compare GNU build-ids between the release `vmlinux` and the unpacked boot kernel, and between the 96 debug `.ko` files and the packaged stripped ones. It's cheap, and it matters now that the kernel actually changed.

**L1 — Two kernel gates still trust a pass flag.** The ancestry and local-delta gates don't parse `kernel-refs.json`: the target being `1c39bb5`, the parents, the 4-path set and `ancestor: true` go unchecked. My manual checks above pass, so this is an enforcement gap only.

**L2 — The tracing (D2) decision is mislabelled.** `TRACING_DECLARATION.md` calls keeping `0x4040e` "the plan's conditional retain-and-document path". The plan only allows that when a real dependency is found, and here the audit of what resets the value is unfinished. It should be recorded as an open item with its runtime test. I confirmed load order alone doesn't explain the zero: all `debug.*` properties share one label, and the vendor `debug.sf` values do apply.

**L3 — `RUNTIME_GATES.md` leaves out some of the plan's kernel runtime checks:**
- exact `uname -r` = `6.6.144-android15-8-g08c56166f188-ab20261111` and a config match;
- the loaded-module set compared with the 574-module baseline, including the two modules known to be absent;
- refresh-rate switching and audio;
- suspend/resume as its own named check;
- the owner's go/no-go on remaining EL2 uncertainty, and the rule that a proven EL2 mismatch blocks regardless.

**L4 — The seven-day freeze closes on 2026-11-18 at 15:04 UTC.**
- `freeze_deadline` runs inside verification and promotion too, not only at build launch.
- After that time, even a verifier-only recheck of an existing artifact fails, and so does the final combined release.
- The K runtime checks, the K+D build and the S measurements (200k frames per arm, with control–candidate–control flashes) are unlikely to fit in that window. The owner should know now, or enforcement should apply only at launch.

**L5 — The delivery can be flashed before its gates are met.** `output-zips/20261111` already has working flash helpers, and the README lists 20261111 as "Latest delivery". The required early-boot bugreport and the decision on slot a as a fallback are still pending. A "not yet admitted" marker until the owner's go/no-go would help.

**L6 — Gaps in tests and cleanup.** The full `frozen_candidate.run` flow and the `prepare.py` candidate-step gating have no tests; only `validate_spec` is tested. A leftover temporary pack file, `tmp_pack_CWva7U`, is still in the audit store on C:. Its size should be checked against the C: space budget.

## Recommended order
1. Fix M1 with tests, preserve the M2 evidence and add the M3 build-id check as recipe commits, then rerun `tests.py` in WSL.
2. Correct `RUNTIME_GATES.md` (L3) and the D2 wording (L2), and raise the freeze-window deadline (L4) with the owner.
3. Leave the K candidate as it is. All phone steps still need the owner's separate authorization.