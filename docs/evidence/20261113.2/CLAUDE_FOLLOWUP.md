# Re-review of the corrected keybox monitor

**Verdict:** one packaging blocker, then a short list of low-severity defects. Several of those were introduced by the fixes themselves. I found no new runtime-critical defect in the service or UI code. The dispositions are accurate except where noted below.

I read the current snapshots, `KeyboxOperations.java`, both updated full and revision diffs, the tests and `REVIEW_DISPOSITION.md`. I didn't edit, build or run anything.

## Blocker

**B1 – `KeyboxOperations.java` is missing from both framework diffs.**
- It exists in `current/` and in `source-sha256.json`, but neither `frameworks_base-full-feature.diff` nor `frameworks_base-revision.diff` contains a `diff --git … KeyboxOperations.java` section. Both diffs do contain the calls to it: `TrickyStoreKeyboxMonitor.java:269` and the tests at `KeyboxMonitorTest.java:130-173`.
- This is almost certainly an untracked file that `git diff` leaves out.
- **Failure:** anything built or replayed from these diffs or from the commit fails to compile. The passing builds and tests were done against the working tree, so they don't show this.
- **Fix:** `git add` the file, regenerate both diffs, confirm the file appears in them, and recheck the SHA pinning.

## Remaining defects (all low, none blocking)

**R1 – A failure after `end()` in `finish()` leaves the queue stuck.**
- **Where:** `TrickyStoreKeyboxMonitor.java:308`. If `finishInternal` throws after `end()` and the reply (for example in `sync()` at 379), `mCurrent` is no longer this cycle. The code returns without calling `drain()`.
- **Failure:** requests already queued (say, an import submitted during a check) are never started and never answered. With the new counters, Settings then shows "Checking…" indefinitely and keeps the Check row disabled until the fragment is recreated.
- **Fix:** in that branch, call `drain()` when `mCurrent == null`. Better still, put `sync()`/`drain()` after the reply in a `finally` block.

**R2 – Delete runs follow-on work inside its rollback `try` block.**
- **Where:** `TrickyStoreKeyboxMonitor.java:238-255`. The `sync()` call at 247 can call `drain()` (175) and start the next queued cycle inside the `try`, before Delete's own reply.
- **Failure:** if anything later in that block throws, the `catch` at 252 puts back a keybox that was already deleted. Meanwhile the cycle that just started has captured `before = ""`, so it ends in `STATE_CHANGED`.
- **Fix:** keep only the throwing writes inside the `try`. Reply, then call `sync()` and `drain()` after it.

**R3 – Secondary users get an error toast on every visit to the page.**
- **Where:** `TrickyStore.kt:382` and the catch at 547-553. The L9 fix hid the controls, but `onResume` still calls `checkKeyboxRevocation()` without checking `ui.monitorOwner`.
- **Failure:** in a secondary user, `LAST_CHECK` is read from that user's own settings (line 376). It is never written there, so a check is always due. AMS then throws `SecurityException` (`ActivityManagerService.java:21039`), which produces the toast.
- **Fix:** return early from the resume check and the auto-fetch when `!ui.monitorOwner`. This only matters if the page is reachable in secondary users.

**R4 – A recovery that finds no valid official keybox is described as a bad file.**
- **Where:** `TrickyStore.kt:558` maps every `CANDIDATE_*` failure to `ts_monitor_bad_file` ("The keybox file is invalid…").
- **Failure:** a manual Check or Fetch where the official mirror is also expired/revoked/unverifiable (`KeyboxOperations.java:58` and `:62`) tells the user their file is invalid, though no file was involved.
- **Fix:** give `CANDIDATE_*` on CHECK/FETCH its own string ("No valid official replacement is available"), in en-US and pt-BR. Keep `ts_monitor_bad_file` for `INVALID_KEYBOX`.

