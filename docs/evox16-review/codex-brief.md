# Independent review of evox16 (Xiaomi 15T Pro "klimt", Evolution X) — READ-ONLY

You are the independent reviewer. Another agent (Claude) is doing its own review in parallel; do not
coordinate with it and do not assume its conclusions. Your result decides what is reverted before the
next build (evox17).

## Background

- Device: Xiaomi 15T Pro (klimt, MediaTek). ROM: Evolution X on Android 17 (`cp2a`, CP2A.260605.016),
  user build, private keys. Builds are incremental in one tree.
- **evox15** (Evolution X 12.2) is the last build that boots and works on the phone. It is the
  baseline. Its source is pinned in
  `C:\Users\diogo\Documents\Codex\2026-10-14\ru\android_custom_rom_building_klimt\manifests\snapshots\evox15.xml`
  and its local manifest is `git show 29f5fa0:manifests/local_manifests/klimt.xml` in that repository.
- **evox16** was meant to be a simple "go upstream" task: move to Evolution X 12.3 (`cnb`) and keep
  only what klimt needs. It was planned and mostly executed by a previous Codex session
  (`C:\Users\diogo\Documents\Codex\2026-10-14\we-x20\outputs\EVOX16_IMPLEMENTATION_PLAN.md`,
  `EvolutionX_commit_reviews_2026-10-14.md`, `EvolutionX_sync_audit_2026-10-14.md`, `EVOX16_EXECUTION.md`)
  and finished by Claude. It passed every offline gate, was dirty-flashed to slot b, and **boot-looped**:
  `system_server` crashed every ~5 s in `TelecomLoaderService`. The phone was restored to evox15.
- The owner's position, which you must adopt: **treat everything done in evox16 with a grain of salt.**
  The upstream maintainers (Evolution X, LineageOS, AOSP) test on real devices before they push; our
  evox16 changes were never run on a phone. Anything that is not clearly required for klimt to build and
  work on 12.3 counts as "went too far" and should be reverted to upstream. A change is not justified
  merely because it fixes a theoretical bug in upstream code, matches stock HyperOS better, or was
  "reviewed".

## What to produce

1. **Boot-loop root cause.** Determine it independently from the evidence (device logs, the built image,
   the build process). State the exact mechanism, with file/line or log-line citations, and say whether
   any evox16 source change, the upstream 12.3 sources, or our build process caused it.
2. **A verdict for every evox16 change relative to evox15.** For each one: `KEEP` (required for klimt on
   12.3 — say what breaks without it, with evidence), `REVERT` (not needed or went too far), or
   `UNSURE` (what would decide it). Cover at least:
   - the 14 projects in `device/xiaomi/klimt/patches/tree` (BASES, PATCHES.json and the `.patch` files;
     device tree commit `a80d3d101e7d19f6f5460c36cfeabc7b980b5886`),
   - the new forks: `iowaz/android_hardware_xiaomi` (evox16), `iowaz/packages_apps_Settings` (evox16),
     `iowaz/android_system_memory_libdmabufheap` (evox16), and the rebased `build_soong` and
     `frameworks_native` (evox16),
   - device-tree commits after evox15's `a528622`: `1767eb4` (TouchBridge doze double-tap),
     `d8bc99b` (allocator BoardConfig), `0590205` (black AOD product overlay), plus the patch-export
     commits `c2ff11b`, `ddd3d12`, `a80d3d1`,
   - `hardware_interfaces` staying on the 12.2-era `cnb-klimt` fork: is it now behind upstream `cnb`
     in a way that matters?
   - The evox15 picks that evox16 declared "superseded by upstream" (`patches/tree-evox15` in the
     device tree: custom ROM hiding, stagefright symbol hiding, PIF defaults, PduParser and decodeWapPdu
     security fixes, AVRCP ext_attrs, the init property pick). Check that each one really is present in
     the 12.3 sources, or that dropping it loses nothing klimt needs. Also check the claim that both old
     `vendor_evolution` `cnb-klimt` commits are in upstream 12.3.
