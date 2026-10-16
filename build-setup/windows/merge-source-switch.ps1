# One-time, elevated (2026-10-15): after merge-source-into-build.sh copied the tree into build.vhdx and the copy
# was verified, stop using source.vhdx. Shut WSL down (detaches both disks), raise build.vhdx's maximum size from
# 480 GB to 640 GB, then attach it with mount-disks.ps1, which bind-mounts /mnt/wsl/build/evox at /mnt/wsl/evox.
# source.vhdx is left on D:, detached. The filesystem is grown afterwards with resize2fs, from WSL.
$ErrorActionPreference = 'Continue'
$root = 'D:\android_rom_building'
$disk = Join-Path $root 'vhdx-images\build.vhdx'
$logDir = Join-Path $root 'diagnostics\logs'
$log = Join-Path $logDir ("merge-source-switch-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
function Log($m) { $line = "{0} {1}" -f (Get-Date -Format 'HH:mm:ss'), $m; $line | Tee-Object -FilePath $log -Append }
function Run($exe, [string[]]$argv) { Log ("> {0} {1}" -f $exe, ($argv -join ' ')); $out = & $exe @argv 2>&1 | Out-String; ($out -replace "`0", '').Trim() | Tee-Object -FilePath $log -Append; Log ("  exit {0}" -f $LASTEXITCODE) }

Log ("start; free D: {0:N1} GB; build.vhdx {1:N1} GB" -f ((Get-PSDrive D).Free / 1GB), ((Get-Item -LiteralPath $disk).Length / 1GB))

# 1. Detach both disks.
Run 'wsl.exe' @('--shutdown')
Start-Sleep -Seconds 8

# 2. Raise the maximum size (MB). Dynamic: nothing is allocated on D: until WSL writes.
$dp = Join-Path $env:TEMP 'expand-build.txt'
"select vdisk file=`"$disk`"`r`nexpand vdisk maximum=655360`r`n" | Out-File -Encoding ascii $dp
Run 'diskpart.exe' @('/s', $dp)

# 3. Attach the build disk and bind-mount the tree.
Log '> mount-disks.ps1'
& (Join-Path $root 'scripts\mount-disks.ps1')
Run 'wsl.exe' @('-d', 'Ubuntu-24.04', '--', 'findmnt', '-o', 'SOURCE,TARGET,SIZE', '/mnt/wsl/build', '/mnt/wsl/evox')
Run 'wsl.exe' @('-d', 'Ubuntu-24.04', '--', 'lsblk', '-o', 'NAME,SIZE,FSTYPE,MOUNTPOINTS')
Log ("end; free D: {0:N1} GB; build.vhdx {1:N1} GB" -f ((Get-PSDrive D).Free / 1GB), ((Get-Item -LiteralPath $disk).Length / 1GB))
'DONE' | Out-File -Encoding ascii (Join-Path $logDir 'merge-source-switch.done')
