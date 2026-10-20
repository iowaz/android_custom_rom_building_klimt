# evox22: TrickyStore persists the leaf-hacked chain so key read paths agree

Status on 2026-10-20: built and image-checked (`evox22-attempt01`, every check passed on the first attempt),
reviewed (a research pass and an independent adversarial review, both in `diagnostics\builds\evox22`). **Not
flashed, not boot-tested.** It is the owner's call whether to flash and whether to publish the framework commit;
see [Not boot-tested](#not-boot-tested).

evox22 is evox21 plus one framework change, and it is the one scan finding evox21 left open: the TEE
`SELF_CHAIN_SPLIT`. evox21 concluded that finding was the TrickyStore feature being on, clearable from Evolver and
with no build change. The owner chose instead to try fixing it in the build, by porting the fix that
TrickyStoreOSS made for the same probe (`beakthoven/TrickyStoreOSS` commit `3f4faae`) into Evolution X's
in-framework TrickyStore. This build is that attempt. Whether it clears the finding without disturbing Play
Integrity can only be confirmed by a scan on the phone.

| Scan finding (evox21, 2026-10-20 13:23) | Cause | evox22 |
|---|---|---|
| TEE: `SELF_CHAIN_SPLIT` (grant chain 5 certs, owner chain 4) | the in-framework TrickyStore rewrites an attested key's chain only on the JCA owner read; a grant or raw-binder read of the same key returns the genuine stored chain, so the two planes disagree | the rewritten chain is persisted into keystore2 at generation, so every read path returns it (frameworks/base) |
| Custom ROM: `framework-res.apk mapped from 3 devices`; Dangerous Apps: hidden ROM-app UIDs | Evolution X's `Pixelframework-res.apk` file name; the framework's package hiding | owner decision 2026-10-20: leave both, no build change (unchanged from evox21) |

## Source

`diagnostics\builds\evox22\evox22-frozen.xml`: evox21's 1,263 projects, two revisions changed.
`SOURCE_VS_EVOX21.json` checks that only these differ, that each builds on its evox21 commit and that every
worktree is clean:

- **frameworks/base** `e4cc2598` -> `f963d8b1` "TrickyStore: Persist the leaf-hacked chain so all key read paths
  agree" (frameworks/base has no local change before this, so the pin moves off the Evolution X `cnb` head for the
  first time). One commit, three files:
  - `core/java/android/security/trickystore/TrickyStoreService.java`: a new `isLeafHackTarget(String[])` predicate
    that is true only for explicit `LEAF_HACK` targets (`pkg?`), never `AUTO`.
  - `keystore/java/android/security/keystore2/AndroidKeyStoreKeyPairGeneratorSpi.java`: after a real key is
    generated for a `LEAF_HACK` target, the rewritten chain is computed and written back with
    `mKeyStore.updateSubcomponents(...)` — the same call the `GENERATE` path already uses to persist its chain, so
    the owner, grant and raw-binder reads all return the one stored chain.
  - `core/java/android/security/trickystore/CertificateHacker.java`: a guard so the owner read does not rewrite a
    chain that is already rooted in the keybox (a second, randomised ECDSA signature would otherwise diverge from
    the persisted bytes and reopen the split for EC keys).
- **device/xiaomi/klimt** `d71b3e4` -> `5d9feb5` "klimt: patches: Carry the TrickyStore chain-persist framework
  patch": the framework commit goes into `patches/tree` (PATCHES.json, BASES, the format-patch under
  `tree/frameworks/base`, and a README note). `apply.py` reports all four bundle projects as final.

Where they are: the framework commit `f963d8b1` is on top of Evolution X `cnb` `e4cc2598`; it has no fork to live
in yet (there is no `iowaz/frameworks_base`), so the frozen manifest pins it in the local tree only and the device
bundle carries it as `patches/tree/frameworks/base/0001-TrickyStore-Persist-the-leaf-hacked-chain-so-all-key.patch`.
The device tree commit is on `iowaz/android_device_xiaomi_klimt` `evox` once pushed.

### Why the split happens, and why persisting closes it

Evolution X reimplements TrickyStore inside the framework (`core/java/android/security/trickystore/`), not as a
module. In `LEAF_HACK` mode the attested key is a genuine TEE key; the framework rewrites its leaf (same public
key, re-signed by the keybox, keybox chain appended) **only** in `AndroidKeyStoreSpi.engineGetCertificateChain`,
the JCA owner read. A reader that fetches the same key another way — a `Domain.GRANT` descriptor, or the raw
`IKeystoreService` binder — never goes through that method and gets the genuine StrongBox chain. A probe that
generates a key and reads it both ways sees the two disagree: `SELF_CHAIN_SPLIT`.

`GENERATE` mode never split, because it persists its fabricated chain with `updateSubcomponents`, so every plane
reads the same stored bytes. evox22 makes `LEAF_HACK` do the same: persist the rewritten chain at generation. This
is the in-framework equivalent of TrickyStoreOSS `3f4faae`, which "forwards the grant and updateSubcomponent flows
for real keys to the real keystore" — i.e. lets the real keystore be the single source for every read plane. The
alternative, hooking the grant read in Java, cannot work: a probe can call `IKeystoreService` directly and bypass
every client-side hook; only changing what the keystore2 service *stores* reaches all planes.

