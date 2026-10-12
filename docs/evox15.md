# evox15 controlled test build

Status on 2026-10-12: source changes reviewed and pushed; build running. Image verification and runtime
validation are pending. This build has not been flashed.

## Source and reproduction

- Device: [831aede](https://github.com/iowaz/android_device_xiaomi_klimt/commit/831aede51253a1ca926993557eba7155edc8233a).
- Private proprietary vendor: `74d378be9f0b832f2c83284474a0f5da72062ca2` on `evox`.
- [Pinned manifest](../manifests/snapshots/evox15.xml): generated from the current build's `repo manifest -r`.
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
Normal/recovery service filenames, init configuration and VINTF identity are retained.

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

## Completion gates

The single waiting supervisor runs verification only after build exit 0. Verification covers AVB, partition
layout, DTB/DTBO, all 888 kernel-module CRCs, previous policy/fix gates, the candidate identity, normal/recovery
Health packaging and retained service configuration. Only the two documented legacy false failures are accepted.
A successful marker verifies image contents; a later authorized flash and runtime tests establish phone behavior.
