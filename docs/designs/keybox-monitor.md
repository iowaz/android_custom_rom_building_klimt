# Scheduled TrickyStore keybox monitoring

Implemented as owner-requested `personal` patches for `frameworks/base` and
`packages/apps/Evolver`, carried by the klimt device patch bundle. The source baseline is
the 20261112.2 checkout. The first implementation shipped in 20261113; the owner confirmed boot and testing. The requested follow-up is recorded in [20261113.2](../20261113.2.md).

## Operation

Evolver > TrickyStore has an opt-in **Automatically check and recover keybox** switch.
It defaults off; the default interval is one hour. Choices are 15, 30 and 45 minutes,
and 1, 4, 12 and 24 hours. The page shows the next check and the existing status row shows
the last result and time. Tapping that row checks immediately.

Enabling schedules an immediate check. Subsequent exact elapsed-realtime wakeup alarms
are anchored to scheduled times, including standby; network completion is not guaranteed
when offline. Changing the interval starts the new interval from the change. Manual checks
reset the next deadline to completion plus the selected interval, including offline checks. Reboot restores the saved deadline after unlock, performing one
overdue check instead of replaying missed checks. Wall-clock changes update the displayed
deadline without changing elapsed-time scheduling.

Monitoring pauses while TrickyStore is off, while device RKP is enabled, or when no
keybox is installed. Explicit deletion leaves it waiting for a new import/fetch. Disabling
monitoring cancels pending automatic work and prevents a late replacement from being installed.

Notifications follow one of three choices: every completed check; only expired, revoked or
suspended results regardless of recovery outcome; or only those results whose recovery fails
(the default). Manual status checks follow the same choice while monitoring is enabled.
Each qualifying check posts one final notification. Recovery policy uses the original verdict
even when a valid replacement is installed. Expiring-soon remains valid until expiry, and an
unknown/offline check never asserts a new valid result. Reports retain the previous confirmed
status and timestamp for the same payload. Notifications open TrickyStore, conceal content on
the lock screen and respect Android channels. UI and notification resources include en-US
and pt-BR. The first release's two-hour interval migrates to four hours.

Upstream's existing daily check is a screen-onResume trigger. When monitoring is enabled,
it follows the system service's persisted deadline; otherwise it retains the daily behavior.
The background alarm remains necessary while Settings is closed. The same serialized
operation performs foreground and background checks. Foreground polling preserves the
checking label and progress indicator until the operation completes.
## Validation and recovery

The shared inspector checks the framework keybox loader's structural/private-key checks,
each RSA/ECDSA certificate chain, signatures, trust anchors, signing-certificate validity
periods and serials against Google's public status list. A certificate's expiry is distinct
from revocation. Trust anchors retain upstream's public-key matching rule for reissued roots.
An unavailable, malformed or unrecognized status response cannot qualify a replacement as
valid. Reports are bound to a SHA-256 hash of the decoded payload.

Replacement uses the URL previously used by the manual **Fetch official keybox** action:
`https://gitea.com/Evolution-X/keybox/raw/branch/main/keybox.xml`.
HTTPS redirects are bounded to three. No alternative keybox provider or custom URL is added.

Before replacement, the previous payload, source and fetch timestamp are written to one
rolling private backup: `/data/system/trickystore/keybox-recovery-backup.json` (0600, in a
0700 directory). A backup failure prevents installation. A rejected, unchanged unusable,
expired or revoked candidate leaves the current payload in place. Failed recovery retries
at the selected interval; the legacy 24-hour failed-fetch cooldown does not suppress it.

Manual check/fetch/import/delete and background fetches run through one asynchronous
system-service controller. Successful fetch/apply saves the payload, official-source marker
and timestamps, clears failed-fetch state, then force-stops the same Google package group as
the existing manual action. An activation failure is reported separately. Automatic fetching
does not clear app data or reboot. The foreground manual-import wipe confirmation remains
an explicit UI choice.

Imports and deletes supersede pending automatic work. Network work is off the Binder and
system Handler threads; each cycle has a 60-second watchdog and bounded wake lock. A bounded
two-thread executor contains an uninterruptible timed-out network operation. Hash/generation
guards reject stale results before installation. The selected schedule owns periodic keybox
work while enabled; the PIF refresh remains independent. When monitoring is off, the existing
hourly official refresh delegates to the shared validated fetch path and preserves user imports.

The new hidden `requestTrickyStoreKeyboxOperation` Binder method is appended to
`IActivityManager` to retain existing transaction numbers. It requires the system UID and
`WRITE_SECURE_SETTINGS`; responses contain status metadata, not signing keys. Monitoring
settings and results use the existing Settings.Secure storage model. No public SDK API is added.

## Validation performed

- Generated the modified AIDL interface with the actual Android AIDL compiler.
- Compiled the new contract, inspector, scheduler, controller, AxSpoofManager and
  ActivityManagerService with the existing Android classpath/system modules in scratch output.
- Compiled both changed Kotlin/Compose files with the existing Kotlin and Compose compilers.
- Compiled the new XML resources with AAPT2. Temporary resource symbols were used for the
  focused Java/Kotlin compilation; this is not a full resource link or ROM build.
- Passed 22 JUnit tests using generated non-production keys: both algorithms, unordered chains,
  leaf/intermediate expiry, revocation/suspension, both serial encodings, untrusted/mismatched
  keys, malformed/offline status data, hash binding, all intervals, drift, reboot/clock changes,
  missed ticks and stale-write rejection. The host adapter replaces Android native logging;
  it does not bypass the real framework keybox loader or certificate validation.
- Exported the patch series with the device export tool, which replays it twice and checks
  deterministic heads and final trees. Existing unrelated patch records remain unchanged.

Local compiler and JUnit logs, source hashes and the patch manifest are retained under
`D:\android_rom_building\diagnostics\features\keybox-monitor\20261113`.

## Remaining acceptance

Run the normal clean-staging ROM pipeline for the next requested build, with both patches
applied together and the new bases included in its frozen manifest. Do not reuse the
20261112.2 image-verification result for the changed source.

After an authorized installation, test two real 15-minute cycles awake and in Doze;
enable/disable and interval changes; reboot restoration; offline/reconnect behavior; channel
visibility and notification navigation; and expired/revoked replacement success/failure.
Confirm private backup permissions and unchanged app/card state. Host tests do not validate
AlarmManager delivery, notification rendering, SELinux file access or Google-process activation
on the phone. The subsequent [20261113 build](../20261113.md) passed full image verification and the 15
packaged feature checks. Monitor timing and recovery still require phone validation.

Passing public certificate checks does not establish a successful Play Integrity or Wallet
verdict. Those are separate runtime outcomes.


## Revision checks and review

[20261113.2](../20261113.2.md) records the complete revision and the Claude Opus 5.5 Medium
review/disposition. The service owns a dedicated Handler and bounded cleanup executor. The
read-only operation engine is tested independently of state writes. Unchanged legacy hourly
refresh downloads only the mirror and preserves the last status; changed candidates receive
fresh validation. Explicit structurally valid imports work offline and then receive the
existing follow-up check. Invalid imports/worker rejection preserve the installed verdict.
Incomplete Google-process reload is distinguished from failed installation.

A pre-inspection timeout/rejection is not a completed check and posts no status notification.
It returns an error to a foreground caller and preserves the previous verdict/deadline.
Twenty-two host tests and final focused compilation pass. Real service/UI lifecycle and phone
timing/recovery acceptance remain required before an upstream submission.
