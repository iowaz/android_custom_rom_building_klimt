# Evox16 controlled-build tools

This directory holds new attempt-isolated tooling. The historical Evox scripts,
Evox15 image/reports and shared incremental source/output were not overwritten.

Root must independently review these tools, complete the source/offline gates,
and write `C:/XiaomiBuilds/debug/evox16/BUILD_READY.json` before starting a build.

```bash
bash /mnt/c/XiaomiBuilds/build-setup/evox/evox16/start.sh evox16-attempt01 \
  /mnt/c/XiaomiBuilds/debug/evox16/BUILD_READY.json
python3 -B /mnt/c/XiaomiBuilds/build-setup/evox/evox16/controller.py status evox16-attempt01
python3 -B /mnt/c/XiaomiBuilds/build-setup/evox/evox16/controller.py stop evox16-attempt01
# Reconnect only when the recorded original controller has gone:
setsid nohup python3 -B /mnt/c/XiaomiBuilds/build-setup/evox/evox16/controller.py \
  resume evox16-attempt01 > /mnt/wsl/evox/logs/evox16/evox16-attempt01.resume.log 2>&1 < /dev/null &
```

The resident controller launches one `m -j12 updatepackage` after explicit lunch
and `TARGET_PRODUCT`, `TARGET_BUILD_VARIANT`, `TARGET_RELEASE` and `WITH_GMS`
checks. It retains the existing environment/keys/ccache/out symlink. A separate
watchdog identifies the wrapper by PID, boot ID, `/proc` start ticks, session and
process group; it leaves a terminal record when the build wrapper disappears.
No process-name kill or WSL shutdown occurs. Process names only reject a launch
when a competing old build/extraction is detected. The source flock is inherited
by the wrapper and watchdog so a dead controller cannot permit another launch.
Root separately owns the Windows WSL keepalive process.

Progress JSONL records each process's cumulative CPU, current log length and
three disk free-space figures every 15 seconds. Quiet progress never triggers a
hang stop. Any later hang decision needs at least the plan's 30-minute evidence
window and a human/agent diagnosis. The emergency disk path stops only the
identified attempt. Tool failures, image failures and build exits are separate.

`resume` observes an existing build and consumes its own runner exit evidence.
It never starts a second build. If the runner vanished without an exit marker,
or a partial extraction exists, it stops for diagnosis; it cannot verify a
stale output or silently remove forensics. A new retry uses a fresh attempt ID.

A diagnosed verifier defect can be fixed without rebuilding a successful image.
After independent review, use a fresh verifier-only recheck:

```bash
python3 -B /mnt/c/XiaomiBuilds/build-setup/evox/evox16/verify.py \
  /mnt/wsl/evox/logs/evox16/evox16-attempt01 --recheck recheck01 \
  --tool-review /mnt/c/XiaomiBuilds/debug/evox16/evox16-attempt01/TOOL_REVIEW.json
```

The review JSON requires `approved:true`, `attempt`, exact
`source_snapshot_sha256` of the original prebuild.xml, nonempty `evidence` and
`tooling_sha256` containing the full current map returned by
`controller.tooling_hashes()`. It may replace `image_checks` only with the
independently reviewed script/hash list. Original exit evidence, source snapshot,
reports and failed extraction stay untouched. New report/extraction/delivery
directories use `rechecks/recheckNN`; original ZIP SHA/mtime/size and unchanged
source still gate the recheck. This command cannot start an Android build.

## Readiness JSON contract

Required fields:

- `approved: true`, `target: "lineage_klimt-cp2a-user"`, `runtime_unvalidated: true`.
- `snapshot`: full frozen XML path (Windows or WSL); `sha256`: exact file digest.
- `reviewed_project_heads`: full path-to-SHA map of every immutable snapshot project.
- `excluded_heads`: includes kernel, kernel-prebuilt, vendor, Xiaomi common and
  MediaTek policy heads. It reflects the final explicitly reviewed disposition;
  the sensor-parser exception must be recorded in the source ledger.
- `checks`: nonempty list of `{ "name": "...", "pass": true, "evidence": "..." }`.
- `public_certificate_sha256`: exact existing `.x509.pem` **file** SHA256 map for
  `platform`, `releasekey`, `shared`, `media`, `networkstack`; no private keys.
- `minimum_start_gib`: numeric host/source/output start budgets.
- Optional `emergency_minimum_gib`: same three names, default 10/2/2; host cannot
  be below 10 GiB. Start thresholds must exceed their emergency thresholds.
- `semantic_checks`: reviewed `{project,purpose,head,pass:true,evidence}` records
  for the four historical security fixes and the Gralloc capability guard below.