### Scope: Play Integrity is untouched

The persist is gated on `isLeafHackTarget`, which matches `Mode.LEAF_HACK` only. GMS, Vending and the other `AUTO`
entries in `DEFAULT_TARGET_LIST` never enter the persist branch; their keys are generated by the unchanged
`generateKey(...)` call and their chains are still rewritten transiently on the owner read exactly as before, so
their stored bytes are byte-identical to evox21. Play Integrity keys live under GMS's own UID, Duck Detector's
under its own; persisting one app's chain cannot affect another's. The real TEE key is kept and the rewritten leaf
keeps the genuine public key, so signing with the key is unaffected; a persist failure is caught and key
generation proceeds, so the change can only help, never break, key creation.

### Review, before the build

- `PORTING-PLAN.md`: a research pass (the actual `3f4faae` diff, the grant-plane trace in
  `AndroidKeyStoreProvider`/`KeyStore2`, the recommended approach and its edges).
- `REVIEW.md`: an independent adversarial review. Verdict **SHIP, 0 blocking**, 5 non-blocking (an optional perf
  hoist and doc nits). It checked every cross-file symbol against the live tree (the three files javac), confirmed
  the idempotency guard is correct and reached by both callers, that the `AUTO` path is byte-unchanged, that the
  key stays usable, and that a persist failure cannot corrupt key generation.
- `SOURCE_VS_EVOX21.json`: evox22 is evox21 plus exactly these two commits, each on its evox21 parent, all
  worktrees clean.

`ready.py` passed its eight gates (frozen graph and clean worktrees, patch bundle final, the five semantic source
purposes, staging clean, image checks registered, and the three evidence gates above).

## Build

`bash pipeline/start.sh evox22-attempt01 ...` at 15:04 after `ready.py`: `m installclean`, then `m updatepackage`,
exit 0 at 16:50, `updatepackage` 1h45m06s (Soong re-analysed the tree, then Ninja ran 17,337 steps including
`framework.jar` and the boot image). The controller stayed detached under a WSL keepalive.

- ZIP: 5,661,644,406 bytes, SHA-256 `0b2dece09021c729c67b5c5194c5d03d59120cee3d8c0b01aa9ebe53a923b99d`.

## Verification

**Everything passed on the first verification** (17:30), with evox21's counts: the must-hold checks (888 modules,
0 CRC mismatches, DTB/DTBO identical to the phone's slot b), **194/194 fix checks** (no new check — evox22 adds no
static image invariant; a framework runtime change is not something a static image check can assert), and the
seven image checks (policy 31, patch packaging 33, private compatibility 115, Health 45, GMS/themes/apps 674, Doze
62, install integrity 16). `promote.py` moved the delivery to `output-zips\evox22`.

The built `framework.jar` contains the change (its dex holds `isLeafHackTarget` and the persist log string), so
this is not a stale jar. File by file against evox21 (`filesystem-files.json`, 12,663 files on both, 187 differ,
none added or removed): the only changed jar/apk/apex is `system/framework/framework.jar`; the rest are derived
from it — 77 boot-image `.art`/`.oat`/`.vdex` (framework is on the bootclasspath), 98 app `.odex`/`.vdex`/`.art`
dexpreopted against the changed bootclasspath, the eight `build.prop` build dates, `build-manifest.xml`, the two
`boot-image` profiles, and `kheaders.ko` (embedded timestamps).

## Not build-tested

**Static checks are not a boot test.** This is a change to a security-sensitive framework key path; it has been
reviewed and image-checked, but not run. What it should do, and what to confirm on the phone (details in
`diagnostics\builds\evox22\REVIEW.md`):

1. Flash dirty to slot b with `output-zips\evox22\lineage_klimt-evox22-flash.bat /flash` (no wipe), with
   `output-zips\evox21` ready to restore the same way. Confirm it boots, then the evox20/evox21 checklist
   (fingerprint, AOD, camera, calls).
2. **Play Integrity must be unchanged** — the same BASIC/DEVICE/STRONG verdict as evox21. A drop would mean the
   `AUTO` path was affected (it should be impossible by scope; investigate before anything else).
3. Re-run Duck Detector (TrickyStore on, as evox21's 13:23 scan). Expected: the **TEE `SELF_CHAIN_SPLIT` clears**
   and the owner and grant chains report the same leaf and the same cert count. The other TrickyStore checks stay
   green.
4. Generate an attested key twice in a `LEAF_HACK` app and confirm two `getCertificateChain` reads of an EC key are
   byte-identical (the guard firing), and that a fresh key still signs and verifies.
5. If the scan is worse, or Play Integrity drops, restore evox21 and turn the Evolver TrickyStore switch off
   instead (evox21's path A). Nothing in evox22 is required for the phone to work; it only changes how a
   `LEAF_HACK` app's own key reads back.

## Not build changes

The Custom-ROM `framework-res.apk` maps trace and the Dangerous-Apps hidden ROM-app UIDs are unchanged from
evox21, owner decision to leave both. Vendor build lineage (Task 2) and the ADB-off scan behaviour are as evox21.
