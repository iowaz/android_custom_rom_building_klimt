# Evox26 independent review disposition

Reviewed with Claude Opus 5.5 High on 2026-10-21. All five requested tasks were reviewed read-only through the CLI; the verifier received an additional review. The first kernel run reported mixed model usage, so a separate kernel confirmation was obtained using only Opus 5.5. Full raw inputs, results and model records remain private.

| Area | Disposition |
|---|---|
| Kernel metadata | Static review passed. Keep the real kernel source SHA and local build number in CONFIG_LOCALVERSION, and retain all existing ABI/module checks. Verify generated config, kernel release and packaged banner after compilation. |
| Partition identity | Build-only follow-up review passed after checking both property generators and quote/duplicate handling. Keep actual platform build dates; pin only the explicitly requested kernel date. Hardware/SKU identity and attestation-service code remain unchanged. |
| Reported vendor SPL | Requested metadata change retained; boot SPL stays at its existing value. Proprietary blobs are unchanged. KeyMint monotonicity and rollback safety remain unvalidated, so compilation approval does not authorize a flash. |
| Optional packages | Retain them: the namespace list includes platform and device dependencies. No dependency-safe removal set was established. |
| Optional RRO | Skip: fe:02/fe:03/fe:32 are filesystem device IDs in memory maps, not resource feature declarations. The precise detector-trace cause remains unresolved. |
| Verifier | Static review passed. Preserve all 194 historical checks and add a fail-closed metadata gate. Follow-up improvements implemented before launch include decimal build-number parsing, REL/release assertions and actual consistent partition dates. |

Before launch, 22 pipeline tests, 46 image-checker tests, nine generator/fallback checks and ten metadata positive/negative cases passed. Readiness confirmed 1,263 clean pinned projects, five retained source checks (two PduParser protections, the Bluetooth attribute fix, the WAP-PDU denial-of-service fix and the SMPTE 2094-50 capability guard), the exact-base patch bundle and capacity. These are source/static checks, not a boot test.

The initial identity review correctly raised timestamp and future-upgrade concerns. August platform dates were removed from the candidate because build.prop dates feed OTA metadata. Evox26 itself changes PackagePartitions' digest on migration from the Pixel profile; later builds reusing the fixed fingerprint/incremental still need a reviewed unique upgrade discriminator or reliable upgrade/cache solution before a dirty flash. No framework upgrade patch or user-cache deletion was added here.

The platform SPL override was already present in Evox25. The new reported vendor SPL increase is separate and explicit. The preceding boot image and source prove the preserved boot SPL; actual Evox26 AVB/kernel/module evidence remains pending compilation. No data-preserving rollback to an older vendor SPL is promised.

Source and detailed limitations: [Evox26](evox26.md). No flash was performed or authorized by the build/publication task.
