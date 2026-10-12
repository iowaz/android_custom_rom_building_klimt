# evox15 controlled test build

Status on 2026-10-12: the initial build exited 1 at 10:33 Sao Paulo after 33 minutes, during Kati packaging.
Image verification did not run for that attempt. Attempt 2 started at 11:01 Sao Paulo with the reviewed
service-path repair. It is building and has not been image-verified or flashed. Runtime validation remains pending.

## Source and reproduction

- Initial attempt device: [831aede](https://github.com/iowaz/android_device_xiaomi_klimt/commit/831aede51253a1ca926993557eba7155edc8233a).
- Attempt 2 packaging repair: [a528622](https://github.com/iowaz/android_device_xiaomi_klimt/commit/a528622c4f52e603a1f3cfa4d998b60da6e0e5c9) (build in progress).
- Private proprietary vendor: `74d378be9f0b832f2c83284474a0f5da72062ca2` on `evox`.
- [Attempt 2 manifest](../manifests/snapshots/evox15.xml): generated from the corrected build's `repo manifest -r`.
- [Attempt 1 manifest](../manifests/snapshots/evox15-attempt1.xml): preserves the failed initial attempt.
- [Build script](../build-setup/evox/build-evox15.sh), [verification](../build-setup/evox/verify-evox15.sh),
  [ten new image checks](../build-setup/evox/fix15/check-image.py) and
  [strict report validator](../build-setup/evox/fix15/validate-reports.py).

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
and recovery target commands passed. Full Soong compilation and packaged-image checks are pending.

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
Its actual Soong/Kati and image checks are pending. The supervisor handles one build and verification at a time;
further retries follow diagnosis and review rather than a blind loop.

## Completion gates

The single waiting supervisor runs verification only after build exit 0. Verification covers AVB, partition
layout, DTB/DTBO, all 888 kernel-module CRCs, previous policy/fix gates, the candidate identity, normal/recovery
Health packaging and retained service configuration. Only the two documented legacy false failures are accepted.
A successful marker verifies image contents; a later authorized flash and runtime tests establish phone behavior.
