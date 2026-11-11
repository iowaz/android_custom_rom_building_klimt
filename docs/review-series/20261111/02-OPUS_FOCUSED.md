The K artifact is approved, now with stronger evidence. Before the first carried K+D build, revise two remaining pipeline gaps. All five of my earlier findings, M1–M3 and L1–L5, are resolved or accepted. The candidate's kernel and archive are unchanged, and I found no defect in them.

## Initial findings, rechecked
| Finding | Status | What I checked |
|---|---|---|
| **M3** packaged kernel not tied to audited ELFs | **Resolved** | `kernel_artifact.py:56-63,112-149` compares the boot.img kernel byte-for-byte with an Image rebuilt from the audited vmlinux, using the frozen Makefile rule (`:118-122`), and checks the embedded IKCONFIG against the audited config. The 96 system_dlkm GKI modules are compared after debug stripping and signature-envelope removal. `promote.py:48-59` re-checks the receipt. recheck02's binding shows Image `bb5ade05…` equal to the audited Image and config `303df908…`. The parsing of `musthold.sh:38` now uses the preserved, hash-bound `Module.symvers` (recheck02 `raw-musthold.txt:106`). The double signature envelope on all 96 modules matches the boot-tested 20261108 baseline, so packaging is unchanged. |
| **M2** evidence on mutable or deletable paths | **Resolved** | `preserve_kernel_audit.py` stores proofs by content digest. Every proof in `kernel-audit-release-final/kernel-audit.json` is under `diagnostics/builds/`. `kernel_artifact.py:114-116` rejects proofs outside diagnostics. |
| **M1** later stages can't reuse the unchanged kernel audit | **Resolved for the readiness step** | `kernel_carry.py` permits only a device change (`:55`) and requires an unchanged kernel, prebuilt, vendor and config contract (`:29-32`). It requires the control's exact audit digest, a passing control and the control's artifact binding (`:33-48`), and re-checks the parent audit with a depth limit (`candidate_gates.py:26-46`). The smoke chain points at the recheck02 RESULTS, manifest and ZIP. The step after the build is still open (N2). |
| **L1** ancestry/delta gates trust outer flags | **Resolved** | `machine_gates.py:34-45` now parses `kernel-refs.json` (target, base, parents, ancestor flag, four paths) and the actual paths in `local-delta.patch`. |
| **L2–L5** tracing wording, runtime checklist, deadline, flash visibility | **Resolved / accepted** | `TRACING_DECLARATION.md` now says the change is deferred and incomplete. `RUNTIME_GATES.md` item 4 adds the exact uname, the 574-module set with its two known absences, audio, refresh switching, suspend/resume, and the EL2 go/no-go plus hard block. The deadline is disclosed. The delivery includes `RUNTIME_PENDING.md`, it is listed in `SHA256SUMS`, and `sha256sum -c` passes for every file. |
| **L6** tests and leftover pack | **Resolved / accepted** | 108 tests pass (`post-review-tests.log`), including the full frozen-candidate flow. The 3.29 GiB pack was measured and is counted in the budget. |

## Remaining findings
**N1 — Medium: four GKI module copies in vendor_boot are not bound to the audit.**
- `libarc4.ko`, `zram.ko`, `rfkill.ko` and `zsmalloc.ko` also ship in vendor_boot's first-stage ramdisk (`vendor_ramdisk00/lib/modules`). Those are the copies that load first.
- `kernel_artifact.validate` only reads `fs/system_dlkm` (`:131-143`), and `validate_receipt` only looks at system_dlkm inventory entries (`:168-169`). These four copies are covered only by the CRC check, which a stale build with the same CRCs would pass.
- The current artifact is fine. I checked each ramdisk copy: it is exactly the system_dlkm copy minus its outer signature envelope, its unsigned body is identical, and the baseline ramdisk has the same single-envelope layout.
- **Fix:** have the gate unpack each vendor_ramdisk, require every audited module name found there to equal the audited stripped ELF after envelope removal, and record those copies in the binding and receipt. This also meets the plan's K3 "every packaged copy" rule.

**N2 — Medium: the tools that create the post-build release audit are not in the recipe.**
- `docs/kernel-candidate-evidence.md` says every newly labelled stage needs a new release audit after its build. The new label changes the banner, so `kernel_artifact.validate` will fail on the carried parent's vmlinux.
- The tools that create that audit's reports (pKVM pahole and callback types, `candidate-module-crc.json`, `protected-policy-report.json`, symbol membership, config delta, sealing) exist only as unversioned scripts in `D:\android_rom_building\tmp\` (`klimt-seal-release-audit.py`, `klimt-module-contract.py`, `klimt-protected-policy.py`, `klimt-release-analysis-inputs.py`, …).
- They are not hash-bound in readiness tooling and have no tests. The recipe only *validates* their output (`machine_gates.py`).
- As designed, each carried stage's first verification fails, and then depends on these ad hoc scripts.
- **Fix:** move the release-audit producers into the pipeline, include them in the tooling hash map, add a post-build "release audit" step with tests, and document the expected first-verify failure (or run the audit before verification).

**N3 — Low: the "K runtime-admitted first" rule is not enforced by the tooling.**
- `kernel_carry.validate` accepts any verified control's RESULTS. It doesn't check runtime admission, `VERIFIED.txt` or `PROMOTED.json`.
- The doc says the carry "never establishes runtime acceptance", so this is an owner-discipline step.
- An owner-recorded admission file tied to the control archive's hash would make the plan's serial order mechanical.

**N4 — Low: some links in the evidence chain are not mechanically checked.**
- The preserved `Module.symvers` is not checked against the CRCs inside the byte-bound vmlinux.
- `audit-fsck.log` is an empty file (hash `e3b0c442…`), which is plausible for a clean fsck but proves little on its own.
- `machine_gates.py:10-13` hard-codes this campaign's target, base, parents and four paths. Any fix-up kernel commit will need a reviewed validator change, which should be documented as deliberate.

## Verdict
- **K (20261111, recheck02, ZIP `035de568…`): APPROVE** for the owner-gated runtime steps. The packaged kernel now matches the audited ELF and config byte for byte, rollback/security equality still holds, and the image gates pass.
- **Pipeline for K+D and K+D+S: REVISE (narrow).** Fix N1 and N2 before the first carried K+D build. N3 and N4 are optional hardening.

## Runtime gates still pending (none satisfied by static evidence)
1. A private bugreport captured soon after an owner-started normal boot, to see which kernel/pKVM signals the unrooted baseline actually exposes.
2. The fastboot slot preflight (slot a is unknown and has older firmware), the owner's fallback/recovery decision, and the physical-key procedure.
3. An authorized no-wipe slot-b flash. Then check the exact uname and config, the 574-module set with the four pKVM modules, and the full hardware/app checklist, followed by overnight use and the owner's EL2 go/no-go.
4. Only after that: K+D, then S120 with matched measurements. All of it must finish by **2026-11-18 15:04:25 UTC**, or a refreshed control is needed.

No flash, reboot, publication or root operation has been performed or authorized.