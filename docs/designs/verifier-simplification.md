# Build verification: simple and full modes

Revision 5, 2026-11-11. **Implemented 2026-11-11 (steps 1-4; step 5 partly, see "Implementation status").**
Used for the simple 20261111.2 build and full 20261112.2 build; both passed their selected checks.
No ROM-source changes are part of this verifier design.
Revision 5 answers the review in
`D:\android_rom_building\diagnostics\plans\20261111-verifier-simplification\review.md`. It changes four things:

- It adds a narrowed kernel-candidate path.
- It computes escalation instead of relying on a declared change note.
- It places every kept check that today lives in legacy code.
- It keeps the delivery folder shape.

It also defers the ROM-profile, registry and environment machinery until something needs it.

## Recommendation

Default to `simple` for routine EvoX/klimt builds: upstream syncs and small local fixes on the same
product, signing, vendor base and kernel arrangement. ready.py escalates automatically when recorded
inputs show something more than routine. It adds named existing checks ("extras") for the affected area,
or selects `full` for a new vendor/firmware base, a signing or partition change, or an Android-version
migration. Neither mode proves that the phone boots or that its hardware works.

Build it in the smallest form that works:

- `full` is today's verifier, unchanged at first.
- `simple` is a new, short path in verify.py.
- The extras are the seven existing supplemental tracks plus the existing module-CRC check.
- Profiles for another ROM, a check registry and a plan preview wait until a second ROM recipe actually
  exists.

## What the evidence supports

The pipeline's one artifact failure on the phone was evox16. A focused `m Telecom` left the legacy Telecom
APK in staging next to TelecomShim. The build succeeded and the phone boot-looped. The verifier of that
time passed it. Three things have addressed that failure directly since then:

- build.sh's `m installclean` with its empty-staging assertion (build.sh:44-48)
- the ban on module goals in the packaging tree
- the `install_integrity` track, which fails on the evox16 output

Simple keeps the staging half of that last check. It does not need to disassemble unrelated components
on every build.

The recent build records show no verifier-found artifact defect. 20261105, 20261105.2 and 20261105.3
passed "without a verifier correction or recheck". 20261111's three rechecks followed verifier and
kernel-gate changes, not artifact defects. Implementation step 1 completes this as a table back to evox17.

Measured cost, from the 20261111 attempt02/recheck02 audit (file-completion timestamps, not profiling):

| Interval | Time |
|---|---:|
| Archive copy, hashes and CRC | 1m 27s |
| Extraction of eight filesystems (extract.sh) | 8m 15s |
| Must-hold, historical, Health/HIS and metadata checks | 1m 21s |
| Seven supplemental tracks | 10m 40s |
| Candidate checks and full filesystem/image inventories | 2m 17s |
| Final source check, reports, delivery checksums | 1m 41s |
| Total, excluding entry preflight | 25m 41s |

The audit's start point excludes the entry preflight. That preflight includes a full hash of the
5.1 GB ZIP and a manifest capture (verify.py:123,148). Across verification and promotion, one build's
ZIP is currently read about nine times: the build-exit hash, the entry hash, the copy, the hash of the
copy, a second source hash, testzip, unzip, `sha256sum *.img`, SHA256SUMS and promote's hashes. Most
of the cost is in extraction and the deep tracks, but the repeated reads are the main remaining cost
in simple.

### The kernel-candidate path

20261111 is a kernel candidate: its RESULTS.json carries `candidate_evidence`. ready.py and promote.py:29
treat any kernel head other than `kernel_contract.BASELINE` (f6a5b29) as a candidate. Today the
candidate path needs:

- `extract/fs/system_dlkm` and `extract/img/boot.img` for the kernel binding (verify.py:198-199)
- `avbtool info_image` over the images for rollback/security equality (verify.py:202)
- `filesystem-files.json`: a hash of every extracted file on all eight partitions (verify.py:205).
  promote.py:53 requires it.

Left as it is, this keeps the full extraction and inventory, about 10 minutes, on every build until the
kernel is admitted as BASELINE. But `kernel_artifact.validate_receipt` only reads the
`system_dlkm/*.ko` rows of that inventory (kernel_artifact.py:188), and the module-CRC check reads
`vendor_dlkm`, `system_dlkm` and the vendor_boot ramdisk. In simple mode the candidate add-on therefore
extracts only `vendor_dlkm` and `system_dlkm` and inventories only those two trees. Its other
requirements stay unchanged: audit, binding, rollback equality, runtime admission and the owner's
go/no-go.

## Simple mode

