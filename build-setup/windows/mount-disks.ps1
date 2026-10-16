# Elevated: attach the build disk to WSL after a reboot or `wsl --shutdown`.
# D:\android_rom_building\vhdx-images\build.vhdx -> /mnt/wsl/build: out/ (evox-out), ccache, reference images, and
# evox/ (the Android tree and the build logs). /mnt/wsl/build/evox is bind-mounted at /mnt/wsl/evox, the path every
# script uses. (Until 2026-10-15 the tree had its own disk, source.vhdx, mounted at /mnt/wsl/evox.)
$root = 'D:\android_rom_building'
$log = Join-Path $root 'diagnostics\logs\mount-disks.log'
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
"start $(Get-Date)" | Out-File -Encoding utf8 -Append $log
& wsl.exe --mount --vhd (Join-Path $root 'vhdx-images\build.vhdx') --name build 2>&1 | Out-String | Add-Content -Encoding utf8 $log
& wsl.exe -u root -d Ubuntu-24.04 -- sh -c 'mountpoint -q /mnt/wsl/build && mkdir -p /mnt/wsl/evox && { mountpoint -q /mnt/wsl/evox || mount --bind /mnt/wsl/build/evox /mnt/wsl/evox; }' 2>&1 | Out-String | Add-Content -Encoding utf8 $log
& wsl.exe -d Ubuntu-24.04 -- df -h /mnt/wsl/build /mnt/wsl/evox 2>&1 | Out-String | Add-Content -Encoding utf8 $log
