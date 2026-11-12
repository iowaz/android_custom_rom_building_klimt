# Parallel image verifier

- **Author:** Diogo Casteluber Laass
- **Status:** Proposed (revision 3, after the Goldfish review and the intermediate zoom-out)
- **Date:** 2026-11-06

---

## Overview

`build-setup/evox/pipeline/verify.py` is the static verifier that runs after every klimt build. It is
**fail-closed**: any failed assertion, missing evidence or tool error stops it before it writes `VERIFIED.txt`, and
without that marker no delivery can be promoted or flashed. It copies the fastboot image ZIP to the Windows delivery
folder, extracts the eight logical partitions, runs the must-hold and legacy shell checks, validates the historical
report gates, runs the seven supplemental image checks in `image-checks/check_image.py`, writes inventories and finally
`VERIFIED.txt`. Every step runs one after another, and the 32 minutes it takes are about a third of a build's total
time.

This design makes verification use the build PC's idle cores (AMD Ryzen 5 7600, 12 threads and 27 GiB RAM in WSL)
without changing what is checked. Every check still runs and still blocks `VERIFIED.txt`; the evidence stays
identical after the normalisation listed under Goals; only scheduling, and the way two expensive kinds of repeated
work are done, change. All new code is Python and Bash in the existing pipeline. A Go graph server is kept as an
optional third phase, to be built only if phase 2's measurements call for it.

### Terms

- **Attempt**: one build run of a dated build, e.g. `20261106-attempt01`; its records live under
  `/mnt/wsl/evox/logs/<build>/<attempt>` and `diagnostics/builds/<build>`.
- **Controller**: `controller.py`, which runs the build wrapper and then `verify.py` under a source lock, and records
  the attempt state (`building`, `verifying`, `image-verified-runtime-pending`, `build-failed`, `tool-failed`).
- **Preflight gates**: the checks `verify.py` runs before touching any file (listed under Task graph).
- **Heads**: the git HEAD of every source project; "effective heads" are the frozen pins, with patched projects at
  their `PATCHES.json` `final_head`.
- **Tooling hash / tooling freeze**: `controller.tooling_hashes()` records the SHA-256 of every `.py`, `.sh`, `.json`
  and `.sha256` file in the pipeline folder when an attempt starts; `verify.py` refuses to run if any changed.
- **Recheck**: `verify.py <attempt> --recheck recheckNN --tool-review <json>` re-verifies a finished attempt with
  changed verifier tooling. `tool_review.py` writes the review JSON, binding the attempt, its source snapshot, the
  current tooling hashes and `IMAGE_CHECKS.json`.
- **Canonical order**: the order today's `verify.py` runs things in (the task table below gives each task its index).
- **9P**: the protocol WSL uses for Windows drives such as `/mnt/d`; much slower than the ext4 build disk
  (`build.vhdx`, a virtual disk file stored on D:).
- **Defect / tooling failure**: `check_image.py` exits 1 for a failed assertion about the image, 2 for a tool or
  evidence problem, 3 for an unexpected error. `verify.py` turns any of them into an exception.

## The Problem

Measured on 20261105.3 attempt01 (build exit 23:04:24, `VERIFIED.txt` 23:36:41, 32 min 17 s), from the report,
attempt and extraction file times:

| Phase | Time | What makes it slow |
|---|---|---|
| exit hash, postbuild manifest (controller); preflight hash, live heads, preverify manifest (verify) | 2 min 19 s | two `repo manifest -r` captures, two per-project `git status` sweeps and a 5 GB hash, back to back |
| archive copy and checks | 3 min 15 s | 5 GB copied to `/mnt/d` over 9P, hashed twice more, then `testzip` reads the Windows copy |
| unzip and `archive-images.sha256` | 4 min 54 s | `extract.sh` unzips the Windows copy over 9P |
| `simg2img` and partition extraction | 4 min 4 s | eight partitions extracted one at a time (product alone 1 min 16 s) |
| `img.sha256` | 1 min 14 s | 17 images hashed one at a time |
| `musthold.sh`, `fixcheck21.sh`, `check-health-his.py` | 1 min 15 s | sequential, small (musthold 17 s) |
| seven supplemental checks | 12 min 49 s | one after another; inside them 75 `ninja -t query` calls each re-parse the 1.5 GB build graph (about 4.5 s each, 5.6 min) and policy's `ninja -t commands` takes about 90 s; about 1,370 `aapt2` calls in three loops run one at a time |
| inventories, postverify manifest, results, `SHA256SUMS` | 2 min 27 s | 9 GB of extracted files hashed serially; the 5 GB archive hashed again over 9P |

Supplemental check times: policy 1 min 55 s, patch_packaging 1 min 49 s, private_compatibility 1 min 50 s,
health_semantics 38 s, gms_themes_apps 3 min 1 s, doze_packaging 2 min 28 s, install_integrity 1 min 7 s.

