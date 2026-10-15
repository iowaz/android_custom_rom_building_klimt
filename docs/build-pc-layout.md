# The build PC's layout

Since 2026-10-15 everything on the Windows side lives in one folder, `D:\android_rom_building`
(`/mnt/d/android_rom_building` in WSL). Before that it was spread over `C:\XiaomiBuilds` (a junction to
`D:\XiaomiBuilds`), `D:\WitAquaBuild`, `D:\EvoXBuild`, `C:\adb`, `C:\WSL`, `C:\tmp`, `C:\xu`, `Downloads`,
the WSL distro's default place in `AppData` and the Codex session folders.

```
D:\android_rom_building\
  README.md               the map, and how to flash
  output-zips\<build>\    the image ZIP, its flash helpers, SHA256SUMS, VERIFIED.txt, RESULTS.json ...
  tools\platform-tools\   adb.exe, fastboot.exe (used by the flash helpers)
  tools\                  also miflash_unlock\ (6.5 and 7.6), ghostlock\, drivers\ (Xiaomi USB drivers)
  vhdx-images\            source.vhdx (/mnt/wsl/evox), build.vhdx (/mnt/wsl/build), wsl-swap.vhdx,
                          wsl-ubuntu-24.04\ext4.vhdx (the distro)
  repositories\           this repository (the pipeline runs from it), the frozen-manifest repository,
                          a local clone of xiaomi-unlock-helper
  diagnostics\            builds\<build>\ (readiness, reports, flash logs), device\, codex-sessions\, logs\
  backups\                PartitionsBackup (the phone's partitions), stock-firmware, signing-keys, boot-images
  archive\                the WitAqua era, old notes, the scripts as they were before the move
  scripts\                mount-disks.ps1, wsl-keepalive.ps1, watch-attempt.sh, one-time\ (this move)
  to-delete\              obsolete files that exist nowhere else; the owner deletes them
```

The flash helpers in `output-zips\<build>` use `tools\platform-tools\fastboot.exe` (builds from evox18 on).
After a reboot, `scripts\mount-disks.ps1` (elevated) attaches both build disks.

## Inside the disks

| Disk | Mount | Contents |
|---|---|---|
| `source.vhdx` (200 GB) | `/mnt/wsl/evox` | `src/` (the Android tree, `.repo` 53 GB), `logs/<build>/<attempt>/` (build and verify logs), `archive/` (WitAqua-era manifests) |
| `build.vhdx` (480 GB) | `/mnt/wsl/build` | `evox-out/` (`src/out`), `ccache/` (20 GB cap), `compare/{author,b9,live,tools}` (reference images for the must-hold checks), `compare/<build>/` (image extraction scratch), `firmware/` (the unpacked HyperOS OTA), `archive/` |

## The 2026-10-15 reorganization

Done in this order (logs in `diagnostics\logs`, scripts in `scripts\one-time`):

1. **Scratch inside the disks removed** (all regenerable from a ZIP or the source):
   - image extractions of evox16 (53 GB), evox15 (18 GB) and the first evox17 attempt (17 GB);
   - evox16's parked projects and patch replay (11 GB);
   - old siso logs.

   Then `fstrim` (113 GiB and 27 GiB trimmed).
2. **One elevated script** ([`relocate-vhdx.ps1`](../build-setup/windows/relocate-vhdx.ps1)) compacted the two
   dynamic VHDX files with `diskpart compact vdisk`: `build.vhdx` went from 451.8 GB to 390.3 GB and
   `evox.vhdx` from 183.9 GB to 174.9 GB. It then moved them into `vhdx-images` (the source disk is now
   `source.vhdx`), moved the swap file and the distro (`wsl --manage --move`), and attached the disks again
   under the same WSL names, so nothing inside WSL changed.
3. **Exact duplicates removed** after a SHA-256 comparison:
   - four extra copies of the evox16 ZIP and three of the evox17 ZIP (the attempt and recheck copies, and the
     Codex session's copies);
   - an 18 GB copy of the PartitionsBackup, identical file for file.

   About 50 GB in all, 10.8 GB of it on C:.
4. **Everything else moved**, nothing deleted:
   - per-build records went to `diagnostics\builds\<build>`, tools to `tools`, backups to `backups`;
   - the klimt Codex sessions went to `diagnostics\codex-sessions`, and this repository and the
     frozen-manifest repository to `repositories` (`repo`'s manifest URL was updated);
   - unique but obsolete files went to `to-delete` (the evox16 boot-loop ZIP, the WitAqua v4.0 ZIP, evox16's
     source bundles, the old `C:\XiaomiBuilds`, old platform-tools downloads), 17.4 GB for the owner to delete.
5. **After evox18, the last strays** (`reorganize-windows-phase-c.ps1`): `C:\tmp` (a device-diagnostics folder,
   an adb log, a GhostLock boot payload), `C:\xu\repo` (the xiaomi-unlock-helper clone), the Mi Unlock 7.6 tool
   and Xiaomi drivers from `Downloads`, and two more klimt Codex sessions. Each file was hash-checked at the
   destination before its source was removed; Mi Unlock 6.5 in `Downloads` was an exact copy and was removed.

Result: D: free space went from 47 GB to 71 GB, and C: gained about 94 GB: the swap file (48 GB) moved to D:,
plus the duplicate ZIPs and the old copies. evox18's build, its ZIP and its extractions then took D: back to
27.6 GB free (`build.vhdx` 425.8 GB, 251 GB used inside).

**The compaction gain is temporary.** Both build disks are dynamic VHDX files. `fstrim` unmaps freed blocks and
`diskpart compact vdisk` gives them back to D:, but the next build or image extraction writes to free blocks
again, and each newly written block grows the file. evox18's build and one extraction grew `build.vhdx` by
about 30 GB. To keep D: from filling:
- delete image extractions under `/mnt/wsl/build/compare/<build>` once a build is promoted, and do *not* run
  `fstrim` afterwards: blocks that stay allocated are reused without growing the file;
- when D: does get tight, run the compaction part of
  [`relocate-vhdx.ps1`](../build-setup/windows/relocate-vhdx.ps1) (elevated; it unmounts the disks) after
  `fstrim`.

A build does not start below 45 GB free on D: (set by `ready.py`), and the verifier does not start below 38 GB.

The build scripts were reorganized at the same time: one generic [pipeline](../build-setup/evox/pipeline)
instead of a copy per build, and [evox18](evox18.md) was built with it from evox17's source to prove that
nothing broke.
