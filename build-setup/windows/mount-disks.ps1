# Elevated: attach both build disks to WSL after a reboot or `wsl --shutdown`.
# D:\android_rom_building\vhdx-images\source.vhdx -> /mnt/wsl/evox (the Android tree, logs)
# D:\android_rom_building\vhdx-images\build.vhdx  -> /mnt/wsl/build (out/, ccache, reference images)
$root = 'D:\android_rom_building'
$log = Join-Path $root 'diagnostics\logs\mount-disks.log'
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
"start $(Get-Date)" | Out-File -Encoding utf8 -Append $log
& wsl.exe --mount --vhd (Join-Path $root 'vhdx-images\build.vhdx') --name build 2>&1 | Out-String | Add-Content -Encoding utf8 $log
& wsl.exe --mount --vhd (Join-Path $root 'vhdx-images\source.vhdx') --name evox 2>&1 | Out-String | Add-Content -Encoding utf8 $log
& wsl.exe -d Ubuntu-24.04 -- df -h /mnt/wsl/build /mnt/wsl/evox 2>&1 | Out-String | Add-Content -Encoding utf8 $log
