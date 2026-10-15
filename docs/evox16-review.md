# evox16 review

evox16 was meant to be a simple move to Evolution X 12.3. It boot-looped on the phone (see
[evox16 details](evox16.md#boot-loop-on-the-phone)). This review looked at everything evox16 changed relative to
evox15, the last build that runs on the phone, with one rule: **upstream is more reliable than us**. The Evolution
X, LineageOS and AOSP maintainers test on real devices; none of the evox16 changes ran on a phone. A change stays
only if klimt needs it on 12.3, or if it was already in evox15.

Two reviews were done independently and then merged:

- Claude (this repository's builder) reviewed the sources, the built image and the phone logs.
- An independent Codex session (Codex CLI 0.162, GPT 6.1 Sol, reasoning effort high, read-only) got the same
  evidence locations and the same rule, but not Claude's conclusions.
  Its full report is in [evox16-review/codex-independent-review.md](evox16-review/codex-independent-review.md)
  and [codex-verdicts.json](evox16-review/codex-verdicts.json). The merged decision record is
  [disposition.json](evox16-review/disposition.json).

## Why it boot-looped

**Our build process put a stray APK into the image.** Neither Evolution X nor any of our source patches caused
the boot loop. Both reviews reached the same conclusion separately.

1. Android 17 has two Telecom app variants, selected by the release flag `RELEASE_TELECOM_MAINLINE_MODULE`.
   It is `true` for `cp2a`, so the product installs `TelecomShim` and system_server runs the mainline
   `TelecomLoaderService`. The legacy `Telecom` app (returns an `ITelecomLoader` binder) is not part of the product.
2. evox16's focused precheck compiled the changed modules with `m <modules>` before the full build. Our Telecomm
   patch put `Telecom` on that list, and `m Telecom` built and **installed** it into
   `out/target/product/klimt/system/priv-app/Telecom` at 18:11.
3. The full build was incremental. It installed `TelecomShim` (19:20) but never removed `Telecom`, because
   Telecom was never in the product's install list. The images are packed from those staging directories, so
   `system.img` shipped both ([listing](evox16-bootloop/system-img-telecom.txt),
   [APK identities](evox16-bootloop/telecom-apks.txt)). The precheck also left
   `system/bin/property_info_checker` ([all strays](evox16-bootloop/staged-not-installed.txt)).
4. Both APKs are `com.android.server.telecom`, version 37. PackageManager scanned `Telecom` first and
   skipped TelecomShim ([log](evox16-bootloop/packagemanager.txt)):
   `Failed to scan /system/priv-app/TelecomShim: Application package com.android.server.telecom already installed.  Skipping duplicate.`
5. The mainline loader registered the legacy app's binder as the `telecom` service. The first
   `TelecomManager.getSimCallManager()` call reached the wrong interface, and system_server crashed with
   `SecurityException: Binder invocation to an incorrect interface`. That repeated 53 times
   ([first crash](evox16-bootloop/system_server-crash.txt)).

evox15 had no precheck, and its `system.img` has `TelecomShim` only.

**The verifier saw it and passed anyway.** The evox16 image check wrote the duplicate into
[`image-apk-duplicate-packages.json`](evox16-bootloop/verifier-duplicate-packages.json). By design it was evidence
only, not a gate, and nobody read it.

The earlier hypothesis in [evox16.md](evox16.md), "a mismatch between the framework and the Telecom app in the
12.3 sources", was wrong. The sources are consistent; the image was not.

## What was kept and what was reverted

| Change in evox16 | Claude | Codex | evox17 |
|---|---|---|---|
| frameworks/base, Sandbox, AppLocker: per-user configuration and permission checks | revert | revert | **upstream** |
| ThemeStore: install/uninstall callbacks, icon packs (4 patches) | revert | revert | **upstream** |
| Telecomm: call-flash torch rewrite and its log fix | revert | revert | **upstream** |
| Bluetooth: accessory without a device class | revert | revert | **upstream** |
| Seedvault: WebDAV out-of-space error | revert | revert | **upstream** |
| libcore: 12.2's root-hiding `UnixFileSystem` re-added on AOSP | revert | revert | **upstream** (12.3 moved libcore to AOSP on purpose) |
| system/sepolicy: keep `su` out of user-build permissive domains | revert | revert | **upstream**: Evolution X 12.3 makes `su` permissive on user builds, apparently for root solutions; evox17 reports it |
| Settings: carrier-scan fallback, and its fork | revert | revert | **upstream** |
| hardware/xiaomi: bounded UDFPS sysfs reads, and its fork | revert | revert | **upstream** `af5766ac`, the same commit evox15 used |
| TouchBridge: arm the panel for 12.3's separate doze double-tap setting | revert | revert | **evox15 bridge** (double tap to wake works as before) |
| libdmabufheap: legacy allocator selector, BoardConfig flag and fork | revert | revert | **upstream** ION-free (see below) |
| Product overlay keeping AOD black | keep | revert | **kept** |
| frameworks/native: libui SMPTE 2094-50 guard (evox13) | keep | revert | **kept** |
| build/soong: MIUI boot jar packages | keep | keep | kept |
| hardware/interfaces: AIDL-only lights (evox1/evox3) | keep | keep | kept |

**Allocator.** The only evox16 change with a plausible boot risk was the allocator. evox16 kept the legacy
implementation, whose exported symbols are identical to evox15's. LineageOS's default build is ION-free, but it
keeps every `BufferAllocator` entry point "for binary compatibility". Of the 57 proprietary libraries that load
`libdmabufheap.so`, the symbols they can only resolve from it come to 15, and all are defined in the
ION-free sources. The 14 blobs that call `ion_*` link `libion.so` themselves. So evox17 uses upstream, and an
image check fails the build if the packaged vendor library is missing any of those 15 symbols.

**Where the reviews disagreed:**
- *Black AOD.* `config_dozeSupportsAodWallpaper` declares what the display supports. The klimt tree has set it to
  false since evox8, when AOD moved to the panel's own doze mode and was tested on the phone. Evolution X 12.3 sets
  it true for every device in a common overlay that outranks device overlays. Without the product overlay the
  phone would quietly change behaviour from evox15. It is resource-only, so it stays.
- *SMPTE 2094-50 guard.* This was not an evox16 addition. It is the evox13 fix that ran on the phone through
  evox15; without it SurfaceFlinger logged about 750 mapper errors a minute. The code is identical.
- *Codex's two "hidden" base changes.* Codex flagged a dumpstate change in the frameworks/native base and a
  `gen_build_prop` change in the build/soong base as local. Both bases are the current Evolution-X `cnb` heads,
  committed by Evolution X maintainers, so they are upstream and stay.

**Confirmed, not changed:**
- Every evox15 pick that evox16 declared superseded is really in the 12.3 tree: each old patch reverse-applies
  cleanly.
- `vendor_evolution` stays on upstream; both old `cnb-klimt` values are in 12.3.

## What changes in the process

- **No focused precheck.** Its module goals install into the same staging directories the images are packed from.
  The full build compiles everything anyway.
- **`m installclean` before every build.** The wrapper then refuses to continue if any staged partition survived,
  so the image only holds this build's installs.
- **A new `install_integrity` image check**, which fails on the evox16 output and image:
  - every staged file must be in this build's install list, kernel module trees excepted;
  - the image's APK set must equal the staged one;
  - no package may be installed twice (only the two overlay pairs that evox15 already had are allowed);
  - the Telecom app must match `RELEASE_TELECOM_MAINLINE_MODULE`.
- **Checks that only proved our optional patches were installed are gone** (su gating, libcore root hiding, legacy
  allocator, doze OR). They now check that those projects are the reviewed upstream commits.
- **Honest labels.** The verifier's marker now says "static image checks passed, NOT boot-tested". Only the phone
  can say more.

Codex also recommended a first-boot checklist on the phone: `sys.boot_completed=1`, a stable system_server, a
single Telecom package, no incorrect-interface crash, then calls, SIM/eSIM, graphics, camera, fingerprint, AOD
and charging. See [evox17](evox17.md).
