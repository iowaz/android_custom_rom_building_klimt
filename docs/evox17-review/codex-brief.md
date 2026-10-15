# Independent review of the evox17 source and tooling — READ-ONLY

You are an independent reviewer. A build (`evox17-attempt01`) is running right now in WSL; do not disturb it.

## Background

- Device: Xiaomi 15T Pro (klimt), Evolution X 12.3 (`cnb`, Android 17), user build with private keys.
- evox15 (12.2) is the last build that runs on the phone. evox16 (12.3) boot-looped. A previous review (yours,
  as a separate Codex session, plus Claude's) found the cause: the focused precheck's `m Telecom` installed the
  legacy Telecom app into the staging directory and the incremental build packed it next to TelecomShim. That
  review is in `C:\Users\diogo\Documents\Codex\2026-10-14\ru\work\evox17\codex-review\EVOX16_INDEPENDENT_REVIEW.md`;
  the merged decisions (including where Claude disagreed with it, and why) are in
  `C:\Users\diogo\Documents\Codex\2026-10-14\ru\work\evox17\EVOX16_REVIEW_DISPOSITION.json` and
  `C:\Users\diogo\Documents\Codex\2026-10-14\ru\android_custom_rom_building_klimt\docs\evox16-review.md`.
- The owner's rule: upstream maintainers test on devices, our changes are untested; keep only what klimt needs.

## What to review

1. **Source.** Does the frozen evox17 source match the stated minimal set and nothing else?
   - Frozen manifest: `C:\XiaomiBuilds\debug\evox17\evox17-frozen.xml` (live tree `/mnt/wsl/evox/src` is synced to it;
     `C:\XiaomiBuilds\debug\evox17\FINAL_SOURCE.json`, `FROZEN_CHANGES.json`).
   - Generator: `C:\XiaomiBuilds\build-setup\evox\evox17\make-frozen.py`.
   - Device tree commits `1e31192`, `6339c91`, `43b71ec` on top of `a80d3d1` in `/mnt/wsl/evox/src/device/xiaomi/klimt`
     (also on GitHub `iowaz/android_device_xiaomi_klimt` branch `evox`). Compare the device tree with evox15's
     `a528622`.
   - Public snapshot `...\android_custom_rom_building_klimt\manifests\snapshots\evox17.xml` and
     `manifests/local_manifests/klimt.xml`.
   - Is anything left that is not upstream and not justified? Is anything reverted that klimt needs on 12.3?
     Pay special attention to the allocator decision (ION-free upstream libdmabufheap; see the disposition), the
     `su` permissive domain now coming from upstream, and the two items Claude kept against your earlier advice
     (black-AOD product overlay, SMPTE 2094-50 guard). Give your verdict on those again with the new evidence.
2. **Build process and checks** in `C:\XiaomiBuilds\build-setup\evox\evox17\` (compare with the evox16 copy in
   `C:\XiaomiBuilds\build-setup\evox\evox16\`): `build.sh` (installclean), `launch.py`, `verify.py`,
   `image-checks/check_image.py` (new `install_integrity` mode, changed `policy`, `patch_packaging`,
   `private_compatibility`, `doze_packaging`), `image-checks/references.json`, `image-checks/tests.py`.
   Look for bugs that would make a correct evox17 image fail (false alarm) or let a bad one pass (missed defect),
   e.g. path handling, the `.installable_files` parsing, symlinks, kernel-module allowance, duplicate allowlist,
   the Telecom variant gate, the expected permissive set `{'su'}` for normal and recovery policy, the 15 allocator
   symbols. Evidence of the new gate failing on evox16: `C:\XiaomiBuilds\debug\evox17\install-integrity-negative-evox16\`.
   The readiness record is `C:\XiaomiBuilds\debug\evox17\BUILD_READY.json` (generator
   `C:\Users\diogo\Documents\Codex\2026-10-14\ru\work\evox17\make_build_ready17.py`).
3. **Anything else** that could make evox17 fail to boot or misbehave on the phone compared with evox15.

## Output

Write `C:\Users\diogo\Documents\Codex\2026-10-14\ru\work\evox17\codex-review-evox17\EVOX17_INDEPENDENT_REVIEW.md` and
`...\codex-review-evox17\EVOX17_FINDINGS.json`
(`{"findings":[{"id":"...","severity":"blocker|high|medium|low","area":"source|tooling|process","summary":"...","evidence":["..."],"recommendation":"..."}],"verdicts":{"black_aod":"KEEP|REVERT","smpte_guard":"KEEP|REVERT","allocator_upstream":"OK|NOT OK","su_upstream":"OK|NOT OK"}}`).
Those two files are the only files you may create or modify.

## Hard rules

- Read-only. Do not run `m`, `make`, `repo`, `apply.sh`, `git checkout/reset/commit/push/am/fetch`, or anything that
  writes to `/mnt/wsl/evox`, `/mnt/wsl/build`, `C:\XiaomiBuilds`, `D:\WitAquaBuild`, the device tree or the build
  repository. Do not touch processes (no kill) — the build is running. Keep CPU use modest; do not run heavy
  tools such as ninja on the combined graph while the build runs.
- `out/` currently holds a build in progress (evox16 leftovers are being replaced); do not draw conclusions from
  partial outputs. Read sources through git (`git -C <project> show <sha>:<path>`).
- WSL commands: `wsl.exe -d Ubuntu-24.04 -- bash -lc "<command>"` with `< /dev/null`, long commands in a script file
  in your output folder (`/mnt/c/Users/diogo/Documents/Codex/2026-10-14/ru/work/evox17/codex-review-evox17`).
- `gh` is logged in; read-only use only.
- No phone access. Do not print or copy signing keys. Cite evidence for every claim.