Simple is an artifact, staging and delivery check. It does not inspect filesystem contents, except the
kernel partitions when the candidate add-on applies.

| Check | What it does | Source today |
|---|---|---|
| `attempt.provenance` | build-exit `exit == 0` (under `set -eo pipefail` this already proves installclean and the empty-staging assertion passed); the ZIP digest, size and mtime equal build-exit; tooling hashes; live heads equal the readiness heads before and after verification; attempt ownership and locks. | verify.py:98-148, unchanged |
| `archive.integrity` | The exact 19-entry set, no duplicates. One CRC-checking pass over the ext4 ZIP that writes only `*.img`, `*.txt` to ext4 scratch. The delivery copy is hashed while copying; the digest must equal build-exit. | verify.py:163-174, rewritten for fewer reads |
| `avb.chain` | `avbtool verify_image --image vbmeta.img --follow_chain_partitions` on the extracted images; records each vbmeta public-key digest and fails if it differs from the previous promoted build's. A key change is never routine. Schema-1 baselines have no recorded digest, so the first time it is read from `vbmeta*.img` in the baseline's promoted ZIP, read-only. | legacy/musthold.sh M2, moved |
| `flash.layout` | The super_empty lpdump layout equals the author/build9 references, with the existing all-readonly exception; `fastboot-info.txt` and `android-info.txt` equal the references. | musthold.sh M3-M4 plus report-gates.py interpretation, moved |
| `dtb.live` | The dtbo payload and the vendor_boot DTB equal the saved live slot-b backups. This is the check that ties the image to the phone's real partitions. | musthold.sh M5, moved |
| `identity.metadata` | `check-metadata26.validate()` (all 112 assertions: genuine Xiaomi fingerprint, build ID, incremental, SPL, no legacy Pixel values on the eight partitions) over the eight build.prop files captured from staging at packaging time, plus the `-ab<build>` kernel banner from the packaged boot.img. Labelled "staged props". | check-metadata26.py, new input |
| `staging.clean` | Every captured staged path is in this attempt's install list (guarded `.installable_files` / `.previous` semantics), except kernel module trees; exactly one `com.android.server.telecom` APK path, matching the captured Telecom mainline flag. | install_integrity, staging half |
| `signing.platform` | The signer of the staged `framework-res.apk` equals the reviewed platform certificate in BUILD_READY `public_certificate_sha256`. | new, small |

The 112 metadata assertions stay because their cost was extraction, not the assertions. The identity
layer is deliberate and the owner relies on it. Reading props from staging trusts the packager to put
staged files into the images, and the report says so.

Simple does not run:

- the 195 historical rows
- check-health-his.py
- the seven supplemental tracks
- the module CRC check (unless the kernel extra or candidate add-on applies)
- full filesystem extraction
- the full file/APK inventories

It cannot detect:

- a packaged file that differs from staging
- a duplicate package identity under another path
- Ninja producer drift
- a behavioral or ABI regression in a component whose sources did not change

The report must not claim it inspected these.

### Packaging-time evidence

On `exit 0`, build.sh's `finish` hook already runs inside the controller's source lock. It also writes
`staging-evidence/` beside build-exit.json and records each file's sha256 in build-exit.json:

- `installable_files`: the guarded current/previous list, with which one was used
- `staged-paths.txt`: paths only, under the eight staging partitions
- the eight build.prop files, under the PARTS layout check-metadata26.py expects
- `build-vars.json`: the Telecom mainline release flag that check_image.py reads today, and
  TARGET_PRODUCT/variant/release
- a copy of the staged `framework-res.apk` signing block, or the apksigner output for it

This runs once for the producing attempt. A later build cannot supply it, so an old attempt without it
cannot be rechecked in simple mode.

## Full mode and extras

Full is today's verifier path, unchanged in the first phase: musthold, fixcheck, Health/HIS, report-gates,
metadata26, the seven tracks, candidate checks and inventories. Cleaning it up comes later (step 6) and
does not block simple.

An extra runs one existing track script from IMAGE_CHECKS.json, or the `kernel` group (musthold M6 module
CRCs and M7 vermagic), on top of simple. Any track extra needs the full extract.sh extraction and the
producing `out/`, exactly as today, so it costs about 8 minutes plus the track. A build with extras
records `mode: simple` plus `extras: [...]`. It is not called full.

## Choosing the mode: computed, not declared

ready.py resolves the mode once and writes it into the write-once BUILD_READY.json:

```json
"verification": {
  "schema": 1,
  "mode": "simple",
  "extras": ["health_semantics"],
  "candidate": false,
  "baseline_build": "20261111",
  "reasons": ["device tree health/ changed since 20261111"]
}
```

