# evox18: the pipeline test after the reorganization

Status on 2026-10-15: built and image-checked (`evox18-attempt01`, verifier recheck `recheck04`). **Not flashed**
(there is no reason to: it is evox17 again). evox17 stays the build on the phone.

evox18 answers one question: after the [2026-10-15 reorganization](build-pc-layout.md), does the build still
work? Everything moved:
- the two build disks went to `D:\android_rom_building\vhdx-images`;
- the WSL distro and its swap moved;
- `repo`'s manifest source moved;
- the per-build tooling copies became one generic [pipeline](../build-setup/evox/pipeline) that runs straight
  from this repository.

So evox18 is evox17's source built again with the new pipeline. Nothing about the ROM changed.

## Source

The same frozen manifest as evox17 (`diagnostics\builds\evox18\evox18-frozen.xml` is a copy of
`evox17-frozen.xml`): 1,263 projects, SHA-256 `da331623…`. Device tree `43b71ec`, build/soong `ffe1ef0`,
frameworks/native `2341752`. The live tree resolved to exactly these heads before and after the build.

## Build

`bash pipeline/start.sh evox18-attempt01 ...` after `pipeline/ready.py` (seven gates, including "same frozen
source as evox17").
- `m installclean`, then `m updatepackage`: exit 0 in **1h14m58s**, 14,993 Ninja steps. Almost every step
  re-installs files `installclean` removed; nothing in the source changed.
- ZIP: 5,661,592,959 bytes, SHA-256 `c7dcb739905c058dd5e4a5a5269cea8a85f317a85b58288b70c2a415b2065237`.

## Verification, and what the reorganization broke

The first four verification runs stopped before finishing: three on defects of the reorganized pipeline and one
on disk space. Each was fixed, then the same ZIP was re-verified ([`tool_review.py`](../build-setup/evox/pipeline/tool_review.py), `verify.py --recheck`):

1. **The competing-build guard matched my progress watcher.** The verifier refuses to run while anything looks
   like another build, including command lines like `build.sh evoxNN`. The watcher was
   `watch-build.sh evox18-attempt01`. It is now `watch-attempt.sh`, and the pipeline README warns about it.
2. **A local variable shadowed a module.** Making `verify.py` generic added `import paths`, but `main()` later
   built a list called `paths`. Python then treats `paths` as local in the whole function, so the first use
   failed. Fixed, plus a test that rejects any pipeline function assigning a name of an imported module.
3. **A helper left behind by the move.** `legacy/musthold.sh` still called
   `/mnt/c/XiaomiBuilds/build-setup/cpio_extract.py`. The vendor ramdisks were not unpacked, so three retained
   Health checks found no recovery files (162/165 passed). It now calls `build-setup/evox/tools/cpio_extract.py`
   relative to itself, and a test rejects any Windows-drive path in the pipeline outside `D:\android_rom_building`.
4. **Disk space.** `recheck03` stopped at the verifier's start guard (D: 35.8 GB free, 38 required). `build.vhdx`
   is a dynamic VHDX, and it had grown back by about 30 GB during the build and the previous extraction; see
   [the layout notes](build-pc-layout.md#the-2026-10-15-reorganization). Removing `recheck02`'s staged ZIP (an
   exact copy) and its extraction made room.

**`recheck04` passed everything** with the same counts as evox17:
- the must-hold checks: 888 modules, 0 CRC mismatches, kernel `6.6.142-android15-8-klimt-4k`;
- all 165 historical checks;
- the seven image checks: policy 31, patch packaging 33, private compatibility 115, Health 45,
  GMS/themes/apps 674, Doze 62 and install integrity 16. TelecomShim is the only Telecom app, and no package
  appears twice beyond the two evox15 overlay pairs.

[`promote.py`](../build-setup/evox/pipeline/promote.py) then moved the delivery to
`D:\android_rom_building\output-zips\evox18`, with fixed names (`lineage_klimt-evox18-img.zip`,
`lineage_klimt-evox18-flash.bat`/`.sh`, `SHA256SUMS`, `VERIFIED.txt`, ...). Its `.bat` uses
`tools\platform-tools\fastboot.exe`.

## Compared with evox17

Both images were extracted and compared file by file (13,592 files in eight partitions;
`diagnostics/builds/evox18/compare-images-with-evox17.py`, result `IMAGE_DIFF_VS_EVOX17.json` on the build PC):

- **No file was added or removed**, in any partition.
- **Changed:** each partition's `build.prop` and `kheaders.ko` (the kernel-headers module, which embeds its
  build time). In `build.prop` only the build date, the incremental build number (a timestamp) and
  `ro.build.host` differ; the fingerprint is the same.
- **Images:** `dtbo`, `init_boot`, `super_empty`, `fastboot-info.txt` and `android-info.txt` are
  byte-identical. The others differ only through those files and their AVB hashes and signatures.

So the reorganized pipeline produces the same ROM from the same source. The image extractions were deleted
afterwards (without `fstrim`, see [the layout notes](build-pc-layout.md#the-2026-10-15-reorganization)).