Most of this is one busy thread, or waiting on 9P, while eleven threads sit idle.

## Goals

- **Wall time** from build-wrapper exit to `VERIFIED.txt`, measured on a full user/GMS build: at most 15 minutes after
  phase 1 (at most 12 if the ninja measurement allows two concurrent loads), at most 10 minutes after phase 2. The
  budget behind these numbers, with its margin, is under Technical Plan. (Today: 32 min on 20261105.3, 42 min on
  20261106.)
- **Same verdict, same evidence**: for the same attempt, a recheck with the new verifier and the original report are
  identical after the normalisation done by `compare-verify-reports.py`, which ignores exactly this list and nothing
  else: times; the report, extraction, `EVOX_TMP`, `EVOX_VTMP` and staging roots inside any JSON value or raw text;
  `RESULTS.json`'s `recheck` field; `script_sha256` (compared with the tool review instead); the new files
  `timing.json`, `raw-ninja-prefetch.txt`, `raw-ninja-prefetch-audit.txt`, `TOOL_REVIEW.json`; the new `RESULTS.json`
  keys `verifier_settings` and `ninja_prefetch`; and the new `source`/`prefetch_hits` fields of `query-batch` raw
  records. JSON is compared parsed, with key order ignored. Raw log file names, check rows (name, pass, details),
  every evidence JSON a check writes, `raw-*.txt` content and the exit codes must match. The allow-list lives in one
  constant shared by the compare tool and the tests.
- **Fail-closed unchanged**: every gate that exists today still runs and still blocks `VERIFIED.txt`. When tasks
  fail, every task earlier in canonical order still runs, and the failure reported is the earliest one in canonical
  order, which is the failure today's verifier reports.
- **Bounded memory**: peak RSS of the verifier's process tree at most 20 GiB, with at most one real ninja graph load
  at a time (two only if the RSS measurement in Open Questions shows it is safe).
- **Observable**: `timing.json` in the report folder with start, end, wait time, exit and peak RSS for every task, the
  effective settings and the load average.

## Non-Goals

- No new, removed or relaxed checks. The preverify and postverify manifest captures, the late read-back hash of the
  delivered archive and `testzip` all stay.
- No rewrite of check logic: `check_image.py`'s assertions and loops, `musthold.sh`, the fixcheck scripts and
  `report-gates.py` keep their code paths. The only `check_image.py` changes are inside `Check.run()` and
  `Check.queries()`, plus one prefetch call before each of three loops.
- No change to the build stage, `prepare.py`, `ready.py`'s gates, `promote.py`, the flash helpers, the controller's
  state machine, locks or the recheck/tool-review process.
- No device testing. "Image-checked" still means static checks only.
- No Go code in phases 1 and 2.

## Open Questions

- **Real ninja RSS today**: the comment in `check_image.py` cites 54.5 s and 16 GB RSS for one full-build load, but
  the 75 queries in 20261105.3 took about 4.5 s each. Measure RSS and time of one `ninja -t query` and of policy's
  `ninja -t commands` on 20261106's graph, between attempts. It decides whether phase 1 may run two ninja loads at
  once.
- **Batch output equals concatenation**: phase 2 assumes `ninja -t query a b` prints exactly the `-t query a` output
  followed by the `-t query b` output, for the tree's `prebuilts/build-tools/linux-x86/bin/ninja`. Prove it on every
  node of the 20261106 report before phase 2 is written.
- **Prefetch hit rate**: how many of a build's queried nodes also appear in the previous build's report, and how many
  of the previous build's nodes are unknown in the new graph (an unknown node makes the whole `ninja -t query` call
  fail). Measure on 20261105.3 → 20261106. If misses cost more than 1 minute, phase 3 (Go server) becomes worth
  designing.
- **VHDX I/O ceiling**: the useful extraction concurrency (2, 3 or 4) on `build.vhdx`; default 3 until measured.
- **9P report writes**: about 1,400 raw files are written to the report folder on `/mnt/d`. Measure their total cost
  once the checks run concurrently.

## Critical User Journeys (CUJs)

### CUJ 1: A normal build is verified faster

- **Given**: an attempt whose build wrapper exited 0, with the controller holding the source lock.
- **When**: the controller runs `verify.py <attempt>` as today.
- **Then**: the same report files (plus `timing.json`, and in phase 2 `raw-ninja-prefetch.txt` and
  `raw-ninja-prefetch-audit.txt`), the same delivery folder and
  `VERIFIED.txt` appear within the wall-time goal; the controller records `image-verified-runtime-pending`.

### CUJ 2: Checks fail while others are running

- **Given**: a build where `doze_packaging` (canonical index 14) fails while `gms_themes_apps` (13) is running and
  I1 (16) has not started.