The baseline is the newest earlier build with a `diagnostics/builds/<build>/PROMOTED.json`. ready.py
reads that build's `BUILD_READY.json` and diffs it against the current readiness. That is a two-manifest
comparison; it does not try to interpret commits. If there is no readable baseline, the mode is full.

| Recorded change since the baseline | Effect |
|---|---|
| Kernel head ≠ `kernel_contract.BASELINE` | Candidate add-on (existing rule, automatic) |
| Kernel head changed, any | `kernel` extra |
| Private vendor blobs head changed, `public_certificate_sha256` changed, target/release changed, Android version changed | `full` |
| A patched project's upstream `base` or its patch files changed (`patch_bundle.projects`) | The extra mapped to that project below |
| Device-tree paths changed (`git diff --name-only` between the two device heads, run in WSL) | The extra mapped to those paths below |
| Anything else (ordinary upstream sync, SPL bump, unmapped paths) | Simple, no extras |

Initial mapping, to be confirmed against the tree during implementation:

| Project or device-tree path | Extra |
|---|---|
| `device/lineage/sepolicy`, `sepolicy/` | `policy` |
| `build/soong`, `frameworks/native`, `hardware/interfaces`, `miui-stub/` | `patch_packaging` |
| `wifi/`, `proprietary-files.txt` | `private_compatibility` |
| `health/` | `health_semantics` |
| `udfps/`, `parts/`, `apps/`, `overlay*/`, `rro_overlays/` | `doze_packaging` |
| GMS vendor project | `gms_themes_apps` |
| `BoardConfig.mk` lines matching `BOARD_.*PARTITION`, `BOARD_SUPER_`, `BOARD_AVB_`; `modules.load.*`; `rootdir/` fstab | `full` |
| `class: personal` patches, `libinit/` | none extra; `identity.metadata` always runs |

The operator can add extras or choose full with `--extra` / `--mode full` and a `--reason`, but cannot
remove a computed one. There is no force-simple option. The resolver is a pure function of the two
readiness records and the device-tree path list, covered by table tests.

## Rechecks and the archive

- A recheck uses the existing tool-review route. TOOL_REVIEW may add extras or select full. It never
  removes anything the sealed readiness selected. Its result keeps its own mode label and never replaces
  an earlier report.
- The ZIP source for a recheck is `out/.../lineage_klimt-img.zip` if it still matches build-exit.
  Otherwise it is the attempt's staged delivery copy or, after promotion, the promoted copy found
  through `PROMOTED.json`. In each case it is matched by the build-exit digest, never by filename alone.
  The promoted folder is read-only to verification.
- A full recheck or a track extra still needs the producing `out/`. If a later build changed it, the
  recheck stops with a missing-evidence error. It does not rebuild, and it does not issue a full PASS
  from an archive-only subset.
- The delivery folder keeps its current shape: the ZIP copy, the flash wrappers that need it beside them,
  RESULTS, SHA256SUMS and the marker. promote.py's rename and same-digest duplicate removal therefore stay
  correct. Simple writes the SHA256SUMS entry for the ZIP from the digest computed during the copy, after
  a destination read-back. That leaves about five reads instead of about nine: build-exit, copy+hash,
  CRC/unzip from ext4, destination read-back, promote.

## Results and promotion

RESULTS.json gets `schema: 2` for new reports. It holds the `verification` record from readiness or
TOOL_REVIEW, one entry per required check (`id`, `outcome`, `summary`, `evidence`, `elapsed_seconds`),
the archive digest and `runtime_unvalidated: true`. Checks that were not selected are listed for people
under `not_selected`; promotion never reads that list.

promote.py, for schema 2, recomputes the required check list from the sealed record:

- the simple checks
- each extra's track or group
- the candidate checks when `candidate` is true

It requires each check exactly once with `pass`, and rejects unknown, missing, duplicate or failed
checks. Mode, attempt and archive identity must match. Candidate validation is unchanged, except that
in simple mode the inventory it checks covers only `vendor_dlkm` and `system_dlkm`. Schema-1 reports and
existing deliveries keep the current path, with the 195 names and the seven coverage strings, for as
long as they exist. A missing `verification` record never means simple.

Marker and README text for simple:

```text
SIMPLE static checks passed (archive, AVB, flash layout, live DTB, staged identity props, staging, platform signer).
Filesystem contents were not inspected. NOT boot-tested.
```

