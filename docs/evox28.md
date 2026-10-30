# Evox28 - LineageOS MediaTek vendor policy and a quieter GED KPI probe

Prepared on 2026-10-30 for `lineage_klimt-cp2a-user`, on top of [evox27](evox27.md)'s exact sources (Evolution X cnb
of 2026-10-29). No flash is authorized by this build task.

## Changes against evox27

- **`device/mediatek/sepolicy_vndr`** moves from the evox26/evox27 pin `117a8de2` to the LineageOS `lineage-24.0`
  head `59913a62` (2026-10-28): 53 commits, 38 files, all modifications (no new files). They include MiTEE,
  Trustonic, Trusty and Microtrust TEE label regrouping, MiTEE Secretkeeper and KeyMint V4 service labels,
  sysfs wakeup labels, `persist.vendor.gpu` properties, same-process HAL labels for the Mali and graphics
  libraries, fastbootd dtbo/vbmeta flashing, the MediaTek Codec2 HAL label and `vendor.debug.sf.kickidle.`.
- **`device/xiaomi/klimt`** drops its copies of what that policy now provides: the
  `vendor_mtk_debug_sf_kickidle_prop` declaration and context (LineageOS makes it a restricted property that
  surfaceflinger may read), the composer's `set_prop` for it, and three charger/battery wakeup genfscon lines
  (`sysfs_wakeup` on both sides). The duplicate type is what stopped evox27-attempt01. Kernel label `-ab28`.
- **`frameworks/native`**: libgui probes `/proc/ged` once per process (`std::call_once`), with `O_CLOEXEC`, logs the
  result once at info level and stops if the open fails; the surfaceflinger check reads `/proc/<pid>/cmdline` only
  after a successful open. What libgui sends to the GED driver is unchanged (review 01 findings 5 and 6 of evox27).

## Checks before the build

- An offline replay of the build's own policy commands (m4, checkpolicy, version_policy, secilc) on scratch copies
  of the new sources compiled the whole policy: the full `secilc` link into `precompiled_sepolicy`, which enforces
  the neverallows. The separate `checkpolicy` neverallow pass was not replayable offline; the build runs it.
- `Surface.cpp` compiled alone with the build's exact command (GED KPI on).
- The device patch bundle reports an equivalent final tree for all five projects; the five historical source
  purposes reverse-apply.

Not taken (unchanged from evox27): misakazip's newer device-tree commits. Five need the shared MediaTek/eSIM
components or new blobs; the sixth only adds a MIUI Camera APK patch applied at extraction time, which our
pre-extracted vendor repository does not run.

## Review

`diagnostics\builds\evox28\reviews\06-evox28.md`: **PASS**.
- **Method:** the reviewer rebuilt klimt's vendor_file_contexts with the build's own fc_sort (the old pin reproduces
  evox27's output byte for byte) and compared 6,464 file labels and 1,475 property labels.
- **TEE and keys:** no label change for klimt's TEE, KeyMint, StrongBox, Weaver, Gatekeeper, Identity or fingerprint.
- **Firmware:** `/vendor/firmware` (318 files) moves to the new `vendor_fw_file` type, still readable by the kernel,
  ueventd and vendor domains.
- **Same-process HAL:** `libaal_sec` and `libapusys` become same-process HAL files.
- **Property:** `ro.vendor.mtk_hdr_video_support` changes type but stays settable by vendor_init and readable.
- **Overlap:** the wakeup list only grows; klimt and LineageOS now share no declarations or contexts.

## Status

- **attempt01** (02:23, 2026-10-30) compiled in 1h08m. The merged vendor policy passed the build's own checkpolicy,
  neverallow and policy-test steps.
- **First verification:** stopped on one historical check, the evox12 count of `sysfs_wakeup` genfscon entries
  (exactly 148). The image has 239: 186 from the new MediaTek policy and 53 from klimt. All 56 wakeup paths klimt
  labelled in evox27 are still labelled. The check now expects 239 from evox28 on (148 before); the name is
  unchanged. A diagnostic dry run of the seven image checks on that extraction passed all seven.
- **recheck01 passed:**
  - all 194 historical checks;
  - 112 metadata assertions (kernel `6.6.142-android15-8-gf6a5b29f9fe5-ab28`);
  - all seven image checks;
  - AVB/layout/DTB/DTBO;
  - 888 modules, 0 CRC mismatches.

Delivery: `output-zips\evox28`, 5,645,858,463-byte ZIP, SHA256
`061321a36908dfa487a3c2c2028e05dec7e6e820f74de30bb6a7466b6cad1c1c`, slot-b no-wipe helpers (run the `.bat` by full
path). **Not flashed, not boot-tested**; evox27 is on the phone. Post-flash checks:
`diagnostics\builds\evox28\REVIEW_DISPOSITION.md`.
