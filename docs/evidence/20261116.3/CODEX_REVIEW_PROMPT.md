# Review request: Evolution X upstream merge for klimt (20261113.3 -> 20261116.2)

You are an independent, read-only reviewer. Do not modify any file except `REVIEW.md` in this folder.
Do not access `\\wsl.localhost\...` or any Android source tree; everything you need is in this folder.

## Context

- Device: Xiaomi 15T Pro "klimt", MediaTek (not Qualcomm), Evolution X `cnb` (Android 17, LineageOS 24.0 base,
  AOSP `android-17.0.0_r1`). Builds are plain upstream plus a small set of device-tree-held patches
  (`klimt-patches/PATCHES.json`, applied by `klimt-patches/apply.py`); there are no ROM-source forks.
- The previous boot-tested build is 20261113.3. This refresh syncs every configured upstream. 64 projects changed.
- `INDEX.json` lists each changed project with old/new revision; `diffs/<project>.diff` holds the commit list,
  stat and full diff (old upstream base -> new upstream base; our patches are NOT included in these diffs).
- `device-tree.diff` is our side: the device-tree commits since 20261113.3 (patch rebases/re-exports, the
  frameworks/base keybox hand port and its correction, build labels).
- `klimt-patches/` is the current patch set. Patch classes: `klimt` (device needs) and `personal` (owner's identity
  layer and the owner's TrickyStore keybox monitor feature: frameworks/base 0003 + packages/apps/Evolver).

## Known so far

1. Build 20261116 failed to compile because the hand-ported frameworks/base keybox patch kept only its AIDL hunk.
   Fixed in 20261116.2 (rebuilt from the original export; the new AIDL method is appended after upstream's new
   TrickyStore/DuckRKP methods to keep transaction numbers).
2. Build 20261116.2 failed: `vendor/gms` commit `c90f7fc gms: Bring back AmbientStreaming` adds
   `AmbientStreaming.apk` as a Git LFS pointer, but `.gitattributes` has no LFS rule for it, so the checkout is the
   130-byte pointer text and `aapt2 dump badging` fails. Proposed fix: keep `vendor/gms` at the 20261113.3 revision
   `7ca1155` (drop only that commit) until upstream fixes it.

## What to review

1. **Build breakers**: anything else in these diffs that can fail a klimt build (LFS pointers, missing files,
   renamed/removed modules or dependencies, Soong/Make changes, Kotlin/Java API changes that our patches call,
   prebuilts referenced but absent, product-config changes affecting a MediaTek target).
2. **Interaction with our patches**: read each patch in `klimt-patches/` and check whether upstream changes in the
   same projects (frameworks/base, frameworks/native, lineage-sdk, Settings, Updater, bootable/recovery,
   device/lineage/sepolicy, packages/apps/Evolver, hardware/interfaces, build/soong, build/make, vendor/lineage)
   make a patch redundant, semantically wrong, or conflicting even though it applied. Pay special attention to
   upstream's new TrickyStore keybox setter (`setSpoofTrickyStoreKeyBox`), DuckRKP and sandbox spoof methods in
   frameworks/base and Evolver versus our keybox monitor patch (do both write the same keybox file/setting? races?
   permission checks?). Check the Binder/AIDL ordering claim in item 1.
3. **Runtime and security risks** for an installed, dirty-flashed (no wipe) phone: data migrations, settings
   changes, sepolicy changes, permission changes, behavior changes in SystemUI/Settings/Launcher/telephony/audio.
4. Verify or refute the proposed vendor/gms fix, and say whether any other project should also be held back.

## Output

Write `REVIEW.md` in this folder: a short summary verdict first, then findings ordered by severity
(blocker / high / medium / low / info). For each: project, file(s) and line(s) in the diff, what is wrong, why it
matters on klimt, and the concrete fix you recommend. Say explicitly when something is only a suspicion.
Be concrete; do not pad.
