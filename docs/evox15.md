# evox15 controlled test build

Status on 2026-10-12: the initial build exited 1 at 10:33 Sao Paulo after 33 minutes, during Kati packaging.
Image verification did not run for that attempt. Attempt 2 started at 11:01 Sao Paulo with the reviewed
service-path repair and completed at 11:51 with exit 0 (50 minutes 29 seconds). Image verification passed.
It has not been flashed; charging and camera runtime validation remain pending.

## Source and reproduction

- Initial attempt device: [831aede](https://github.com/iowaz/android_device_xiaomi_klimt/commit/831aede51253a1ca926993557eba7155edc8233a).
- Attempt 2 packaging repair: [a528622](https://github.com/iowaz/android_device_xiaomi_klimt/commit/a528622c4f52e603a1f3cfa4d998b60da6e0e5c9) (build and image verification passed).
- Private proprietary vendor: `74d378be9f0b832f2c83284474a0f5da72062ca2` on `evox`.
- [Attempt 2 manifest](../manifests/snapshots/evox15.xml): generated from the corrected build's `repo manifest -r`.
- [Attempt 1 manifest](../manifests/snapshots/evox15-attempt1.xml): preserves the failed initial attempt.
- [Build script](../build-setup/archive/pre-evox16/build-evox15.sh), [verification](../build-setup/archive/pre-evox16/verify-evox15.sh),
  [ten new image checks](../build-setup/archive/pre-evox16/fix15/check-image.py) and
  [strict report validator](../build-setup/archive/pre-evox16/fix15/validate-reports.py).

The vendor binary remains in the private vendor repository. The public device tree's guarded extraction
helper reproduces the camera modification from the exact stock input and refuses an unknown input.
All the previous image checks and their reference-image prerequisites still apply.

## Charging estimate

On evox14 with the Samsung charger connected, battery current was about -2,406,000 uA at 4.07 V and charge
level rose from 61% to 71%. The average-current node stayed at 4,500 uA, while time-to-full reported
1,173,120 seconds (13 days, 13 hours, 52 minutes). BatteryStats used exactly that estimate.
After physically unplugging, current became +132,000 uA and status became Discharging, but the average
remained 4,500 uA and the time-to-full value persisted. This confirms reversed current polarity and
unreliable average/time telemetry. No effective inversion property was identified in this configuration.

The device-local Health service normalizes both the current getter and HealthInfo snapshot. It guards
INT_MIN overflow, exposes average current as unsupported (zero in the snapshot), and sets time-to-full to -1.
BatteryStats then falls back to measured charge-level step durations. It can initially show no estimate until
at least one valid duration is available. Charger power, thermal limits and charging control are unchanged.
The naming repair gives normal/recovery binaries and RC/XML files unique Klimt filenames. Init executable
paths and factory/meta imports follow those names; service identities, permissions and VINTF HAL identity
are retained, and the vendor binary receives the existing Health execution label.

Independent review, current-sign/boundary checks and offline compilation with the existing Android vendor
and recovery target commands passed. Full Soong compilation, linking and packaged-image checks now pass for normal and recovery Health.

## Camera watchdog

The captured immediate transition was video 0x8004 to photo 0x9002 after recording/lens actions. MiaNode-Init
waited for HIS's global session-lifetime gate while the old adaptor flush retained 24 outstanding requests.
Equivalent stacks appeared before evox14. The lost-callback cause and complete old-session recovery remain open.

The candidate extends only photo mode 0x9002 to HIS's existing 0x9200 timed acquisition fallback (about
1.2 seconds). If the gate remains occupied, HIS is disabled for that node and existing graph pruning is used.
Other modes, lock ownership and the watchdog remain intact. This bounds initialization; it does not repair
the old hardware flush. Correct photo output and repeated session recovery still require device testing.

- Packaged candidate SHA-256: `4a4fe8a0b6ca0bcc57b5045da37ca6ad64e52f4ee889a2dcefde23d09836329a`.
- Distinct deterministic BuildId: `30ee8f4f63103efcd6f66558e345682c`.

Exact-byte/branch, ELF 4 KB/16 KB mapping, 65,536 mode-routing and local Bionic loading checks passed.
Independent review approved a controlled test build. Actual camera namespace loading, lens/recording transitions,
watermark photos, stabilization and repeated recovery are pending; camera property-reader denials remain open.

## Packaging failure and repair

The initial attempt used unique module names but retained generic `.example` binary stems. Soong generated
install rules for both the generic service and the Klimt service at the same target path. Kati rejected
`vendor/bin/hw/android.hardware.health-service.example` as an overridden command; this was a build
configuration error, not a freeze or disk-watchdog stop. Source analysis completed before the failure.

The repair removes the shared stems, uses `.klimt` and `.klimt_recovery` binary names, and gives their init
and VINTF files matching unique names. The existing Health domain and HAL identity are preserved. Generic
modules and standalone chargers remain overridden in the product. The image checks also require the generic
binaries to be absent from the extracted package. Both attempt snapshots are preserved above.
The user authorized repairs and build retries until completion; attempt 2 uses the reviewed follow-up commit.
Actual Soong/Kati generation and all image packaging checks passed on attempt 2. The supervisor handles one build and verification at a time;
further retries follow diagnosis and review rather than a blind loop.

## Completion gates

The single waiting supervisor runs verification only after build exit 0. Verification covers AVB, partition
layout, DTB/DTBO, all 888 kernel-module CRCs, previous policy/fix gates, the candidate identity, normal/recovery
Health packaging and retained service configuration. Only the two documented legacy false failures are accepted.
A successful marker verifies image contents; a later authorized flash and runtime tests establish phone behavior.

## Verified image

- Archive: `lineage_klimt-evox15-img.zip` (5,630,534,547 bytes).
- SHA-256: `63982b332d7cca2539ccbbb25f8e057b7ee656d1cf2e9fe02c4c14748223f90a`.
- Build exit: 0; duration: 50 minutes 29 seconds; completed 2026-10-12 11:51 Sao Paulo.
- Image checks: AVB chain, partition layout, DTB/DTBO, 888 kernel-module CRCs, prior policy/fix gates,
  and all ten new Health/camera package checks passed.
- Fix checks: 163 OK results; only the two previously documented legacy false failures remain.

This verifies the built image and source selection. It does not establish camera recovery, photo/video output,
stabilization or charging estimate accuracy on the phone. Those tests require a separately authorized flash.

## Verifier metadata repair

The first verification run rejected two source-selection checks because `module-info.json` was a developer
cache from 2026-10-09; the `updatepackage` target did not refresh it. A third byte comparison rejected the
VINTF build tool's legitimate input comment and root schema-version serialization (1.0 to 9.0).

The reviewed correction follows each unique current Soong module/install producer, its exact source and
configuration paths, and producer-to-built-to-packaged binary hashes. Normal and recovery VINTF files must
match processed build output byte-for-byte and preserve the complete source HAL definition. Only root schema
version, comments and insignificant formatting are normalized; unexpected processing instructions are rejected.
All ten gates remain, and the legacy failure whitelist is unchanged. Revalidation passed on the same extracted
image without rebuilding or re-extracting it; the original failed-verifier reports were preserved locally.

[Negative verifier checks](../build-setup/archive/pre-evox16/fix15/verifier-negative-tests.py) exercise 14 module-provenance
positive/negative cases and reject nine changed XML definitions, including duplicate or wrong producers,
changed Health versions/instances, added HALs/attributes and processing instructions.
