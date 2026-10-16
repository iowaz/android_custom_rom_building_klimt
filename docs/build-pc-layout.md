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
  vhdx-images\            build.vhdx (/mnt/wsl/build, with the tree bind-mounted at /mnt/wsl/evox),
                          wsl-ubuntu-24.04\ext4.vhdx (the distro)
  repositories\           this repository (the pipeline runs from it), the frozen-manifest repository,
                          a local clone of xiaomi-unlock-helper
  diagnostics\            builds\<build>\ (readiness, reports, flash logs), device\, codex-sessions\, logs\
  backups\                PartitionsBackup (the phone's partitions), stock-firmware, signing-keys, boot-images
  archive\                the WitAqua era, old notes, the scripts as they were before the move
  scripts\                mount-disks.ps1, wsl-keepalive.ps1, watch-attempt.sh, one-time\ (this move)
```

The one exception is WSL's swap file, `C:\WSL\swap.vhdx` (`swapFile` in `%USERPROFILE%\.wslconfig`): it is on
C: on purpose, a different drive from the build disks, so paging during the soong analysis does not compete with
the build's I/O on D:. WSL creates the file when it is missing; it grows up to the 48 GB of `swap=`.

The flash helpers in `output-zips\<build>` use `tools\platform-tools\fastboot.exe` (builds from evox18 on).
After a reboot, `scripts\mount-disks.ps1` (elevated) attaches the build disk and bind-mounts the tree.

## Inside the disk

Since the evening of 2026-10-15 there is one build disk, `build.vhdx` (dynamic, 640 GB maximum), attached at
`/mnt/wsl/build`:

| Folder | Seen as | Contents |
|---|---|---|
| `evox/` | `/mnt/wsl/evox` (a bind mount) | `src/` (the Android tree, `.repo` 53 GB), `logs/<build>/<attempt>/` (build and verify logs), `archive/` (WitAqua-era manifests) |
| `evox-out/` | `/mnt/wsl/evox/src/out` (a symlink) | the build output |
| `ccache/`, `compare/`, `firmware/`, `archive/` | | ccache (20 GB cap); `compare/{author,b9,live,tools}` (reference images for the must-hold checks) and `compare/<build>/` (image extraction scratch); the unpacked HyperOS OTA; WitAqua-era files |

The tree used to have its own disk, `source.vhdx` (200 GB), mounted at `/mnt/wsl/evox`. Every script still uses
that path: about twenty of them name `/mnt/wsl/evox/src`, `build.sh` refuses to run anywhere else, the controller
requires `/mnt/wsl/evox` to be a mount point, and the build output and ccache record the tree's absolute path. A
bind mount keeps all of that true; a symlink would fail the controller's mount-point check.

## The 2026-10-15 reorganization

Done in this order (logs in `diagnostics\logs`, scripts in `scripts\one-time`):

1. **Scratch inside the disks removed** (all regenerable from a ZIP or the source):
   - image extractions of evox16 (53 GB), evox15 (18 GB) and the first evox17 attempt (17 GB);
   - evox16's parked projects and patch replay (11 GB);
   - old siso logs.

   Then `fstrim` (113 GiB and 27 GiB trimmed).

   One thing in the parked projects was not scratch: `vendor/xiaomi/klimt`'s git-lfs store
   (`.repo/projects/vendor/xiaomi/klimt.git/lfs`) was a symlink into them. The checked-out `MiuiCamera.apk`
   stayed intact, so evox18 built fine, but every git-lfs operation on it failed. This was found in step 7 and
   repaired: `lfs` became a real folder, as in the tree's other LFS projects, and the object was stored again
   from the checked-out file after its SHA-256 matched the pointer in HEAD (`fix-klimt-vendor-lfs.sh`). Before
   deleting scratch, look for symlinks into it (`find /mnt/wsl/evox -lname '*<folder>*'`).
2. **One elevated script** ([`relocate-vhdx.ps1`](../build-setup/windows/relocate-vhdx.ps1)) compacted the two
   dynamic VHDX files with `diskpart compact vdisk`: `build.vhdx` went from 451.8 GB to 390.3 GB and
   `evox.vhdx` from 183.9 GB to 174.9 GB. It then moved them into `vhdx-images` (the source disk is now
   `source.vhdx`), moved the swap file and the distro (`wsl --manage --move`), and attached the disks again
   under the same WSL names, so nothing inside WSL changed. (The swap went back to C: that evening, see below.)
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
     source bundles, the old `C:\XiaomiBuilds`, old platform-tools downloads), 17.4 GB, which the owner then
     deleted.
5. **After evox18, the last strays** (`reorganize-windows-phase-c.ps1`): `C:\tmp` (a device-diagnostics folder,
   an adb log, a GhostLock boot payload), `C:\xu\repo` (the xiaomi-unlock-helper clone), the Mi Unlock 7.6 tool
   and Xiaomi drivers from `Downloads`, and two more klimt Codex sessions. Each file was hash-checked at the
   destination before its source was removed; Mi Unlock 6.5 in `Downloads` was an exact copy and was removed.
6. **The swap back to C:** (the owner's choice: a different drive from the build disks). `.wslconfig` now says
   `swapFile=C:\\WSL\\swap.vhdx`; after `wsl --shutdown` WSL created the new file and attached 48 GB of swap,
   and the old 48 GB `vhdx-images\wsl-swap.vhdx` was removed. (When WSL had started earlier that evening with
   the file on D:, `/proc/swaps` was empty: it was running without swap.)
7. **The source disk merged into the build disk** (`merge-source-into-build.sh`, `merge-source-switch.ps1`,
   both also in [`build-setup/windows`](../build-setup/windows)), so the tree and the build share one pool of
   free space (the source disk was 84% full) and the space already allocated inside `build.vhdx` gets reused:
   - every project's HEAD and dirty state was recorded first (1,263 projects, all clean);
   - `rsync -aHAX --numeric-ids` copied `/mnt/wsl/evox` into `/mnt/wsl/build/evox`: 2,203,608 entries,
     171.3 GB, 1 h 24 min. `build.vhdx` grew only 40.9 GB, because the copy reused space freed inside it;
   - a second pass, `rsync -c -n -i --delete`, compared every file's contents and every attribute (times,
     mode, owner, ACLs, xattrs) and listed nothing;
   - elevated: `wsl --shutdown`, `diskpart expand vdisk maximum=655360` (640 GB, from 480), and the new
     [`mount-disks.ps1`](../build-setup/windows/mount-disks.ps1), which attaches `build.vhdx` and bind-mounts
     `/mnt/wsl/build/evox` at `/mnt/wsl/evox`; then `resize2fs` grew the ext4 to 629 GB while mounted;
   - checked at the old path: the bind mount (it survives a distro restart, so `/etc/fstab` is not needed),
     the same HEADs and clean state in all 1,263 projects (after the LFS repair of step 1), the pipeline tests
     (20/20 and 45/45), and `lunch lineage_klimt-cp2a-user` from `/mnt/wsl/evox/src`;
   - `source.vhdx` (174.9 GB) was then deleted.

Result: D: had 47 GB free before the reorganization and 223.8 GB at the end, after evox18's build, ZIP and
extractions, the deletion of `to-delete`, the swap's return to C: and the merge (`build.vhdx` 470 GB, 416 GB
used inside, 640 GB maximum; full, it would still leave about 54 GB on D:).

**The compaction gain is temporary.** The build disk is a dynamic VHDX file. `fstrim` unmaps freed blocks and
`diskpart compact vdisk` gives them back to D:, but the next build or image extraction writes to free blocks
again, and each newly written block grows the file. evox18's build and one extraction grew `build.vhdx` by
about 30 GB. To keep D: from filling:
- delete image extractions under `/mnt/wsl/build/compare/<build>` once a build is promoted, and do *not* run
  `fstrim` afterwards: blocks that stay allocated are reused without growing the file;
- when D: does get tight, compact: `sudo fstrim -v /mnt/wsl/build` in WSL, stop the keepalive, then elevated
  `wsl --shutdown`, `diskpart` with `select vdisk file="<build.vhdx>"`, `attach vdisk readonly`,
  `compact vdisk`, `detach vdisk`, and `scripts\mount-disks.ps1`. Compaction only frees whole 32 MB VHDX
  blocks, so it gives back part of what was trimmed (61 of 113 GB in the morning). These are steps 2, 3 and 7 of
  [`relocate-vhdx.ps1`](../build-setup/windows/relocate-vhdx.ps1). Do not run that whole script again: it
  is the record of the one-time move: its step 5 would put the swap back on D:, and it still expects
  `source.vhdx`.

A build does not start below 45 GB free on D: (set by `ready.py`), and the verifier does not start below 38 GB.

The build scripts were reorganized at the same time: one generic [pipeline](../build-setup/evox/pipeline)
instead of a copy per build, and [evox18](evox18.md) was built with it from evox17's source to prove that
nothing broke.
