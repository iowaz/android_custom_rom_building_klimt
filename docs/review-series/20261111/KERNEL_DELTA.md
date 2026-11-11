# Kernel maintenance audit

The audit candidate is `08c56166f1883020396e8e95570671407f00ba04`, with parents
`f6a5b29f9fe59e4849680d50232f8b5758aa8c11` and official LTS
`1c39bb5f635a741f90a5ecb4535e7bd264083a80`. Its tree is the exact official 6.6.144 tree plus the
complete preserved klimt delta. Nothing has been installed in the ROM build checkout at this checkpoint.

## Local changes retained

The true LTS base is `c3dd858dcf5843346c0a5b9c031ae0e9e0664277`. The net baseline delta is exactly:

| File | Disposition |
|---|---|
| android/abi_gki_aarch64_klimt | Keep the 9,273-symbol whitelist byte-for-byte. |
| android/klimt_gki_modules | Keep the complete source-built module list. |
| arch/arm64/configs/klimt_defconfig | Keep the resolved owner config policy; no tuning additions. |
| include/linux/compiler_types.h | Keep the counted_by exclusion under __GENKSYMS__; retain the real compiler attribute for C compilation. |

The actual history is recorded in local-history.txt. `b13ac15b32e25368f70859fff986e07c18d9d5a5`
selected the LTS tree; `8935932d04125c3f0e31f5f9a296a50b1f78e714` introduced the compatibility
files before that integration. The final `f6a5b29` defconfig/localversion adjustment is included in the net
four-file patch. The candidate applies that complete patch to the new LTS tree, rather than assuming the
earlier individual compatibility commit is the final delta.

## Upstream and configuration

The official target remains Android15-6.6, KMI generation 8, and Makefile 6.6.144. A 49-node authenticated
first-parent path reaches the exact old LTS base. Raw commit objects were SHA-1 verified while walking it.
Shallow fetches cut available history locally; missing merge-parent objects were fetched explicitly and only
redundant shallow boundaries whose every parent object was present were removed. The resulting ordinary
Git ancestor check passes. This changes local audit-cache traversal metadata, never an upstream commit.
See raw-first-parent-path.json, missing-parent-objects.json and shallow-known-parent-completion.json.

The source-tree delta spans 739 files, 11,091 insertions and 9,375 deletions. The commit list and full diff
stat are retained separately. Imported areas include upstream filesystem/memory, networking/driver,
userspace-crypto and ARM64/pKVM maintenance. Concrete examples include synchronous processing for the
older algif_skcipher interface, the i2c adapter deregistration race, udmabuf DMA-direction handling,
guest-memory pinning/remapping checks and bounding the pKVM GIC list-register count. This does not assign
unverified CVEs or transfer Google's binary certification to our source build.

The last packaged kernel was actually compiled with Clang r596125 / 22.0.2, not the older compiler declared
by build.config. The isolated candidate analysis uses that same actual compiler, owner build identity,
KCFLAGS and whitelist policy. It uses its own source worktree and output, never packaged staging.
The generated config delta and decisions are in generated-config-delta.json and analysis-config-reviewed.json.
Rust remains disabled; the availability probe differs in the isolated shell. The only upstream capability
addition is HAVE_BUILDTIME_MCOUNT_SORT selected by ARM64. The release resolved config must match the analyzed
config apart from the build label or verification stops for review.

## Vendor and protected-module policy

There are 517 unique stock vendor modules in the Makefile-selected corpus, distinct from 888 packaged
instances. Every versioned baseline import matches, including module_layout. All 517 module_layout CRCs
equal the baseline kernel's CRC 1311207223. Its old checker exclusion has therefore been removed. The one
baseline unresolved symbol remains mtk_drm_gateic_set_backlight; no additional exception is admitted.

All 9,273 whitelist names occur in Google's tracked symbol sets in both old and target trees, with no newly
untracked symbol. Google's protected-export list is unchanged. In this tree there is no separate named
protected-module policy file: kernel/module/Makefile and gen_gki_modules_headers.sh derive the protection
headers from the whitelist and protected-export list. Protected exports restrict exports by unsigned
modules; the generated unprotected list controls their imports. These roles are checked separately.
Stock modules remain vendor modules and are not re-signed as trusted GKI modules.

The vmlinux-only graph misses 217 retained symbols provided by GKI modules. The ABI tool therefore includes
vmlinux and all 96 built GKI module ELFs and verifies coverage of all 9,273 retained symbols before comparing
types. Assembly/alias exports without DWARF types additionally require byte-identical actual C declaration
headers and provider-source proof; stgdiff may not ignore a type-presence change. These are explicit
supplemental contracts, not a successful empty graph or a new module-CRC exception.

## pKVM semantic classification

The entire kvm_pkvm_module.h interface is unchanged at the target, including the callback signatures.
Baseline compiled pkvm_module_ops is 688 bytes. Candidate compiled layout/type comparison remains required.
Stock pkvm_mgmt, pkvm_mkp, pkvm_smmu and pkvm_tmem import the established EL2 loader/call interfaces; their
host-module loading alone is insufficient evidence of successful protected-mode initialization.

| Changed area | Classification and device implication |
|---|---|
| EL2 HCR/E2H initialization and RES1 detection | Upstream early CPU-state repair before module initialization, including the shared el2_setup.h macros. No module-ops slot or callback argument changes. Hardware startup/suspend must still be verified. |
| SCTLR_EL1 / SPSR_EL2 on PSCI CPU entry | Initialize known architectural state before notifying callbacks and returning to the host. No callback signature change; CPU on/resume behavior remains a runtime gate. |
| Hypervisor stack-page ownership | Include privately mapped hyp stacks in the ownership transfer. Module loader/callback interface unchanged; no assumption that host module presence proves the resulting EL2 state. |
| used_lrs bound and hyp_gicv3_nr_lr | Clamp guest GIC state to the implemented register count before restore; internal bookkeeping plus an internal hyp global. No vendor-module ops exposure. |
| pvmfw_relinquished | A new internal pkvm_hyp_vm boolean preserves firmware-release state. This private VM type is not passed through the module ops table, which exposes handles for guest operations. Do not describe all internal hyp layouts as unchanged. |
| IOMMU identity-domain free rejection | Reject freeing the reserved identity domain with EINVAL. No ops signature/layout change; SMMU/protected-camera/video behavior needs on-device validation. |
| Guest pinning / stage-2 split | Hold mmap locking for pin/lookup and verify donated-page PFNs before split. Guest-memory safety changes; no module ops ABI change. |

The byte-exact diff is pkvm-changes.patch plus gitiles-arm64-headers.diff; the candidate must be compared
against the old compiled types. Static compatibility is an admission gate, not a claim of boot safety.
Early unrooted bugreport capability, observable protected-mode signals, slot-a fallback, rollback equality
and the owner's flash decision remain the plan's separate runtime gates.
