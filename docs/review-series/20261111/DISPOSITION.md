# Published review state

The owner requested stopping further reviews and publishing the completed work for direct review.
The final focused Sol/Opus runs were stopped. No flash or phone reboot was performed.

The archived initial and focused reports cover the K implementation and its earlier corrections. Both
approved the observed K artifact. Opus's last two mandatory carried-stage findings were then implemented:

- Every source-built GKI copy is bound to audited ELF bytes: 96 system_dlkm modules and four vendor_boot
  first-stage copies, including each signature-envelope layout and the vendor_boot container digest.
- The versioned post-build producer runs before normal verification and on resume. It regenerates and
  preserves release type/pKVM/CRC/policy/membership/config evidence. Automatic updates bind original
  readiness, source, successful producing archive and frozen tooling, without changing admitted config.
- All 9,434 Module.symvers CRCs are independently decoded and matched against the audited ELF bytes.

All 120 tests pass. The real producer, complete attempt02/recheck03 image verification, promotion and
unchanged-kernel carry validation pass on the unchanged ZIP. The normal automatic-update path is covered
by orchestration/context rejection tests; this historical build's producer record is explicitly manual
and admitted through a separately bound verifier recheck. Original build/readiness/source records remain.

The new N1/N2 code did not receive a completed final independent rereview because the owner stopped it.
The source and tests are published for the owner's review. Hardware, early-boot/EL2 observability,
slot-fallback/recovery and separate flash admission remain pending. Queued D/S patches are review
artifacts, absent from the K build/default device head; runtime acceptance and S's objective benefit are
required before those stages ship. The campaign deadline remains 2026-11-18 15:04:25 UTC.
