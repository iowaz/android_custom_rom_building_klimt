# evox23: build recovery

Status on 2026-10-20: resumed at 21:43 Sao Paulo time and built successfully at 22:16:58
in 33m20s. The 5,661,632,773-byte image ZIP has a recorded SHA-256. Post-build artifact
inspections passed; dirty-flashed to slot b at 23:01:05, with 111 OKAY, zero FAILED,
zero erase/format operations and no slot-a writes. Left in fastbootd without the final
Android reboot. The owner subsequently rebooted Android; adb confirms completed boot
on slot b. Play Integrity is reported BASIC-only and is being investigated in
`diagnostics/builds/evox23/integrity-20261020-2306/FINDINGS.md`; other runtime testing is pending.

Post-build progress is in `diagnostics/builds/evox23/postbuild-20261020/status.json`
and `verify.log`. The run checks archive hash, inventory and CRC, extracts images and runs
the existing must-hold and historical checks. Their strict failures remain failures.
The original release verifier remains blocked because this manual build has no pre-build
approved frozen readiness record. A separate diagnostic adapter in
`diagnostics/builds/evox23/practical-review/` recorded that provenance assertion as unknown
and ran every artifact assertion in all seven tracks; all passed. No release verification
marker was issued. Five missing source-review inputs were revalidated against current clean
project HEADs and reverse-applicable patches. The historical suite then passed 188 checks;
the six old Pixel identity expectations were separately replaced by explicit Xiaomi identity
checks, all passing. The original failures were retained. See TEST_FLASH_ASSESSMENT.md.

Flash authorization and results are recorded in `diagnostics/builds/evox23/RUNTIME.md`,
`flash-evox23.ps1`, `flash-evox23.log`, `flash-status.json` and `FLASH_RESULT.json`.
The candidate is in `output-zips/evox23`; evox21 remains the boot-tested fallback.

Claude's original `updatepackage` failed at 21:05:36 after 28m19s, at 531/15008 tasks.
The `build-manifest.xml` rule invoked repo inside the read-only build sandbox. The global
Git configuration had changed at 18:06, leaving `/home/diogo/.repo_.gitconfig.json` stale.
Repo tried to regenerate that cache and failed with `OSError: [Errno 30] Read-only file system`.

Recovery refreshed the repo cache by running `repo manifest -r` outside the sandbox.
The same manifest operation then passed inside nsjail with the original read-only mounts.
No Android source or sandbox permissions were changed for this recovery. Resume runs
`m -j12 updatepackage` against Claude's staging; its original installclean already completed.
An independent Windows WSL keepalive was already running.

Records are in `diagnostics/builds/evox23/resume-20261020/`: the original failed log,
resume script, build.log, status.json, prebuild-heads.xml and prebuild-source-status.txt.
The HEAD manifest is copied to `manifests/snapshots/evox23-resume-heads.xml`.
It records commit IDs only: Claude's uncommitted device and vendor/lineage edits are
listed in the status record and saved separately as local patches in the diagnostics folder.
This is not yet a frozen, reproducible or verified release snapshot.

The cache refresh addresses this failure. A future edit to the global Git configuration
can invalidate it again; refresh the repo manifest cache before starting that build.
