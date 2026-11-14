# TrickyStore keybox monitor review (first shipped version and current revision)

I didn't modify, build or run anything. I also couldn't save a plan file: no write or plan-exit tool was available in this session. I read the current snapshots, the upstream originals, both full-feature diffs, both revision diffs and the logs. javac shows only one existing AMS deprecation warning, kotlinc printed nothing, and 15 host tests pass.

**Verdict:** the current revision fixes most of what was wrong in the first one. It is still not ready to build-and-ship. One defect crashes Settings, and several medium-severity defects affect default-off users, retries and serialization.

## Revision delta (first → current)

The revision correctly fixes these first-release problems:
- It replaces 2h with 4h and adds 24h; the 120 → 240 migration happens in `sync()`.
- The upstream onResume check is restored. In the first version it returned early when monitoring was on.
- The loading state now survives the 1.5 s polling refresh.
- The "fetching" notification is gone, so a check posts one notification instead of two.
- The three notification policies work and use the original verdict.
- Notification text is localized instead of showing raw failure codes.

Most findings below were present in both versions.

## HIGH

**H1 – Settings crashes when the keybox setting has never been written.**
- **Where:** `current/frameworks/base/core/java/android/security/trickystore/KeyboxMonitor.java:50` calls `TrickyStoreService.decodeKeybox(raw)` before checking for null. `TrickyStoreService.java:435` then calls `payload.trim()`.
- **Caller:** `TrickyStore.kt:565-566` passes `Settings.Secure.getString(..., KEYBOX_KEY)`, which is `null` on a fresh install whose first official fetch hasn't succeeded yet (offline first boot, status endpoint unreachable), or after `settings delete`.
- **Failure:** `refreshMonitorStatus()` runs from `onCreate`/`refreshStatus` and the polling loop, so the TrickyStore page throws an NPE as soon as it opens.
- **Fix:** in `keyboxHash`, treat `null` as `""` before decoding, or make `decodeKeybox` null-safe. Add a `keyboxHash(null)` host test.

## MEDIUM

**M1 – The legacy hourly fetch is now much heavier for default-off users and overwrites status.**
- **Where:** `AxSpoofManager.java:618-620` → `TrickyStoreKeyboxMonitor.refreshOfficialIfUnmanaged` (187-195) → `work()` (230-262) → `finishInternal` → `publish` (349).
- **Failure:** upstream's hourly job downloaded only `keybox.xml`. Now every hour, with monitoring off, it:
  - inspects the installed keybox (one full Google status-list download),
  - inspects the candidate (a second status-list download), even when the candidate is identical (the hash comparison at 259 comes after the inspection),
  - writes `REPORT`/`LAST_STATUS`/`LAST_CHECK`.

  As a result:
  - Users who never opted in pay roughly 48 status-list downloads a day on metered data.
  - Any offline hour turns a confirmed VALID into "Unable to verify keybox".
  - `LAST_CHECK` is always under 24h old, so upstream's daily onResume check never fires.
- **Fix:** for `hourly` requests, compare the candidate hash first and return early if unchanged. Validate only the candidate. Don't call `publish()` unless the keybox was actually replaced.

**M2 – After any timeout, the next queued request fails with `WORKER_BUSY`.**
- **Where:** `end()` at `TrickyStoreKeyboxMonitor.java:415` submits `cycle::disconnect` to `mWorkers` (max 2 threads, `SynchronousQueue`). `drain()` at 226-227 runs immediately afterwards.
- **Failure:** after a `CYCLE_TIMEOUT`, thread A is still stuck in DNS, the very case the second thread exists for. `end()` hands the disconnect task to thread B, then `drain()`'s `submit` is rejected and the next request finishes as `WORKER_BUSY`.
  - A manual Check returns failure without ever validating.
  - It still re-anchors the schedule at 344-348.
  - It overwrites `REPORT` with UNKNOWN.
  - The same race can hit intermittently after normal completions, when the old worker hasn't returned to polling yet.
- **Fix:** don't run disconnects on `mWorkers`. Skip the disconnect when `connections` is empty (the normal case), or use a separate small executor. Don't re-anchor or publish on `WORKER_BUSY`.

**M3 – With monitoring enabled and no keybox installed, nothing ever installs one.**
- **Where:** `refreshOfficialIfUnmanaged` skips when `enabled()` (189); `autoFetchIfNoKeybox` skips when `ui.monitorEnabled` (`TrickyStore.kt:597`); the monitor itself is ineligible with an empty keybox (`eligible()` 122).
- **Failure:** the user enables monitoring, then deletes the keybox (or the bootstrap fetch failed). Upstream's hourly/bootstrap and on-resume auto-provisioning are now all off, so the device stays without a keybox until the user taps Fetch.
  - Enabling monitoring also stops upstream's proactive replacement of a still-valid official keybox when the mirror changes.
