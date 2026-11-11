# Kernel candidate evidence and unchanged-kernel stages

K, K+D and K+D+S use the serial runtime admission in the reviewed plan. A static control record does not
establish that K has booted or that a later display experiment may start. All phone actions remain separately
authorized. No general upstream sync belongs in these comparisons.

The frozen-candidate entry point remains required while the audited kernel is unpublished. Give its spec
exact kernel/device heads and the preceding validated stage's frozen snapshot as the control. An unchanged
kernel SHA is valid: the audit default 17.0 must still point to it, the build checkout stays detached, only
device changes are admitted, and the existing ROM patch bundle/full effective graph are checked.

For an unchanged kernel/prebuilt/vendor contract, create a prebuild carried audit with `kernel_carry.py`:

```sh
KLIMT_BUILD=<new-date> python3 -B build-setup/evox/pipeline/kernel_carry.py \
  --control-results <preceding-validated-stage/RESULTS.json> \
  --control-manifest <preceding-stage-frozen.xml> \
  --control-archive <identical-validated-control-img.zip> \
  --candidate-manifest <new-stage-frozen.xml> \
  --output <diagnostics/builds/new-date/carried-kernel-audit.json>
```

Run through WSL shell from the workspace. Paths in these commands refer to the actual chosen builds;
do not manufacture a future date or advance the experiment before its preceding runtime gate passes.
The carry validates the control source/manifest/archive, complete passing static coverage and exact
verified parent-audit digest, including its hash-bound packaged kernel/module evidence and inventories.
The parent audit is revalidated recursively. Kernel, kernel build/prebuilt,
vendor and normalized config must stay identical. Only the device project may differ from the control.
All ten audit gates still run. This rebinds the contract to the new control manifest; it never drops a gate,
changes the original evidence or establishes runtime acceptance.

Pass that audit and a newly extracted, provenance-bound rollback baseline from the preceding stage to
`ready.py`. Preserve the inherited campaign freeze anchor: for the current series its deadline is
2026-11-18 15:04:25 UTC. Deadline checks still apply to readiness, verification and promotion; if it expires,
revalidate a refreshed control as a separate stage and restart affected comparisons.

Every newly labeled build still needs exact release ELF evidence after compilation. A carried audit alone
does not let a differently labeled Image pass. The controller now runs the versioned `release_audit.py`
after a successful full build and source-manifest check, before the first image verification. It preserves
the real vmlinux, all 96 GKI module ELFs, .config, Module.symvers and generated headers, regenerates
type/pKVM/vendor-CRC/protected-header/tracked-membership/config reports, retains source/semantic and carry
provenance, and seals permanent evidence. Its compiler-output CRC table is independently compared with
the CRC values decoded from vmlinux and every GKI ELF. Budget the full normal build plus release ABI checks and image
verification for each stage. The current retained debug/proof corpus is about 0.5 GB; reserve at least 2 GiB
additional host capacity for its immutable copies as well as the existing build/extraction space gates.

Use `preserve_kernel_audit.py --audit <new-audit.json> --output <diagnostics/builds/date/kernel-audit-release>
--frozen-manifest <new-frozen.xml>` before final verification. It content-addresses all proofs, preserves
historical command argv, rewrites dereferenced input paths (including relocated old ELF records by digest),
and validates the preserved audit. Packaged-candidate verification rejects proofs outside release diagnostics.
The next installclean or cleanup of analysis caches must not invalidate a delivered audit. The automatic
producer already performs this preservation. Manual `preserve_kernel_audit.py` is also available for
reviewed historical corrections.

The post-build update binds the original readiness, prebuild manifest, successful build-exit/archive and
exact frozen tooling hashes. Verification and promotion independently validate that context before using
effective verification-only readiness. Original readiness is unchanged. Automatic analysis must preserve
the admitted normalized configuration: it cannot approve newly discovered flags or learn an expectation
from the tested image. A mismatch is an explicit review requirement, not the normal carried-stage path.
The standalone `release_audit.py <attempt> --admitted-audit <reviewed-audit.json> --output <diagnostics-path>`
prepares historical evidence only; its record is marked non-automatic and requires the existing explicit
tool-review/recheck path. It cannot be substituted for an automatic build admission.

For an unchanged archive, use the existing explicit `tool_review.py ... --kernel-audit <preserved-audit.json>`
and verifier-only recheck path. Original readiness/archive/source records remain unchanged. The effective
readiness cannot launch a build. The packaged v4 boot kernel must equal the exact audited vmlinux after the
frozen Image conversion; embedded IKCONFIG must match the audited normalized config. All 96 packaged GKI
modules must equal the audited ELFs after debug stripping and removal of structurally bounded appended
signature envelopes. Signatures are recorded, never altered or claimed cryptographically verified by this
comparison. Stock vendor-module CRC/protected-policy checks remain separate.
Every audited GKI copy in vendor_boot is checked too: this campaign retains libarc4, zram, rfkill and
zsmalloc in the first-stage ramdisk. The gate parses every packaged v4 ramdisk directly, compares each
copy's stripped ELF bytes and binds its record to the complete vendor_boot image digest. Missing,
duplicated or stale copies fail; the 96 system_dlkm instances remain independently checked.
The packaged CRC check uses the preserved, hash-validated release Module.symvers; it does not infer the
candidate's CRC table from whatever happens to be in the mutable KERNEL_OBJ output directory later.

RESULTS binds this kernel/config/module comparison and both image/filesystem inventories. Promotion
revalidates those records against the archive, audit and each packaged module hash. GNU build-id matching
alone is insufficient for Image because the arm64 rule removes its build-id note; exact byte comparison
also covers module relocation/symbol data beyond allocated sections.

This campaign deliberately pins the ACK base, official target and four-path owner delta in the machine
validator. A kernel fix-up or different target requires a reviewed validator/admission change; it is not
implicitly admitted as an unchanged-kernel carry. An empty fsck stdout file is historical command output,
not standalone ancestry proof; the pinned raw parent/tree/delta evidence and independent source review
remain separate. Runtime acceptance is still an owner-recorded device decision, never inferred from a
static RESULTS or promotion receipt.
