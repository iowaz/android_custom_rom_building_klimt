# Keybox monitor review disposition

Reviewer: Claude CLI `claude-opus-5-5`, Medium, read-only. The review covers the shipped
feature and this revision. The actual CLI journal and model-usage result confirm the model.
The original findings are retained in `CLAUDE_REVIEW.md`; this file records our decisions.

## Accepted and fixed

- **H1:** null-safe payload hashing and inspection. A null/empty regression case passes.
- **M1:** the legacy hourly worker downloads the mirror first, skips unchanged content before
  loading roots/status data, and validates only a changed candidate. It does not overwrite the
  current verdict/daily timestamp unless installation succeeds. Operation-engine tests assert
  one mirror request and no roots/status requests for unchanged content, and one status request
  for a changed candidate.
- **M2:** TLS cleanup has its own bounded executor and is skipped with no active connection.
  The spare validation worker is available after a timed-out DNS request. A worker rejection
  cannot overwrite the installed verdict or move the manual deadline. The monitor also owns
  a dedicated HandlerThread, so AxSpoofManager's bounded PIF waits cannot delay its alarms,
  timeouts or Settings callbacks.
- **M4:** Settings counts pending operations instead of silently discarding user imports/deletes.
  The service serializes them. Screen-resume checks are suppressed while the picker is open.
- **M5:** the service publishes only an actual inspection of the installed payload or a successful
  commit. Invalid imports and rejected workers preserve the current verdict and check timestamp.
  Failed import/legacy-refresh cases are exercised through the read-only operation engine.
- **L1:** localized failure categories distinguish invalid/unverified files, disabled/RKP state,
  busy work, changed configuration, storage failures and incomplete Google reload. Manual
  verification that replaces a keybox gives a success toast even with monitoring off.
- **L2:** keybox import/fetch/delete/status controls are hidden while device RKP is selected.
- **L3:** deletion catches provider-write failures and attempts to restore the previous payload,
  source and fetch timestamp. Failure returns to Settings rather than escaping on the Handler.
- **L4:** a valid installed keybox with an incomplete Google reload has a distinct
  `reload_incomplete` outcome and localized notification/toast. It qualifies for the default
  alert because runtime activation is incomplete; the text accurately says installation succeeded.
- **L5:** failed FETCH operations update the existing failed-fetch cooldown. The silent bootstrap
  flag suppresses foreground failure/success toasts. Automatic CHECK recovery retains its chosen
  interval, rather than inheriting the legacy 24-hour cooldown.
- **L6 (duplicate import work):** successful imports establish the next deadline before the
  settings observer runs; the existing explicit follow-up check resets it again on completion.
- **L7:** notification deadlines include a date and honor Android's 12/24-hour setting. A paused
  monitor reports that it is paused instead of displaying a stale or epoch deadline.
- **L9:** keybox operation controls are restricted to the owner; AMS handles unavailable service
  initialization explicitly. The Binder system-user restriction is retained.
- **L10:** the exception path verifies that the cycle is still current before replying, so a
  failure after completion cannot deliver a second callback.

The operation engine was separated from state writes to make hourly/manual/recovery decisions
testable and reduce the controller's coupling to network details. Keybox imports are also bounded
before reading them into Settings memory. Candidate validation reads the current clock after
network operations, rather than accepting an expiry verdict captured at the start of a request.

## Deliberate behavior retained

- **M3:** an explicitly deleted/missing keybox pauses opt-in monitoring until a manual import or
  fetch. This was an explicit property of the first implementation, avoids immediately undoing
  Delete, and is stated on screen. Monitoring replaces known expired/revoked/suspended keyboxes;
  it does not proactively rotate a still-valid keybox on the legacy hourly clock. When monitoring
  is off, legacy bootstrap/proactive refresh remains available. A separate bootstrap-vs-explicit-
  deletion setting can be proposed upstream if desired; it is not silently introduced here.
- **L6 (initial timing):** immediate enable and one overdue check after unlock remain intentional.
  An arbitrary initial delay would change the chosen schedule. Offline results are UNKNOWN;
  the default notification policy does not alert merely for an unknown result.
- **L8:** retain one private rolling backup, as designed, instead of expanding private-key history
  or adding an unrequested restore flow. A separately retained last user-imported backup and a
  privileged restore flow are possible future work with explicit retention/validation semantics.
- **Endpoint:** retain the existing manual Evolver official endpoint, centralized in the inspector.
  The legacy Ax URL differed; both local paths now intentionally use the manual action's provider.
- **Fresh status required:** a replacement must pass fresh validation. An unverifiable first-install
  keybox is not installed merely because there is no existing payload. This is the requested
  validated-recovery contract, with manual retry and an explanatory failure result.
- **Offline cache/serial spelling:** retain the current conservative UNKNOWN plus last-confirmed
  display and upstream-compatible serial spellings. No cached response establishes a newly VALID
  replacement. Serial canonicalization can be agreed with maintainers in the upstream review.

## Upstream readiness and limits

The SystemUI AOD and PackagePartitions changes in the full framework comparison are older,
separate personal patches; all 17 earlier patches remain unchanged. They must not be included
in a future PR for this feature. The proposed PR should isolate/squash only the keybox feature
commits and use generic resource-file names. The unused sync parameter, wildcard static import
and intermediate status publication were removed. New logic is separated into a read-only
operation engine, shared contract, inspector, scheduler and state-owning controller.

An appended private Binder method, upstream root/validation changes and bootstrap/refresh
changes still require review during a rebase. Source pinning and deterministic device patch
replay fail closed when patches no longer apply. Hardware timing, notifications, provider
failure injection and full Handler/Settings lifecycle tests remain acceptance work; the focused
host tests do not claim to validate Android service scheduling or UI rendering.

## Follow-up review

The same Claude Opus 5.5 Medium session re-reviewed the corrected code. It found no new
runtime-critical service/UI defect and accepted the deliberate behavior choices. The full
follow-up is retained in `CLAUDE_FOLLOWUP.md`. We also addressed all seven follow-up findings:

- **B1:** include every new source/resource in Git's review diff and explicitly stage the engine
  for the feature commit. Deterministic patch replay must include `KeyboxOperations.java`.
- **R1:** when a post-reply resync fails, resume draining an idle queue without replying twice.
- **R2:** deletion's rollback block contains only the state transaction. Reply and subsequent
  scheduling/queue work occur afterwards; follow-on errors cannot restore a completed deletion.
- **R3:** resume/bootstrap checks return early for secondary users. A missing keybox uses the
  legacy bootstrap only with monitoring off; it does not repeatedly check a paused deadline.
- **R4:** unavailable/unverifiable official candidates have their own localized error category,
  separate from invalid files chosen by the user.
- **R5:** hourly work rechecks monitoring/user ownership before committing. Both dequeue and
  completion use one policy helper; a regression case covers changed ownership/monitoring.
- **R6:** an installed import with an incomplete reload retains its follow-up verification/wipe
  prompt flow and shows the accurate reload warning.
- **R7:** structurally valid explicit imports do not depend on roots/status network requests.
  They install first, then use the existing follow-up check. Automatic official replacements
  still require fresh validation. A regression case fails if import touches the network.

The dead fetching-notification branch/resource was removed. Final focused compilation and
all 22 host tests pass. A pre-inspection rejection/timeout does not count as a completed check:
it preserves the old verdict/deadline and posts no status notification, even in every-check mode.
The follow-up corrections were reviewed by Codex and tested; they were not sent through a
third Claude pass. Android Handler/Settings/UI and real-device acceptance remain explicit limits.