- `image_checks`: reviewed external script checks with `{name,coverage,argv,
  script_sha256}`; argv starts with `bash` or `python3` followed by the script path.
  The six coverage names are `policy`, `patch_packaging`, `private_compatibility`,
  `health_semantics`, `gms_themes_apps`, `doze_packaging`. All scripts must exit 0;
  their exact hashes are checked before invocation. Root/platform author and
  independently review these producer/artifact checks against final source.

Required semantic purposes:

| Project | Purpose |
|---|---|
| frameworks/base | Fix security vulnerabilities in PduParser.java |
| frameworks/base | Fix potential OOM in PduParser by using stream skip |
| packages/modules/Bluetooth | Remove unused ext_attrs from playerapplicationsetting_cb |
| frameworks/opt/telephony | RESTRICT AUTOMERGE: Fix remote DoS in decodeWapPdu (b/517376969) |
| frameworks/native | SMPTE 2094-50 capability guard |

Source and tooling snapshots are checked again before/after verification. This
replaces subject-window searches and extraction-vs-source mtime assumptions with
reviewed source identity and current installed-producer hashes. Supplemental
checks must assert actual policy/ABI/resource/producers; their coverage labels
alone do not establish correctness.

## Artifacts and comparison preservation

Attempt logs/owner/exit/watchdog/resource/manifests:
`/mnt/wsl/evox/logs/evox16/evox16-attemptNN`, with key records copied to
`C:/XiaomiBuilds/debug/evox16/evox16-attemptNN`.

Reports/raw comparisons/machine-readable checks/hash inventories:
`C:/XiaomiBuilds/compare/evox16/evox16-attemptNN`.

Extraction and temporary unpack/ramdisk/certificate work:
`/mnt/wsl/build/compare/evox16/evox16-attemptNN`. It must be new and is never
recursively deleted by these tools. Author/build9/saved-live-slot references are
read-only. `create-ports.py` records every historical input hash and prepares
local comparison copies; it does not execute a verifier.

Delivery directory:
`D:/WitAquaBuild/out-evox/evox16/evox16-attemptNN`, containing:

- `lineage_klimt-evox16-attemptNN-img.zip` and SHA256SUMS;
- adjacent `lineage_klimt-evox16-attemptNN-flash.bat` and `-flash.sh`;
- README.md, RESULTS.json, COMPARISON-evox16.md and VERIFIED.txt;
- prebuild.xml, postbuild.xml and postverify.xml.

The ZIP must contain exactly the historical 19 fastboot artifacts:
android-info.txt, fastboot-info.txt, boot.img, dtbo.img, init_boot.img, odm.img,
odm_dlkm.img, product.img, super_empty.img, system.img, system_dlkm.img,
system_ext.img, unsparse_super_empty.img, vbmeta.img, vbmeta_system.img,
vbmeta_vendor.img, vendor.img, vendor_boot.img, vendor_dlkm.img.

The verifier preserves the historical author/build9/live layout, AVB, DTB/DTBO,
kernel identity and 888-module CRC comparisons and all 165 legacy check
identities. The sole unresolved kernel symbol is checked by exact name,
`mtk_drm_gateic_set_backlight`. Old OK counts and two FAIL waivers are removed.
USB context matching now accounts for escaped file_contexts syntax; fingerprint
power use is proven via client-attribute membership and platform find allowance.
The retained HIS/Health checks keep current Soong install producer/binary hashes
and processed normal/recovery VINTF semantics.

The marker appears only after the required archive, source, historical and six
Evox16 supplemental image gates pass. Runtime AOD/fingerprint/camera/charging
validation stays pending. The generated flash wrappers have never been run and
require a later separately authorized phone operation; they preserve data and
leave the reboot to the operator.

## Capacity evidence and limits

Measured Evox15 ZIP: 5,630,534,547 bytes (5.244 GiB); expanded entries:
8,712,008,253 bytes (8.114 GiB). Existing extracted images allocate
8,712,048,640 bytes and filesystems 9,604,853,760 bytes (total 17.06 GiB).
Existing author/build9 references allocate 11,674,566,656 / 11,522,400,256 bytes
and are reused. Existing ccache allocates 19,518,447,616 bytes with 20G cap.

Allow about 22 GiB for a new isolated extraction plus conversion/unpack overhead,
and 6 GiB for the delivery ZIP. The verifier checks at least 38 GiB host and
24 GiB output ext4 free immediately before copying/extracting. Source-download
and compilation projections are root's measured gate responsibility; filesystem
holes do not justify assuming zero VHDX growth. Runtime image execution, final
module compilation and a real build have not been tested by the tooling tests.

Run focused tests without an Android build:

```bash
python3 -B /mnt/c/XiaomiBuilds/build-setup/evox/evox16/tests.py
```
