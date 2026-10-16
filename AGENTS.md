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
clone in `D:\android_rom_building\repositories`.

## Rules

- **Upstream first.** Keep Evolution X / LineageOS / AOSP code as upstream ships it. Change it only for a failure
  seen on klimt or something klimt cannot work without. Changes that already ran on the phone may stay. See
  [docs/evox16-review.md](docs/evox16-review.md) for what happens otherwise.
- **Never run `m <module>` in the tree that gets packaged.** It installs into the staging directories the images
  are packed from. The pipeline runs `m installclean` before every build.
- **Static checks are not a boot test.** Say "image-checked" until the phone has booted the build.
- **Flashing only when the user asks**, to slot b, with `fastboot update --skip-reboot` and never `-w`: the user's
  data is kept ("dirty flash"). Keep the previous working ZIP ready to restore the same way.
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