- **Fix:** gate the legacy path on "monitoring is actively scheduling" rather than `enabled()`. Keep it running when no keybox is installed, or let the monitor fetch when the keybox is MISSING and the source isn't `user`. Treat the "stop proactive refresh" part as a product decision and document it.

**M4 – Settings silently drops Import and Delete while any other operation is in flight.**
- **Where:** `requestKeyboxOperation` returns at `TrickyStore.kt:500` when `isCheckInProgress` is set. The Import/Delete actions (`TrickyStoreContent.kt:170-187`) are never disabled.
- **Failure:** returning from the document picker runs `onResume` (361-381). If the daily check is due (always true right after a Delete, which sets `LAST_CHECK=0`) or the silent auto-fetch starts, a CHECK/FETCH begins. The picker's IO read then finishes and the IMPORT is discarded with no toast. Upstream's import wasn't gated by this flag.
- **Fix:** user-initiated operations should always be sent, since the server already serializes them, or at least show a "busy" toast. Alternatively, track pending operations with a counter instead of a boolean.

**M5 – A failed Import (or `DISABLED`/`WORKER_BUSY`) overwrites the installed keybox's verdict with UNKNOWN.**
- **Where:** `work()` 234-235 calls `finish(cycle, null, null, "INVALID_KEYBOX")`. `finishInternal` 312/340 then builds an UNKNOWN report and `publish()` writes it under the old keybox's hash.
- **Failure:** the user picks a wrong file. A still-valid installed keybox now shows "Unable to verify keybox", and `LAST_STATUS`/`LAST_CHECK` are rewritten.
- **Fix:** only publish when the current keybox was actually inspected (`cycle.observed != null`) or a commit happened. Reply to the caller with the failure, but don't publish.

## LOW (concrete, limited impact)

**L1 – One generic error message for every failure, and no feedback after a replacement.**
- `TrickyStore.kt:513` shows "Unable to complete… check your connection" for `INVALID_KEYBOX`, `DISABLED`, `BUSY`, `STATE_CHANGED` and recovery failures alike. Upstream showed the actual problem.
- A manual Check that replaces the keybox with monitoring off produces no toast or notification at all; `result.recovery == "replaced"` is ignored.
- **Fix:** map failure codes to a few localized messages, and add a "replaced" toast.

**L2 – Import fails under device RKP with a misleading message.**
- Import stays visible when RKP is on (`TrickyStoreContent.kt:170-178`), but `drain()` 210-212 always rejects it as `DISABLED`.
- **Fix:** hide or disable Import under RKP, or show a specific RKP message.

**L3 – A failed settings write during Delete can crash system_server.**
- In `drain()` 214-217, `put(KEYBOX/SOURCE/LAST_FETCHED)` throws `IllegalStateException` when the settings write fails. Unlike `finish()`, nothing catches it, so the exception lands on the system_server handler and crashes it (soft reboot).
- **Fix:** wrap the DELETE path the same way `finish()` is wrapped.

**L4 – A successful replacement can be reported as a failed recovery.**
- At 324, if any force-stop throws, the code reports `ACTIVATION_FAILED` and recovery "failed", with "check your connection" text, even though the new keybox is installed. Under the default policy that produces a misleading failure alert.
- **Fix:** add a separate "installed, reload incomplete" outcome.

**L5 – Silent auto-fetch failures don't set the 24h cooldown.**
- `FAILED_FETCH` is written only for `hourly` requests (337-339). With no keybox and no network, every resume runs `autoFetchIfNoKeybox` → FETCH → failure toast plus a spinner.
- Note that `fetchOfficialKeybox(silent)` ignores the `silent` argument.
- **Fix:** record the cooldown for Settings FETCH failures too, and honour `silent`.

**L6 – Immediate checks at awkward moments.**
- `restoreDelay` returns 0 when `NEXT` is in the past (143-149). This triggers a check:
  - right at unlock after a long reboot, before networking is up, giving a spurious UNKNOWN or "recovery failed" notification;
  - immediately when monitoring is turned on (`NEXT` was cleared);
  - when a keybox reappears, alongside Settings' own follow-up check after an import (two checks, two notifications under "every check").
- **Fix:** use a minimum initial delay, or a single deferred first run after unlock.

**L7 – Stale or ambiguous "Next check" time.**
- While monitoring is enabled but paused (no keybox), `NEXT` isn't cleared. A manual check's notification then shows a stale or past time (463-464), and onResume treats it as due.
- `DateFormat.getTimeInstance()` shows no date, which is ambiguous for 12h/24h intervals, and ignores the user's 24-hour setting. Use `android.text.format.DateFormat` with a date.

**L8 – Only one backup slot.**
- `keybox-recovery-backup.json` is overwritten on every replacement or import (`backup()` 386-400). After two recoveries the user's original keybox is gone, and there is no restore path in the UI.
- **Fix:** keep the last user-sourced backup separately.

