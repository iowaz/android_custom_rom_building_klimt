# Elevated, one-time: attach build.vhdx bare, format it ext4 from WSL, then mount it at /mnt/wsl/build.
$log = 'C:\XiaomiBuilds\build-setup\format-build-disk.log'
$vhd = 'D:\WitAquaBuild\build.vhdx'
function L($m) { $m | Add-Content -Encoding utf8 $log }
"start $(Get-Date)" | Out-File -Encoding utf8 $log
L (& wsl.exe --mount --vhd $vhd --bare 2>&1 | Out-String)
$dev = (& wsl.exe -d Ubuntu-24.04 -u root -- bash -c "lsblk -dbno NAME,SIZE | awk '`$2==515396075520{print `$1}'" 2>&1 | Out-String).Trim()
L "device: [$dev]"
if ($dev -match '^sd[a-z]+$') {
  L (& wsl.exe -d Ubuntu-24.04 -u root -- mkfs.ext4 -F -L build "/dev/$dev" 2>&1 | Out-String)
  L (& wsl.exe --unmount $vhd 2>&1 | Out-String)
  L (& wsl.exe --mount --vhd $vhd --name build 2>&1 | Out-String)
  L (& wsl.exe -d Ubuntu-24.04 -u root -- bash -c "df -h /mnt/wsl/build && chown 1000:1000 /mnt/wsl/build" 2>&1 | Out-String)
} else { L 'device not found, not formatting' }
L "end $(Get-Date)"
