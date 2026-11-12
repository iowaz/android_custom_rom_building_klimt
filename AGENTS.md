# AGENTS.md

Read [README.md](README.md) first: it describes the device, the repositories, the build PC and how a build goes.
This file only adds the rules an agent (Claude, Codex, ...) must follow when working on this project.

## Where things are on the build PC

Everything lives under `D:\android_rom_building` (`/mnt/d/android_rom_building` in WSL); its own `README.md`
is the map. The Android tree is `/mnt/wsl/evox/src` and the build output `/mnt/wsl/build/evox-out`, both on
`D:\android_rom_building\vhdx-images\build.vhdx` (`/mnt/wsl/evox` is a bind mount of `/mnt/wsl/build/evox`).
After a reboot, [`build-setup/windows/mount-disks.ps1`](build-setup/windows/mount-disks.ps1) (elevated)
attaches the disk and makes the bind mount. Keep the path `/mnt/wsl/evox/src`: the scripts, the build output
and ccache depend on it. WSL's swap is on C: on purpose (`C:\WSL\swap.vhdx`); do not move it to D:.
Builds run through [`build-setup/evox/pipeline`](build-setup/evox/pipeline), straight from this repository's
clone in `D:\android_rom_building\repositories`: `prepare.py` (upstream, move-renamed, sync, patch, label,
freeze), then `ready.py`, `start.sh` and `promote.py`. The scripts push nothing; pushes, tags and branch changes
need the owner's OK.

## Rules

- **Patch only what klimt needs, and only when the owner asks.** Keep Evolution X / LineageOS / AOSP code as
  upstream ships it. Change it only for a failure seen on klimt or something klimt cannot work without, and only
  after the owner asks for it. See [docs/evox16-review.md](docs/evox16-review.md) for what happens otherwise.
- **The owner's personal identity layer** is kept as device patches (class `personal` in
  `device/xiaomi/klimt/patches/PATCHES.json`) because the owner asked for it explicitly. Do not extend it without
  that request.
- **No ROM-source forks.** Patches to ROM sources live in `device/xiaomi/klimt/patches/<project path>/` and are
  applied with `patches/apply.py`; the frozen manifest pins those projects at their upstream base. The only
  iowaz repositories in a build are the device tree, the kernel and the private vendor blobs.
- **No per-build branches.** Default branches only (device tree `cnb`). A build is marked by a tag,
  `docs/<build>.md` and `manifests/snapshots/<build>.xml`.
- **Builds are named by date from 2026-11-04**: `YYYYMMDD`, or `YYYYMMDD.N` (N from 2) for another build the
  same day; attempts `20261105-attempt01`; kernel label `-ab20261105`. evox1 to evox31 keep their names.
- **Never run `m <module>` in the tree that gets packaged.** It installs into the staging directories the images
  are packed from. The pipeline runs `m installclean` before every build.
- **Static checks are not a boot test.** Say "image-checked" until the phone has booted the build.
- **Flashing only when the user asks**, to slot b, with `fastboot update --skip-reboot` and never `-w`: the user's
  data is kept ("dirty flash"). Keep the previous working ZIP ready to restore the same way.
- **Reboot after a successful flash by default** (owner request, 2026-11-12). Flash authorization includes
  booting Android afterwards, unless the owner explicitly asks to stay in fastboot. Check the update exit
  status, then run `fastboot reboot` if the helper has not already done it; verify ADB boot completion,
  slot and build. Never auto-reboot after a failed or uncertain flash. This supersedes older instructions
  that leave the reboot to the operator, including helpers generated before this rule.
- **Never commit or upload signing keys** (`vendor/evolution-priv/keys`, `backups\signing-keys`), and never put
  raw phone logs (bugreports, full logcat, getprop) in this public repository. Only trimmed excerpts.
- **One build at a time.** The controller takes a source lock. Do not edit the pipeline while an attempt runs (its
  tooling hashes are checked before verification).
- **Long WSL jobs** go through `start.sh` or a background shell, and WSL must be kept running
  ([`build-setup/windows/wsl-keepalive.ps1`](build-setup/windows/wsl-keepalive.ps1)). A `setsid ... &` inside a
  one-off `wsl.exe` call can die with it.
- **Record every build** in `docs/<build>.md` and `docs/history.md`, and its source in `manifests/snapshots/`.
  Write in the existing style: plain sentences, numbers, no hype.
- **Independent review**: when asked, a second agent reviews read-only and writes its findings to files; merge
  them in a disposition, and say where you disagree and why.