**R5 – The legacy hourly fetch doesn't recheck "unmanaged" before installing.**
- **Where:** the hourly gate is checked only when the request starts (`drain()` at 229). `canCommit` for non-automatic work compares only the hash (319-320).
- **Failure:** the user enables monitoring while an hourly fetch is in flight. A changed mirror keybox is still installed afterwards. The requirement is that the monitor schedule takes precedence.
- **Fix:** at the top of `finishInternal`, reject hourly requests when `enabled()` or `SOURCE == "user"`.

**R6 – An import whose Google reload is incomplete skips the follow-up flow.**
- **Where:** an `IMPORT` that installs but returns `ACTIVATION_FAILED` comes back with `success=false` (378).
- **Failure:** Settings shows the reload-incomplete toast, but skips the follow-up Check and the Play Store wipe prompt (`TrickyStore.kt:521-527`), even though the keybox is installed.
- **Fix:** treat `recovery == "reload_incomplete"` as an installed import in the callback.

**R7 – Imports now depend on the network.**
- **Where:** `KeyboxOperations.java:51-53` loads roots and the status list before an import is installed.
- **Failure:** while the network is unreachable, an import can take up to the 60 s deadline and then fail as `CYCLE_TIMEOUT`. Upstream installed a structurally valid import immediately.
- **Fix:** either accept this and document it, or install after `validate()` and run the inspection as a follow-up.

## Disposition check

| Item | Verdict |
|---|---|
| H1 null hash | Fixed (`KeyboxMonitor.java:51`, `KeyboxInspector` null check moved before decode, test at 121-126). |
| M1 hourly cost | Fixed (`KeyboxOperations.java:38-46`; `shouldPublish` prevents status overwrites). See R5. |
| M2 worker saturation | Fixed: separate `mDisconnects` executor, skipped when there are no connections (443-446); a rejected worker neither publishes nor moves the deadline. Moving to a dedicated `HandlerThread` is sound; `mActivated` is `volatile`. |
| M4 dropped imports | Fixed with counters. The `!isKeyboxPickerOpen` guard at 382 is effectively a no-op, because the fragment result arrives before `onResume`. It does no harm now that imports are queued. |
| M5 verdict overwrite | Fixed (357-366). |
| L1, L2, L4, L5, L7 | Fixed. See R4 for L1. `getLastFetchedFormatted` (`TrickyStore.kt:635`) still uses `SimpleDateFormat`; cosmetic only. |
| L3 delete rollback | Fixed, with the structural caveat in R2. |
| L6 duplicate import | Fixed: the re-anchor at 371-376 plus `restoreDelay` turns the eligibility change into a full interval. |
| L9 | Partially fixed; see R3. |
| L10 double callback | Fixed, but the fix introduced the stall in R1. |
| M3 (keep monitoring paused when no keybox) | Reasonable, but the rationale covers only an explicit Delete. A user can also enable monitoring on a device whose first fetch never succeeded, and then nothing fetches. Delete writes `SOURCE=""`, while a never-provisioned device has `null`, so bootstrapping only on `null` would keep both behaviours. Worth considering. |
| L6 timing, L8, endpoint, fresh-status requirement, offline cache | Reasonable as documented. The endpoint change and the regions where googleapis is unreachable should be raised with maintainers. |

Notification behaviour is correct. A check that times out or is rejected before inspecting the keybox posts no notification even under "every check", which is defensible because no check completed. It is worth stating in the documentation.

## Future upstream acceptance work (not blockers)

- `ts_monitor_fetching` and its `symbols.xml:6647` entry are now dead and can be removed.
- `TrickyStoreContent.kt` checks `monitorOwner && !rkpEnabled` twice, once nested inside the other.
- Rename the `klimt_*` resource files, keep the SystemUI and `PackagePartitions` patches out of the PR, and review the appended Binder method.
- Tests needed:
  - Handler/lifecycle tests for `finishInternal` paths (STATE_CHANGED, timeout before and after inspection, DELETE rollback, the R1 stall).
  - A test that the hourly install is refused once monitoring is enabled.
  - A Settings test for counters when an import arrives during a check.
  - Notification tests on a device.

**Recommended before building:** fix B1, then R1 and R2 (small structural fixes), then R3 and R4. R5–R7 can be recorded as dispositions.