3. **Process review.** Flaws in the evox16 build/verification process (focused precheck, controller,
   verify.py, image checks) that let a non-booting image be called verified, and what the evox17 process
   must do differently. Be concrete.
4. **The minimal evox17 change set**: the list of local changes that should remain on top of upstream
   Evolution X 12.3 `cnb` for evox17.

Write the full report to
`C:\Users\diogo\Documents\Codex\2026-10-14\ru\work\evox17\codex-review\EVOX16_INDEPENDENT_REVIEW.md`
and a machine-readable summary to `...\codex-review\EVOX16_VERDICTS.json`
(`{"root_cause": "...", "changes": [{"id": "...", "project": "...", "verdict": "KEEP|REVERT|UNSURE", "reason": "...", "evidence": ["..."]}], "process_findings": ["..."], "evox17_minimal_set": ["..."]}`).
Those two files are the only files you may create or modify.

## Where things are

- Source tree (WSL2 Ubuntu-24.04): `/mnt/wsl/evox/src`. Run commands with
  `wsl.exe -d Ubuntu-24.04 -- bash -lc "<command>"` (put long commands in a script file under the
  codex-review folder, which is `/mnt/c/Users/diogo/Documents/Codex/2026-10-14/ru/work/evox17/codex-review`
  inside WSL, and pass `< /dev/null`).
  **The working tree may change while you review** (Claude will start preparing evox17). Read evox16
  sources through the pinned commit SHAs (`git -C <project> show <sha>:<path>`, `git log <sha>`), not the
  working tree. The evox16 pins are in `C:\XiaomiBuilds\debug\evox16\FINAL_SOURCE.json` and
  `...\manifest-final-source.xml`; upstream bases are in the device tree's `patches/tree/BASES`.
- evox16 build output (still evox16 until you finish; do not write to it):
  `/mnt/wsl/evox/src/out/target/product/klimt` (target files under
  `obj/PACKAGING/target_files_intermediates/lineage_klimt-target_files`). Host tools are in
  `/mnt/wsl/evox/src/out/host/linux-x86/bin` (aapt2, simg2img, ...). For large temporary files use
  `/mnt/wsl/build/tmp-codex-review` and delete them afterwards.
- Delivered evox16 ZIP: `D:\WitAquaBuild\out-evox\lineage_klimt-evox16-img.zip`
  (`/mnt/d/WitAquaBuild/out-evox/...`); attempt folder `D:\WitAquaBuild\out-evox\evox16\evox16-attempt01`.
- Build logs: `/mnt/wsl/evox/logs/evox16/` (precheck02..05, attempt01) and `C:\XiaomiBuilds\debug\evox16\`.
- **Phone logs from the boot loop**: `C:\XiaomiBuilds\debug\evox16\device-bootloop-20261014\`
  (logcat-all.txt, logcat-crash.txt, logcat-events.txt, dropbox-system_server_crash.txt, getprop.txt,
  bugreport zip). These contain personal data: quote only the log lines you need, never account names,
  phone numbers, IMEIs or serials.
- Tooling: `C:\XiaomiBuilds\build-setup\evox\evox16\` (precheck.py, controller.py, verify.py,
  image-checks/). Public build docs: `C:\Users\diogo\Documents\Codex\2026-10-14\ru\android_custom_rom_building_klimt`
  (README.md, docs/evox16.md, docs/history.md). Note docs/evox16.md states a root-cause hypothesis; verify
  it rather than trust it.
- GitHub CLI `gh` is logged in (read only for you: no pushes, no repo changes, no issues/PRs).

## Hard rules

- Read-only. Do not run `m`, `make`, `mka`, `repo sync`, `repo init`, `apply.sh`, `git checkout`,
  `git reset`, `git commit`, `git push`, `git am`, or anything that writes to the source tree, the out
  directory, the device tree, the building repository, `C:\XiaomiBuilds`, or `D:\WitAquaBuild`.
- Do not touch the phone (no adb/fastboot).
- Do not print or copy signing keys.
- Cite evidence for every claim; mark anything you could not verify as unverified.