- **When**: `doze_packaging` exits non-zero.
- **Then**: the scheduler does not start index 15 or later, lets running tasks finish (a check above 14 that was
  already running may finish and leave its files, which the sequential verifier would not have written), runs any
  not-yet-started task below 14,
  writes `supplemental-results.json` with every finished check in canonical order, writes no `VERIFIED.txt`, and
  raises the error of the lowest failed index. `verify.py` exits 1 and the controller records `tool-failed` with
  `tool-error.json`, exactly as today.

### CUJ 3: A ninja answer served from the prefetch is wrong

- **Given**: the prefetch file holds a section that differs from what ninja would print now (cannot happen when the
  concatenation property holds; this is the guard for when it does not).
- **When**: the end-of-run audit (task C1) re-queries real ninja, in one call, for every node that was served from the
  prefetch, taking the node list and the expected bytes from the checks' own `raw-supplemental-*-query-batch.txt`
  logs.
- **Then**: any byte difference raises `RuntimeError('Ninja prefetch audit mismatch: <node>')`; `verify.py` exits 1,
  the controller records `tool-failed`, and no `VERIFIED.txt` is written. C1 also runs when a check failed, and a C1
  mismatch takes precedence over every check failure: the raised message is
  `Ninja prefetch audit mismatch: <node> (also: <the check error>)`, so a wrong prefetch answer is reported as the
  cause instead of a false ROM defect.

### CUJ 4: The owner rechecks an attempt with changed tooling

- **Given**: the changed pipeline committed, `IMAGE_CHECKS.json` and `TEST_RESULTS.linux.json` updated, and a review
  written by `tool_review.py` for the latest attempt, before the next `prepare.py`.
- **When**: the owner runs `verify.py <attempt> --recheck recheckNN --tool-review <json>`.
- **Then**: the recheck runs in parallel, and `compare-verify-reports.py` prints "identical" or every differing row.

### CUJ 5: Serial scheduling of the new verifier

- **Given**: a suspected scheduling problem.
- **When**: the owner sets `EVOX_VERIFY_JOBS=1` before `start.sh` (which forces `EVOX_EXTRACT_JOBS=1`,
  `EVOX_CHECK_THREADS=1` and `EVOX_NINJA_PREFETCH=0` in every child).
- **Then**: every task runs one at a time in canonical order with the same raw names and evidence. This is not a
  revert: the unzip still reads the WSL ZIP. Rolling back means `git revert` of the phase commit, then `ready.py`.

## Technical Plan (Architecture)

### Task graph

`verify.py` keeps its preflight gates in today's order, then runs the rest as tasks with explicit dependencies,
then keeps today's finalize code. A small scheduler in `pipeline/verify_tasks.py` runs ready tasks on a
`concurrent.futures.ThreadPoolExecutor` (each task is a subprocess or a GIL-releasing hash loop) with a semaphore per
limited resource.

Preflight, unchanged and sequential: tool freeze, recheck review binding, exit record, ZIP hash/size/mtime against the
exit record (the digest is kept as `zip_digest` along with `st_ino` and `st_ctime_ns`), foreign processes, stale input
archive, live heads, recheck folders, preverify manifest equals effective heads, no prior `VERIFIED.txt`, headroom,
`dest.mkdir`. New in preflight: `EVOX_VTMP` (`<extract>.verify`) must not exist and is created (a leftover one
from an interrupted run stops verify with "stale EVOX_VTMP from an interrupted run: delete <path>"), and no `ninja`
or `check_image.py` process from an earlier run may be alive.

| Idx | Task | Depends on | Limit | Reads | Writes |
|---|---|---|---|---|---|
| 1 | A1 copy WSL ZIP to `.partial`, hashing the bytes read | preflight | 9p | WSL ZIP | staging `.partial` |
| 2 | A2 read back `.partial`, rename to the archive | A1 | 9p | staging `.partial` | staging archive |
| 3 | A3 `testzip` + entry inventory of the WSL ZIP | preflight | io | WSL ZIP | `archive-inventory.json` |
| 4 | X `extract.sh` from the WSL ZIP | preflight | io (own jobs) | WSL ZIP | `<extract>/img` (all 19 entries), `fs`, `tmp`, `archive-images.sha256`, `img.sha256`, `raw-extract.txt` |
| 5 | P ninja prefetch (phase 2; never raises) | preflight | ninja | `out/*.ninja`, previous report | `EVOX_VTMP/ninja-prefetch/`, `raw-ninja-prefetch.txt` |
| 6 | H1 `musthold.sh` | X | — | `img/*`, `img.sha256`, `fs/*_dlkm`, `out/.../Module.symvers` | `EVOX_TMP/evx_vb*`, `evx_rd`, `evx_boot`, `raw-musthold.txt` |
| 7 | H2 `fixcheck21.sh` then `check-health-his.py` | H1 | — | `fs`, `EVOX_TMP/evx_rd`, tree | `EVOX_TMP/evx20_boot`, `evx20-proc-version.txt`, `ota7`, `xiaomiparts-manifest.txt`, `raw-fixcheck.txt` |
| 8 | R1 `report-gates.validate`, then `check-metadata26.py` | H2 | — | `raw-extract/musthold/fixcheck.txt`, `evx20-proc-version.txt` | `metadata26.json` |
| 9–15 | S1–S7 `check_image.py <mode>`, in `IMAGE_CHECKS.json` order | H1 (and P in phase 2) | check (4) | `fs`, `evx_rd`, `out/soong`, tree, prefetch | `supplemental-<mode>*`, `raw-supplemental-<mode>-*`, the six mode evidence JSONs, `raw-image-check-NN.txt`, `EVOX_TMP/supplemental-<mode>/` |
| 16 | I1 `filesystem-files.json`, `image-files.json` | X | io | `fs`, `img` | the two inventories |
| 17 | C1 prefetch audit (phase 2), whenever P wrote at least one prefetch file | all S that ran | ninja | `EVOX_VTMP/ninja-ledger.txt`, `raw-supplemental-*-query-batch.txt`, query records | `raw-ninja-prefetch-audit.txt` |
| 18 | A4 late read-back hash of the staged archive | A2, all S, I1 | 9p | staging archive | digest |
| 19 | M2 postverify manifest, live heads, tool freeze, ZIP identity unchanged | every task except A4 | — | tree, WSL ZIP stat | `postverify.xml` |