Exit codes are new: today every failure is an uncaught exception, and controller.py:423 records
`tool-failed`. verify.py will exit 1 for an artifact or assertion defect, naming the check and the
artifact; 2 for a missing tool, missing evidence or the wrong host; 3 for an unexpected error. The
controller stores the code and the failing check ID in status.json and keeps its existing states.

## Host guard

The incident was Windows Python reaching `import fcntl`. A guard of about 10 lines (`hostcheck.py`, stdlib
only) runs first in verify.py, promote.py, ready.py, tool_review.py and controller.py, before importing
`fcntl` or `controller`. On a non-Linux host it prints the `wsl.exe -d Ubuntu-24.04 -- python3 ...`
equivalent and exits 2, without creating anything. Mount and out-symlink identity are already checked by
build.sh:24-26 and controller.py:290. Simple checks only its own tools (avbtool, lpdump, unpack_bootimg,
apksigner) in one list, before copying anything.

## Deferred until there is a consumer

- ROM profiles, crDroid and a recipe abstraction for the hardcoded target. A crDroid verification profile
  without a crDroid build recipe is useless. When one comes, it starts in full mode. It also needs a
  defined boot record, for example the `uname -r` `-ab<build>` suffix captured after a flash, before any
  simple-mode eligibility.
- A check registry or dataclass framework, `--show-plan`, environment observations in RESULTS, VHDX and
  memory budgeting beyond today's `space()` limits, and detection of a Windows `.exe` winning PATH.
- Parallel workers, shared APK inventory and cross-run caches for full (see parallel-verifier.md). Step 6
  only.

## Implementation plan

1. **Failure history.** Tabulate every verifier failure since evox17 from `docs/<build>.md` and the
   reports, as artifact defect or verifier defect. If any artifact defect was caught only by a check that
   simple skips, add that narrow assertion to simple before going further.
2. **Host guard and exit codes**, with tests: the guard runs on Windows Python before fcntl, and the
   failure classes map to their codes.
3. **Packaging-time evidence** in build.sh's finish hook. Run it on one ordinary build alongside today's
   full verification; that changes no verification result.
4. **Simple path, resolver and promotion.**
   - Add `verify.py` simple, the ready.py resolver and record, schema-2 promotion and the narrowed
     candidate add-on.
   - Fixtures that must fail:
     - the evox16 staging case (stray Telecom APK)
     - a missing evidence file
     - an extra or duplicate ZIP entry, and a corrupt CRC
     - an AVB image with a tampered byte, and a changed vbmeta key
     - a dtbo mismatch
     - one wrong identity prop
     - a platform signer mismatch
   - Promotion must reject missing, extra or failed checks and a mode mismatch. Table tests cover the
     resolver.
5. **Benchmark** simple on the preserved 20261111 attempt02 ZIP, entry to promotion, in two cases:
   non-candidate (goal ≤ 5 min) and with the candidate add-on (goal ≤ 8 min). Then make simple the
   default for routine builds.
6. **Full cleanup, separately:** remove obsolete historical rows and duplicate metadata, deduplicate the
   461 repeated aapt calls, batch the Ninja queries, then consider the useful parts of parallel-verifier.md.

## Verifier failure history (step 1)

Every recorded stop of the verifier since evox17 (when `install_integrity` was added), from `docs/<build>.md`:

| Build | Stop | Kind |
|---|---|---|
| evox17 | Codex review found three checker gaps (E17-001 Telecom path trusted, E17-002 APK symlinks, E17-003 libdmabufheap/libion producers); recheck01 | verifier gap, no artifact defect |
| evox18 | progress watcher matched the competing-build guard; a local `paths` shadowed the module; musthold called a moved `/mnt/c` helper; D: below the 38 GiB reserve; recheck04 passed | tooling, host |
| evox19 | `install_integrity` found no `.installable_files` (Soong renamed it to `.previous`); recheck01 | verifier |
| evox26 | report-gates required the old CI kernel banner; inherited checks kept the old Pixel fingerprint and February SPL; recheck01 | verifier pins |
| evox27 | super_empty readonly attributes (build/make 90d0063); policy check pinned evox26's sepolicy commit; D: below reserve; recheck03 | verifier pins, host |
| evox28 | evox12 `sysfs_wakeup` genfscon count 148 vs 239 from the new MediaTek policy; recheck01 | verifier pin |
| 20261111 | rechecks 01-03 after new kernel candidate gates | verifier changes |

evox21, evox22, evox25, evox30, evox31, 20261104, 20261105, 20261105.2, 20261105.3, 20261106 and 20261108 passed on the
first verification (evox20, evox24 and evox29 have no build document). No verification stop since evox17 was an
artifact defect. The one artifact defect in the record is evox16's stray Telecom APK, which `staging.clean`
covers (fixture in test_simple_verification.py). Simple keeps the two verifier lessons that touch its checks:
the guarded `.installable_files`/`.previous` choice and the super_empty readonly exception.

