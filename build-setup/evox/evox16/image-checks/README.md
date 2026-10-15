# Evox16 supplemental producer/image checks

`check_image.py` implements all six `verify.image_checks` coverage names. It is
post-build tooling, and it has not been run against an Evox16 image. Run one mode
per verifier entry, with the existing `EVOX_EXTRACT`, `EVOX_TMP`, `EVOX_READY` and
`EVOX_REPORT` environment. It writes `supplemental-<mode>.json` plus numbered raw
command reports into the verifier report directory. Each mode creates a new
temporary directory; an existing directory blocks accidental reuse.

The accompanying `IMAGE_CHECKS.json` contains the six argv/hash registrations.
The independently reviewed build-readiness record must import those entries
after any final checker corrections. `references.json` is bound by an exact
SHA256 literal inside the checker; no external mutable evidence can silently
change its required values.

| Coverage | Actual evidence |
|---|---|
| policy | Current Ninja normal-policy compiler command, every corresponding packaged CIL/install/producer hash, recompilation of packaged CIL to the current binary, normal/recovery exact empty permissive inventories, binary policy access rules, generated contexts, real root analyzer call. |
| patch_packaging | MIUI installed boot JAR DEX packages and actual BootJars membership/allowlist; installed libui producer, Gralloc5 source edge and matching stripped/unstripped .text, compiled guard/list/getter/unsupported-return evidence; stock AIDL lights producer/ELF/metadata and absence of generic services; entire libcore tree equals the accepted baseline tree. |
| private_compatibility | All 22 pinned proprietary source/installed/image hashes; actual ELF DT_NEEDED and Build IDs; all five allocator legacy files; current independent Soong selectors, compiled source edges and actual ion_open stubs; selected custom Wi-Fi shim producer, export and stock library target. |
| health_semantics | Exact unchanged accepted semantic source content, current normal/recovery producer/install/image hashes and source edge; matching producer/unstripped .text; interpretation of actual UpdateHealthInfo AArch64 instructions over eight current inputs, average=0 and TTF=-1; direct getter normalization/INT_MIN exception and average unsupported; actual current sysfs path. Existing legacy checker retains RC/VINTF/unique service checks. |
| gms_themes_apps | Current selected package inventory; actual Soong and Make/Ninja selected GMS APK producer/source payload bindings; GMS binaries rather than LFS pointers; installed Google permissions; ThemeStore APK/manifest/grants and compiled SettingsGoogle/Evolver explicit component closure; Canvas unselected; obsolete ThemeIcons consumers unselected; seven measured retired GMS installation paths absent; actual partition-filesystem APK/package/duplicate inventories; parsed protected catalog and binary theme assets. |
| doze_packaging | TouchBridge producer/manifest/DEX and interpretation of compiled Java gesture bytecode for all four wake/doze combinations; active-user observer/FOD independence; current selected UDFPS/sensor/fingerprint producers and wake sensor identity/hals route; real packaged framework/RRO resource defaults resolved by packaged partition order/config/static priorities; current Doze/UDFPS properties; selected SystemUIGoogle DozeService. |

`vendor/themes` is a protected catalog/binary-assets repository. It contains no
Soong namespace/module and has no installed theme-catalog producer. The checker
does not invent either. Evolver resources are compiled into SettingsGoogle;
Evolver does not produce a separate APK. ThemeStore is opened by an explicit
Settings component, so a launcher intent filter is not required.

The narrow old-artifact fixture contains five actual Evox15 APK installation
paths and two actual XML installation paths, with every old file SHA256 measured
by root from the accepted extraction. It rejects any file or link at those
retired paths, regardless of its current bytes, and requires all seven removed
module names to remain unselected. `preinstalled-packages-pixelsystemservice.xml`
is still a current source artifact and is explicitly excluded. No ThemeIcons or
IconPack path was found by the baseline name filter; no unproven old ThemeIcons
installation path is invented. The measured packet is preserved in
`OBSOLETE_BASELINE_CAPTURE.json` and embedded in the bound reference fixture.

`image-apk-inventory.json` and `image-apk-duplicate-packages.json` are written
before obsolete-path rejection so a failed candidate retains this evidence.
The inventory covers every directly extracted partition `.apk`, including
symlink records without following external targets. APKs inside mounted APEX
payloads are outside this direct filesystem inventory. Package duplication is
recorded for review; it is not blindly rejected because a reviewed generic/Pixel
SetupWizard or split/stub layout may contain the same package name.

The expected normal and recovery permissive sets are both empty, measured in
`baseline/POLICY_REFERENCE.json` before Evox16 compilation. Existing source
backuptool/recovery exceptions are not evidence that those domains actually ship
permissive. The fixture preserves that baseline record and its original digest.

Exit status 1 means a stated artifact/source invariant failed. Exit status 2 means
missing tools/evidence or unsupported compiler/layout output; this must be
diagnosed as a checker limitation before declaring an image defect. Exit status
3 is an unexpected checker error. All fail closed. No path can emit the main
VERIFIED marker or invoke a build, flashing command, device operation or fetch.

The AArch64 Health evaluator currently knows HealthInfo offsets 0x24/0x50/0x90
from the accepted compiled producer. A changed layout or opcode is a tooling
failure that requires an independent reviewed adaptation. Gralloc binary checks
use the mapper v5 table offsets 0x48/0x60 and type 24; the source semantic gate
continues to carry supported/unsupported/list-error behavior tests. This checker
does not claim to replace those offline semantic tests.

The Doze resource resolution follows current `OverlayConfig` behavior for
partition overlay directories, config/merge files, static priorities and the
optional packaged partition order. It records every relevant enabled overlay
and effective value in `doze-overlay-resolution.json`. Actual user-controlled
overlay selections/settings and mounted APEX overlay resources are not executed
or modeled here; if such an overlay is selected and can affect one of these
resources, an additional exact producer/resource check is required before
claiming complete effective coverage. A source XML conflict alone is not a
failure; only the resolved image default is asserted. A wrong inherited default
does not by itself establish an introduced regression.

The existing 165 historical checks, AVB/layout/DTB/DTBO/888 modules, HIS/Health
RC/VINTF producer checker and frozen before/after manifests remain required.
Neither these supplemental checks nor a successful build establish device
runtime AOD/fingerprint/camera/charging validation.

Helper and negative tests:

```bash
python3 -B /mnt/c/Users/diogo/Documents/Codex/2026-10-14/ru/work/image_checks/tests.py
```

The original 32 tests passed on Linux. The updated 40-test suite was run using
the local Windows Python while Ubuntu transport was unavailable: 39 executed
tests passed, and the real filesystem symlink fixture was skipped because the
host lacks symlink privilege (WinError 1314). A separate broken-symlink trait
fixture passed. No host permission was changed; the real POSIX symlink fixture
remains pending the next Linux rerun. The cases include injected artifacts at
each of the seven exact retired paths and preservation of the retained XML,
wrong producer/install/image bytes, duplicate
modules, incorrect ownership/Ninja binding, incorrect bridge OR behavior and
namespace, Health polarity/average/TTF mutations, unsupported code generation,
resource/property/manifest faults, and static/configured overlay precedence.
`TEST_RESULTS.json` explicitly limits that result to helper/fixture tests.