Finalize (today's code, sequential, after A4 and M2): `RESULTS.json`, `COMPARISON.md`, flash scripts, copies,
`SHA256SUMS` (the archive line uses A4's digest, which must equal `zip_digest`, A1's and A2's), `VERIFIED.txt`.

Why the order is what it is:

- **`evx_rd`**: `musthold.sh` creates it; `check-health-his.py` (H2) and every `check_image.py` mode read it. H2 and all
  S tasks wait for H1.
- **`evx20-proc-version.txt`**: `fixcheck20.sh` (run by `fixcheck21.sh`) writes it; `check-metadata26.py` reads it, so
  R1 waits for H2.
- **`archive-images.sha256`**: hashes the images as they leave the ZIP, so `extract.sh` takes each image's archive hash
  before `simg2img` can rewrite it. `img.sha256` is taken after every partition is extracted, and `musthold.sh` prints
  it.
- **R1 before S in canonical order**: today the historical gates run before the image checks; R1 keeps a lower index
  so a must-hold defect is still the reported failure.
- **`EVOX_VTMP`**: `extract.sh` requires `<extract>` not to exist and creates `EVOX_TMP` itself, so anything the
  scheduler writes before X runs (prefetch, `ninja.lock`, `timing.json` buffer) lives in the sibling
  `<extract>.verify`, outside the folder `controller.resume()` inspects.

### Failure handling

After the first failure at index k the scheduler starts no task with index above k, keeps starting tasks below k,
waits for running tasks, runs C1 if P wrote at least one prefetch file, writes `supplemental-results.json` and
copies `timing.json` in a `finally` block (every finished check, canonical order, with `exit` and `log`), and raises
the error of the lowest failed index, except that a C1 mismatch always wins and names the other error. Tasks below
k cannot be skipped, because the sequential verifier would have run them first. P never raises: any problem means
no prefetch, recorded in `RESULTS.json['ninja_prefetch']`, so it cannot hide a must-hold or check failure.

### Evidence chain for the archive

- The WSL ZIP's digest, size and mtime are checked against the wrapper's exit record in preflight, as today; its
  inode and ctime are recorded too.
- A1 hashes the bytes it reads from the WSL ZIP while copying; that digest must equal `zip_digest`. This replaces
  today's separate second hash of the WSL ZIP with the same comparison on the same read.
- A2 re-reads the Windows `.partial` and must equal `zip_digest` before the rename (today's `sha(partial)`).
- X unzips the WSL ZIP; A3 runs `testzip` on it. M2 re-checks the WSL ZIP's size, mtime, inode and ctime, so the
  extracted and tested bytes are the hashed bytes.
- A4 re-reads the delivered archive late in the run, as today's `SHA256SUMS` does, and finalize requires it to equal
  the others.

### Inside the checks: prefetch and replay

`Check.prefetch(argvs)` hands a list of argv lists to a `ThreadPoolExecutor` of `EVOX_CHECK_THREADS` workers (default
2) and stores the futures by `tuple(argv)`. `Check.run(argv, label)` is unchanged except for its first step: if a
future for the identical argv exists, it waits for it instead of starting a subprocess. The counter, raw log name,
`self.raw` record, timeout and exception are all handled at that point, exactly as today. Unconsumed results are
dropped without writing anything. The check loops are not changed; one prefetch call goes before each of:

- `gms_themes_apps`: `aapt2 dump badging` for every image APK file, in `sorted(rglob)` order (about 460).
- `doze_packaging`: `aapt2 dump xmltree` and `aapt2 dump resources` for every overlay APK (about 450; the
  `resources` result is used only for overlays that target `android`, as today).
- `install_integrity`: `aapt2 dump badging` for every image APK file (about 460).

A speculative call that fails is not an error until `run()` consumes it, so a failure surfaces at the same point and
with the same raw files as today. The argv lists are built on the main thread with a `tool_path()` helper that
selects the tool exactly like `tool()` but does not call `identify()`, so the order of `inputs` in the evidence JSON
does not change; `tool()` still identifies the tool at its first real use inside the loop. `finish()` shuts the pool
down with `cancel_futures=True`, so a failing check does not wait for hundreds of unused calls. With
`EVOX_CHECK_THREADS=1`, `prefetch()` does nothing, so serial mode runs the plain code path. A `Check` built without
`__init__` (as the unit tests do) has no pool and behaves as today.

### Ninja prefetch (phase 2)

`check_image.py` asks ninja about the same `out/soong/.intermediates/...` and `out/target/product/klimt/...` nodes in
every build. Task P builds the node list from the previous verified report's `supplemental-*.json` raw records
(arguments after `-t query`). The previous report is the newest top-level
`diagnostics/builds/*/reports/<attempt>/` with a `VERIFIED.txt`, never a `rechecks/` folder and never the current
attempt. P then makes two real ninja calls under the ninja lock: `ninja -t targets all`, to drop nodes the current
graph does not have (every queried node is a build output or a phony target), and one `ninja -t query` over the
rest. It reads stdout and stderr separately, writes prefetch files only from a call that exited 0, and splits the
output into one file per node in `EVOX_VTMP/ninja-prefetch/` (the file name is the SHA-256 of the node path). Any
problem (an unknown node despite the filter, a non-zero exit, out of memory) means no prefetch for this run.

`Check.queries(nodes)` first appends `<mode> <counter> <node>` for every node it will serve from the prefetch to
`EVOX_VTMP/ninja-ledger.txt`, then composes the text for the batch from prefetch files in argument order, runs one
real ninja call for the nodes not in the prefetch, splices those sections in at their positions, and writes the
result through the same counter and `query-batch` raw log as today. The raw record keeps today's ninja argv and adds
`source: prefetch|ninja|mixed` and `prefetch_hits`, the ordered list of nodes served from the prefetch.
`parse_query()` is unchanged. Every answer is real ninja output for this build's graph. C1 audits the union of the
ledger and the records, so even a check that crashed before `finish()` is covered; a ledger node with no matching
section in a raw log fails C1.

### Resource limits

| Limit | Default | Members |
|---|---|---|
| `ninja` | 1 (`fcntl.flock` on `EVOX_VTMP/ninja.lock`, taken in Python before `subprocess.run`, so waiting does not count against the 900 s timeout and the argv is unchanged; with `EVOX_NINJA_JOBS=2`, two lock files `ninja.0.lock`/`ninja.1.lock`, each tried without blocking, then a blocking wait on the first; without `EVOX_VTMP`, no lock and no prefetch) | every real ninja call: queries, policy's `-t commands`, P, C1 |
| `9p` | 1 | A1, A2, A4 |
| `io` | 3 | A3, I1; `extract.sh` runs `EVOX_EXTRACT_JOBS` (default 3) workers inside its one task |
| `check` | 4 | S tasks; each runs up to `EVOX_CHECK_THREADS` (default 2) tool calls |

Overrides: `EVOX_VERIFY_JOBS`, `EVOX_EXTRACT_JOBS`, `EVOX_CHECK_THREADS`, `EVOX_NINJA_JOBS` (1 or 2),
`EVOX_NINJA_PREFETCH` (1 or 0). Effective values go into `timing.json` and `RESULTS.json['verifier_settings']`.
`timing.json` is buffered in `EVOX_VTMP` and copied once at the end.

### Time budget

| Step (critical path) | Today | Phase 1 | Phase 2 |
|---|---|---|---|
| controller exit hash and postbuild, verify preflight | 2.3 min | 2.3 | 2.3 |
| X: local parallel unzip, archive hashes, extraction (product 1.3 min, rest spread over 3 workers), `img.sha256` | 10.2 | 2.9 | 2.9 |
| H1 `musthold.sh` | 0.3 | 0.3 | 0.3 |
| S: the seven checks | 12.8 | 7.5 (75 queries + `-t commands` serialised under one ninja lock) or 4.0 with two | 2.5 (policy's `-t commands` and gms dominate) |
| C1 audit (one ninja load) | — | — | 0.2 |
| M2 (one `repo manifest -r`, one `live_heads()` sweep), finalize; A4 runs beside M2 | 2.4 | 1.2 | 1.2 |
| **Total** | **32.3** | **14.2** (10.7 with two ninja) | **9.4** |

Margins against the goals: 0.8 min for phase 1 (1.3 with two ninja loads), 0.6 min for phase 2. A1, A2, A3, P, H2, R1,
I1 and A4 run beside the critical path at these estimates; A4 (about 1 min over 9P) overlaps M2 (about 1 min).

## Alternatives Considered

### Alternative A: Only run today's tasks concurrently

- **Pros**: no change inside the checks.
- **Cons**: 5.6 minutes of serial ninja parsing stays (the ninja lock prevents parallel loads), the 9P unzip stays,
  and the three `aapt2` loops stay serial.
- **Reason for Rejection**: Rejected by author: it is phase 1 minus the two cheapest wins; the design keeps its parts.

### Alternative B: Go graph server

- **Pros**: one parse of the 1.5 GB graph (an estimated 10 to 20 s), arbitrary new nodes answered without ninja.
- **Cons**: a reimplementation of ninja's manifest semantics (subninja scoping, escapes, validations, exact
  `-t query` output) that needs its own cross-check, server lifecycle, tooling-hash coverage (`.go` and `.mod` are not
  in `tooling_hashes()` today) and toolchain pinning.
- **Reason for Rejection**: Rejected by author for now: the prefetch gives the same saving with real ninja output when
  nodes repeat between builds. Kept as phase 3 if the measured miss rate costs more than a minute.

### Alternative C: Rewrite the verifier in Go

- **Pros**: one static binary, real types.
- **Cons**: about 1,100 lines of reviewed checks (some evaluating AArch64 instructions) would need a new review; the
  slow parts are tools and I/O, not Python.
- **Reason for Rejection**: Rejected by author: high review cost for little speed.

### Alternative D: Batch broker for live ninja queries

- **Pros**: no stale-node risk; one ninja load per round of concurrent batches.
- **Cons**: needs a cross-process broker; the BFS walks in different checks rarely line up, so loads drop by less than
  half.
- **Reason for Rejection**: Rejected by author: the prefetch removes nearly all loads with less machinery.

### Alternative E: Collect-then-consume rewrite of the loops

- **Pros**: explicit parallel code.
- **Cons**: `doze_packaging`'s second `aapt2` call and `installed_target()` queries depend on earlier results, so
  raw log numbers would change, and reviewed loops would be rewritten.
- **Reason for Rejection**: Rejected by author: prefetch-and-replay keeps the loops and numbering unchanged.

### Alternative F: Parse APKs in-process (androguard or similar)

- **Pros**: no `aapt2` process per APK.
- **Cons**: a different parser with different output; the checks assert on `aapt2` text.
- **Reason for Rejection**: Rejected by author: it changes the evidence.

### Alternative G: Drop "redundant" gates

- **Pros**: about 3 minutes.
- **Cons**: weakens the fail-closed verifier; the owner's rules forbid it.
- **Reason for Rejection**: Rejected by author.

---

## Non-Functional Requirements

- **Security & Privacy**: no network access, no new dependencies, no keys or phone data touched. `EVOX_VTMP` is per
  attempt and user-only.
- **Performance & Latency**: goals above; `timing.json` samples process-tree RSS every 2 s.
- **Rollout & Rollback**: each phase lands only between attempts, in this order: edit; run both test suites; update
  `IMAGE_CHECKS.json` and `TEST_RESULTS.linux.json`; commit; Codex audit of the diff; `tool_review.py` for the latest
  attempt; parity rechecks (see Verification Plan); re-run `ready.py` for the next build; one real build verified with
  it. Rollback is `git revert` of the phase commit, followed by `ready.py` (an older `BUILD_READY.json` carries the
  old `check_image.py` hash and would fail at verify time). Parity rechecks are never promoted; their extraction,
  `EVOX_VTMP` and staging copies are deleted after the comparison, and the attempt's `status.json` is restored.

### Additional Resources

- `build-setup/evox/pipeline/README.md`, `verify.py`, `controller.py`, `extract.sh`, `tool_review.py`,
  `legacy/musthold.sh`, `legacy/fixcheck21.sh`, `check-health-his.py`, `check-metadata26.py`,
  `image-checks/check_image.py`, `image-checks/README.md`.
- `docs/20261105.3.md` (the measured run), `docs/evox16-review.md` (why the checks are fail-closed).
- Review record: `diagnostics/verifier-design-review/` on the build PC (four Goldfish reports and the disposition).
- Ninja manifest format: https://ninja-build.org/manual.html#ref_ninja_file

### Future Improvements

- **Phase 3, Go graph server**: only if phase 2's miss cost exceeds one minute. It would need `.go`, `.mod` and
  `.sum` added to `tooling_hashes()`, the tree's Go toolchain version checked first, `-mod=readonly`, the binary
  built with `-o` into `EVOX_VTMP` and its hash recorded, and C1 kept as the authority check.
- **Parallel `live_heads()`**: it runs `git rev-parse` and `git status` per project, serially, three times per build.
  A thread pool keeps the same checks.
- **Shared APK badging**: `gms_themes_apps` and `install_integrity` badge the same APKs; sharing would halve the calls
  but couple two independent pieces of evidence.
- **buildwatch**: switch `D:\android_rom_building\scripts\buildwatch\wsl_probe.py`'s `verify_marks()` to read
  `timing.json` (it infers sequential steps from file times today). Outside this repository; a separate change.

---

## Detailed Implementation Plan

### Target Files to Create/Modify

#### 1. `build-setup/evox/pipeline/verify_tasks.py` (Create, phase 1)

- **Type / Scope**: Python module.
- **Proposed Changes**: `Task(index, name, fn, deps, limit)`; `run(tasks, limits, vtmp) -> dict[str, object]`
  implementing Failure handling above; `limits_from_env() -> dict` (when `EVOX_VERIFY_JOBS=1`, every limit is 1 and
  the returned child environment sets `EVOX_EXTRACT_JOBS=1`, `EVOX_CHECK_THREADS=1`, `EVOX_NINJA_PREFETCH=0`); an RSS
  and load-average sampler thread over `/proc`; `timing.json` written to `vtmp` and returned. No local variable may be
  named `time`, `json`, `os`, `re` or `subprocess` (`tests.py` rejects that).

#### 2. `build-setup/evox/pipeline/verify.py` (Modify, phases 1 and 2)

- **Type / Scope**: Python verifier.
- **Proposed Changes**: keep lines 97–141 and 143–153 (preflight, in order; keep the preverify capture at 142 in its
  place), storing `zip_digest`, `st_ino`, `st_ctime_ns`; add the `EVOX_VTMP` and stale-process gates. Replace 154–187
  with the task table: A1 (copy with `hashlib` on the read side), A2 (today's `sha(partial)`, rename), A3
  (`zipfile.testzip` on `ZIP`), X (`extract.sh` with `str(ZIP)`), P (phase 2, from `ninja_prefetch.py`), H1, H2
  (fixcheck21 then health, same `raw-fixcheck.txt`), R1, S1–S7 (one task per `ready['image_checks']` entry,
  `raw-image-check-NN.txt` by readiness index, script hash check kept), I1 (thread-pooled `inventory()`, same sorted
  output), C1 (phase 2), A4, M2 (adds the ZIP stat check). `supplemental-results.json` written in `finally`. Finalize
  unchanged except the archive line of `SHA256SUMS` uses A4's digest after the four-way equality check. The child
  `env` adds `EVOX_VTMP` and the child settings.

#### 3. `build-setup/evox/pipeline/extract.sh` (Modify, phase 1)

- **Type / Scope**: Bash.
- **Proposed Changes**: same arguments, same output files. For every ZIP entry (`unzip -Z1 "$Z"`, 19 names, including
  `android-info.txt` and `fastboot-info.txt`, which `musthold.sh` compares), in parallel
  (`xargs -P "${EVOX_EXTRACT_JOBS:-3}"`): `unzip -q "$Z" "$name" -d "$E/img"`, then, for `*.img` only, `sha256sum` into
  `$E/tmp/archive-<name>.sha256`. Then write `archive-images.sha256` by iterating the same `*.img` glob in the same
  shell and concatenating, so the order and collation match today. Per partition, in parallel: `simg2img` if sparse
  (its stdout/stderr and the `evox <p>: <kind>` line go to `$E/tmp/out-<p>.txt`, which is what reaches
  `raw-extract.txt` today), `fsck.erofs`/`debugfs` into `$E/tmp/extract-<p>.log` as today; afterwards print the
  `out-<p>.txt` files in today's partition order, so `raw-extract.txt` has today's content. `img.sha256` the same way
  as the archive hashes, then `du -sh` as today. Any failed worker fails the script. `T` may be overridden by
  `EVOX_EXTRACT_TOOLS` (default unchanged) for tests.

#### 4. `build-setup/evox/pipeline/image-checks/check_image.py` (Modify, phases 1 and 2)

- **Type / Scope**: Python checks.
- **Proposed Changes**: `Check.prefetch(argvs)` and the first step of `Check.run()` as in "prefetch and replay";
  `Check.run(..., lock=False)` takes `fcntl.flock(EVOX_VTMP/ninja.lock)` before the subprocess when `lock` is true;
  every real ninja call passes `lock=True`. One `c.prefetch([...])` line before the loops at today's lines 497, 624
  and 667. Phase 2: `Check.queries()` composes from `EVOX_VTMP/ninja-prefetch/` when `EVOX_NINJA_PREFETCH=1`, as
  described, keeping the counter and `query-batch` label. No assertion changes.

#### 5. `build-setup/evox/pipeline/ninja_prefetch.py` (Create, phase 2)

- **Type / Scope**: Python module.
- **Proposed Changes**: `previous_nodes(diagnostics, attempt) -> list[str]` (the search defined under "Ninja
  prefetch"); `prefetch(ninja_bin, nodes, out_dir, raw_log) -> dict` (the `targets all` filter, one query, separate
  stdout/stderr, files only on exit 0, never raises; returns counts for `RESULTS.json['ninja_prefetch']`);
  `audit(report, vtmp, ninja_bin, out_log) -> int` (C1: the union of `ninja-ledger.txt` and the `prefetch_hits` of
  every query record, each node's section taken from its raw `query-batch` log, one real ninja call, byte comparison,
  raise on a missing section or the first mismatch, return the node count, which must be above zero when the ledger
  is not empty).
  The ninja binary is chosen with `check_image`'s rule (`prebuilts/build-tools` copy, sorted last).

#### 6. `build-setup/evox/pipeline/image-checks/IMAGE_CHECKS.json` and `TEST_RESULTS.linux.json` (Modify, each phase)

- **Type / Scope**: reviewed check registry.
- **Proposed Changes**: new `check_image.py` SHA-256 in all seven entries and in `check_image_py_sha256`, with the new
  `tests_run`, after `image-checks/tests.py` passes on Linux.

#### 7. `build-setup/evox/pipeline/tools/compare-verify-reports.py` (Create, phase 1)

- **Type / Scope**: Python tool.
- **Proposed Changes**: `compare-verify-reports.py <reportA> <reportB> --review <TOOL_REVIEW.json>`. Lists only each
  report's top folder (never `rechecks/`), applies exactly the normalisation in Goals, compares file name sets (with
  the allow-list of new files), every JSON and every `raw-*.txt`, checks `script_sha256` against the review, and
  prints "identical" or each difference. Exit 0 only when identical.

#### 8. `build-setup/evox/pipeline/tests.py` (Modify)

- **Type / Scope**: Python unit tests.
- **Proposed Changes**: scheduler tests with fake tasks (dependency order, limits, no start above a failure, tasks
  below it still run, lowest failure raised, `EVOX_VERIFY_JOBS=1` equals canonical order, `supplemental-results.json`
  written on failure); `extract.sh` with a PATH-shim fixture (eight tiny images, shims that echo a kind and create
  `fs/<p>/x`, one partition that sleeps) checking output order and hash-file order; `ninja_prefetch` retry, splice and
  audit mismatch on a fake ninja script.

#### 9. `build-setup/evox/pipeline/image-checks/tests.py` (Modify)

- **Type / Scope**: Python unit tests.
- **Proposed Changes**: `prefetch` + `run` replay: shuffled completion keeps counters and raw names; a conditional
  second call is numbered as today; an unconsumed result writes nothing; a failing speculative call raises only when
  consumed; `lock=True` waits outside the timeout.

#### 10. `build-setup/evox/pipeline/README.md`, `image-checks/README.md`, `docs/build-pc-layout.md` (Modify)

- **Type / Scope**: documentation.
- **Proposed Changes**: task table, `EVOX_VTMP`, settings, `timing.json`, prefetch and audit, serial mode, the
  rollout order. Each phase's measured result goes into that build's `docs/<build>.md`.

### Verification Plan

- **Before phase 1**: between attempts, measure one `ninja -t query` and `ninja -t commands` (time and peak RSS) on
  20261106's graph; record the numbers in this doc.
- **Unit tests** (only between attempts, since both suites write tracked files): `python3 -B tests.py` and
  `python3 -B image-checks/tests.py` in the pipeline folder, all passing, including the new tests.
- **Static checks**: `python3 -m py_compile` on changed files; `bash -n extract.sh`; `shellcheck extract.sh` if
  installed, with no new warnings.
- **Parity**: on the latest attempt, before the next `prepare.py`, with the same `out` ZIP and enough headroom
  (`space()` checked before each run): `tool_review.py` → recheck with `EVOX_VERIFY_JOBS=1` → compare → clean up →
  `tool_review.py` → recheck with defaults → compare. Both must print "identical". Repeat for phase 2, once with the
  prefetch built from the 20261105.3 report (an older graph), so mixed batches and the `targets all` filter run
  against the real graph.
- **Failure injection**: outside the recheck path, run the S group of the new scheduler and of the old sequential
  `image_checks()` against a hard-linked copy (`cp -al`) of the extraction in which `system/system/build.prop` is
  replaced by a new file (written beside it, then renamed over the link, never edited in place) with
  `doze.display.supported=false`. Both must stop at `doze_packaging` with the same exit code, rows and error text,
  and be identical up to and including that check; later checks that were already running may add files.
- **Phase 2 property test**: for every node in the 20261106 report's `query-batch` logs, `ninja -t query` of the whole
  list equals the concatenation of single-node outputs.
- **Metrics**: `timing.json` wall time within the goal for the phase, peak RSS at most 20 GiB, on one real build.
- **Independent audit**: Codex (`gpt-6.1-sol`, high) audits each phase's diff and parity evidence before the first
  real build uses it.

---

*Drafted with EGM*