## Implementation status

Implemented in `build-setup/evox/pipeline`:

- `hostcheck.py`: the guard, first in verify, promote, ready, tool_review, controller, prepare and launch.
  Checked under Windows Python: exit 2 with the `wsl.exe` command.
- `verification.py`: the record, resolver, mapping tables, `widen`, required checks, schema-2 promotion contract
  and exit codes.
- `simple_checks.py`: the eight checks and the kernel extra.
- `staging_evidence.py` plus build.sh's exit hook: evidence hashed into build-exit.json.
- verify.py: simple path, `verify-exit.<run>.json`; full path unchanged except defect classification.
- ready.py: `--mode/--extra/--reason`, baseline lookup through PROMOTED.json, baseline AVB keys from the
  baseline's promoted ZIP (hash-bound).
- tool_review.py: `--mode full`, `--extra`.
- promote.py: schema 2.
- controller.py: record validation, exit code in status.

Current pipeline discovery passes 216 tests (2026-11-12), including the unchanged-kernel upstream-refresh
admission tests. Real build evidence is recorded in [20261111.2](../20261111.2.md) and
[20261112.2](../20261112.2.md).

Differences from the text above, decided while implementing:

- The baseline AVB keys are read at readiness (ready.py), not by verify.py.
- `rollback_security.collect` now passes sparse images to `avbtool info_image`, which reads them directly.
  Unsparsing system/system_ext/product first cost 111 s. The full path is unchanged, because it unsparses
  first.
- A simple candidate's rollback record reads the reported SPL props from the staged build.prop files, through
  a view whose `fs` is the packaging evidence.
- image-files.json comes from the member hashes taken during the CRC pass, so no image is hashed twice.
- The real data needed two fixes, which the fixtures had missed:
  - Android 17 keeps ProductPackages under `PartitionVarsForSoongMigrationOnlyDoNotUse`, so the whole Soong
    document is searched, as check_image.py does.
  - 20261111's framework-res.apk is v3-only. apksigner prints `V3.0 Signer: certificate SHA-256 digest: ...`.

## Benchmark (step 5, partial)

On 2026-11-11, simple checks ran on the 20261111 attempt02 ZIP still in `out/`, with no attempt or delivery
created. Staging was captured from `out/` after the fact. Scratch was on ext4, and a delivery copy went to
D:\android_rom_building\tmp; both were removed afterwards. Two runs:

| Step | Run 1 | Run 2 |
|---|---:|---:|
| Copy to D: while hashing | 23.5 s | 56.3 s |
| CRC pass and image extraction to ext4 (8.0 GB) | 28.5 s | 57.4 s |
| avb.chain (verify_image on the sparse images) | 12.5 s | 14.5 s |
| flash.layout, dtb.live, identity.metadata, staging.clean, signing.platform | 0.5 s | 13.6 s |
| Read back the delivered ZIP | 17.9 s | 18.0 s |
| **Simple checks** | **83 s** | **160 s** |
| Kernel extra and candidate: vendor/system_dlkm, ramdisks, module CRCs (888, 0 mismatches), rollback, kernel binding | — | 43 s |
| At readiness: hash the baseline ZIP, read its vbmeta keys | 44 s | 43 s |
| At packaging: staging capture | 2.2 s | 1.4 s |

Run 1 found the two format problems listed above. In run 2 every check passed. The candidate rollback record
and kernel binding were byte-for-byte equal to 20261111 recheck03's `rollback-security-candidate.json` and
`kernel-artifact-binding.json`, so the staged SPL props and sparse `info_image` give the same result as the
full path.

Not timed: entry provenance (live heads and two `repo manifest -r` captures, as in full mode) and promotion.
The copy and extraction times vary by about a factor of two between runs. Still, a candidate build like
20261111 needs about 3-4 minutes of checks instead of 25m41s.

A dry run of the resolver on the real readiness files gives simple + kernel extra + candidate in two cases:

- 20261111's readiness as the next build, against 20261111
- 20261111 against 20261108

That is 11 required checks.

Not done yet:

- No real build has run in simple mode. The first one exercises packaging-time capture, ready.py and
  promotion end to end.
- Step 6 (full cleanup) is untouched.

Do not edit the pipeline while an attempt runs, and run the existing pipeline tests between attempts.
Neither mode authorizes a flash or replaces a boot test. Say "image-checked" until the phone has booted
the build.
