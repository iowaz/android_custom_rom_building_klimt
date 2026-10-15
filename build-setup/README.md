# build-setup

The scripts the build PC runs, with the PC's paths (`D:\android_rom_building`, `/mnt/wsl/...`).

| Folder | What it holds |
|---|---|
| [`evox/pipeline`](evox/pipeline) | **The build pipeline**: readiness, detached build, verification, promotion. Start here. |
| [`evox`](evox) | `env.sh` (the build environment the pipeline sources), `sync.sh` / `sync-run.sh` (repo sync), `keys-generate.sh` (one-time signing keys), `snapshot-manifest.py` (public snapshot from `repo manifest -r`) |
| [`evox/tools`](evox/tools) | Read-only helpers: tree state, unpushed commits, backup audit, manifest test, `gh_replay_commits.py` (publish commits from a shallow checkout), `cpio_extract.py` |
| [`windows`](windows) | Disk and WSL setup on Windows: create/format the VHDX disks, `mount-disks.ps1` (elevated, after a reboot), `wsl-keepalive.ps1`, `relocate-vhdx.ps1` (the 2026-10-15 move into `D:\android_rom_building`) |
| [`archive`](archive) | Scripts earlier builds ran (evox16/evox17 copies of the tooling, the evox1-15 flow) |