**L9 – Secondary users get unexplained failures.**
- In secondary users, Settings runs as uid 10xx1000, so every Check/Fetch/Import/Delete fails the AMS check (`ActivityManagerService.java:21035-21044`), with the generic toast.
- `getKeyboxMonitor()` is also null when `systemReady` bailed out (`AxSpoofManager.java:177-179`), which causes an NPE.
- **Fix:** hide the controls when `!monitorOwner`, and null-check in AMS.

**L10 – A double callback is possible.**
- If an exception is thrown after `end()`/`reply()` inside `finishInternal`, `finish()` (296-299) replies a second time.
- **Fix:** keep a `replied` flag on the cycle.

## Behavior changes to decide on (not defects as written)

- **Endpoint unified:** the hourly path now uses `gitea.com/Evolution-X` (`KeyboxInspector.java:41`) instead of upstream `AxSpoofManager`'s `git.evolution-x.org/EvoX` (`upstream/.../AxSpoofManager.java:101`). Confirm which one is "the existing official EvoX endpoint".
- **First install now needs Google's status service:** with no keybox installed, an unreachable status endpoint blocks installation (`CANDIDATE_UNKNOWN`). Upstream installed anyway ("anything beats no keybox"). Regions that block googleapis would never get a keybox.
- **Offline revoked-serial cache dropped:** the Settings-side cache (`CACHED_OFFLINE`) is removed, so offline checks now give UNKNOWN. That matches "never newly VALID", but it is a visible change.
- **Serial matching:** checking both decimal and hex spellings can, rarely, match an unrelated entry. This was already in upstream.

## Requirement checks that passed

- Default off, default 1h, default notification policy "recovery failed", interval list, and 120 → 4h migration.
- Exactly one notification per completed CHECK, with the original verdict kept via `cycle.observed`.
- UNKNOWN never shown as VALID. The quiet channel is used only for a positive result; a missing status list or roots fall back safely.
- Manual check re-anchors the schedule, including offline results.
- Generation checks and hash checks block stale or late commits. Import/Delete cancel automatic work. Hourly work skips user-sourced keyboxes at dequeue time and is serialized with manual operations.
- Wake lock bounded at 65 s. Deadlines enforced per request. HTTPS-only redirects.
- Backup is 0700/0600 and written atomically. No keybox material in logs or reports, only a hash.
- en-US and pt-BR strings are complete and match each other in both repos. Two notification channels, `VISIBILITY_SECRET`.

## Test gaps

All 15 tests exercise pure helpers. Nothing tests the `TrickyStoreKeyboxMonitor` state machine. Needed:
- null/empty `keyboxHash`;
- worker saturation after a timeout;
- hourly-path network calls and publish side effects;
- notification count per path (automatic, manual, replaced, timeout, cancelled);
- rollback when the SOURCE write fails;
- DELETE while hourly work is in flight;
- the `sync()` transition table (enable, interval, RKP, unlock, keybox appearing);
- a Settings UI test for an Import arriving during a check.

## Upstream PR readiness and maintainability

**Not ready as-is.**

- **Unrelated changes in the full-feature diff:** SystemUI charging-animation/AOD changes and a `PackagePartitions` fingerprint change (adds `ro.build.date.utc`, so every build counts as an upgrade). Each needs its own commit or PR.
- **Device-specific naming:** the `klimt_*` resource file names in frameworks and Evolver.
- **Style:**
  - several statements per line;
  - wildcard `import static`;
  - unused `sync(boolean unused)` parameter;
  - settings keys duplicated as string literals instead of `Settings.Secure.SPOOF_*` constants;
  - a dead `ts_monitor_fetching` notification branch, plus an intermediate `publish("fetching")` (247-252) that still writes `LAST_CHECK` for checks that may never finish.
- **Things upstream could change that break this patch:**
  - The Evolver diff deletes about 600 lines of upstream revocation and roots logic, so any upstream fix there (new fallback roots, status parsing) conflicts or is silently lost.
  - The appended `IActivityManager` method will conflict on every upstream AIDL addition.
  - `keyboxHash` depends on `decodeKeybox`'s exact behaviour, and `drain()` depends on `KeyBoxManager.validate` semantics.
  - Changes to `AxSpoofManager`'s refresh cadence or bootstrap would conflict. The bootstrap retry now never sees the asynchronous fetch finish, so it always retries.
  - A rename of the upstream keybox endpoint would break fetching.
  - The monitor shares the `AxSpoofManager` handler. Its `runBounded` fingerprint crawl can block that handler for 20 s per step, delaying alarms, timeouts and Settings callbacks.

**Recommended order before building:** fix H1, M1, M2 and M5 first, then decide on M3 and the endpoint question.
