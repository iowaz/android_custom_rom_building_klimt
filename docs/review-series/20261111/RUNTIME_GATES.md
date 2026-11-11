# Runtime gates retained from the approved plan

Implementation prepares source and image candidates; these checks are not static passes.

1. Before the first kernel trial, capture a private baseline bugreport soon after an owner-started normal
   boot. Establish the actual unrooted kernel/pstore/protected-mode signals. Preserve observed signals;
   report unavailable signals as unknown. No root or unsolicited reboot.
2. Before an authorized flash, compare the sealed candidate/control rollback-security records and archive
   hashes. In fastboot inspect both slots' available boot/success/retry fields. Slot a remains an unknown
   recovery target with older recorded firmware. Require the owner's concrete fallback/interception decision.
3. Keep the known-good 20261108 archive available. The owner uses the existing no-wipe slot-b helper with
   --skip-reboot. On the first reboot loop enter fastboot immediately; do not consume repeated retries.
   For one uninterrupted no-ADB boot, the plan's conservative cutoff is 90 seconds. Never accept a reset.
4. Validate K's exact uname release `6.6.144-android15-8-g08c56166f188-ab20261111` and, where readable
   without root, its configuration against the sealed embedded-config record. Compare the loaded-module
   set with the captured 574-module baseline, including all four pKVM host modules and the known absent
   `ptp_kvm` / `mtk_swpm_isp_dbg_v6991` entries; do not confuse 574 loaded with 888 packaged instances.
   Check early-boot evidence, charging, suspend/resume as a separate case, AOD/Goodix, display/touch and
   refresh-rate switching, protected video, photo/video, audio, calls/eSIM/data, Wi-Fi/Bluetooth/GNSS, thermal and app checks;
   then observe overnight/normal use. No missing signal or static ABI result is represented as a boot test.
   A proven EL2 incompatibility is a hard blocker regardless of owner preference. Remaining unavailable
   baseline-observable EL2 evidence requires a recorded owner go/no-go, with its uncertainty stated.
5. Package D1/documentation only after K passes. Retain the tracing default pending the writer investigation
   in TRACING_DECLARATION.md. Validate the cleanup build before making it the timing control.
6. The isolated S120 commit is a trial, not a shipping default. Use K+D as control and the identical validated
   control ZIP/hash for a third block. Confirm active 120 Hz and selected timings, with unchanged 60 Hz.
   Keep 90/144 Hz and the vendor 60 Hz table out of this initial trial.
7. Follow PLAN.md's matched workloads, settling criteria, 200k initial frame budget per arm/workload,
   block-aware uncertainty, named app-frame-to-present benefit and non-regression bounds. If unavailable or
   inconclusive, do not promote S. Do not choose a favorable replacement metric after seeing the results.

No timing setting, input injection, device installation, data clear, slot-state write, flash, root operation,
signing-key operation or remote publication is implied by the source implementation.

The campaign freeze started 2026-11-11 15:04:25 UTC and expires 2026-11-18 15:04:25 UTC
(12:04:25 Sao Paulo). It is enforced at readiness, verification and promotion. It is not extended by a
later candidate build or a verifier-only recheck. If staged trials cannot fit, revalidate a refreshed control
as a separate stage before restarting affected comparisons; do not silently reset the clock or weaken it.
