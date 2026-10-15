# One-time, elevated: move every WSL disk used for the klimt ROM builds into D:\android_rom_building\vhdx-images,
# compacting the two build disks on the way, then attach them again under the same WSL names
# (/mnt/wsl/build and /mnt/wsl/evox), so nothing inside WSL changes.
# Written 2026-10-15. Log: D:\android_rom_building\diagnostics\logs\relocate-vhdx-<time>.log
# Do not run again: it is the record of the one-time move. Its step 5 would move the swap back to D:, but since
# the evening of 2026-10-15 the swap is on C: (C:\WSL\swap.vhdx) on purpose. To compact the disks, run only steps
# 2, 3 and 7 (see docs/build-pc-layout.md).
$ErrorActionPreference = 'Continue'
$root = 'D:\android_rom_building'
$vh = Join-Path $root 'vhdx-images'
$logDir = Join-Path $root 'diagnostics\logs'
New-Item -ItemType Directory -Force -Path $vh, $logDir | Out-Null
$log = Join-Path $logDir ("relocate-vhdx-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
function Log($m) { $line = "{0} {1}" -f (Get-Date -Format 'HH:mm:ss'), $m; $line | Tee-Object -FilePath $log -Append }
function Run($exe, [string[]]$argv) { Log ("> {0} {1}" -f $exe, ($argv -join ' ')); $out = & $exe @argv 2>&1 | Out-String; ($out -replace "`0", '').Trim() | Tee-Object -FilePath $log -Append; Log ("  exit {0}" -f $LASTEXITCODE) }
function SizeGB($p) { if (Test-Path -LiteralPath $p) { [math]::Round((Get-Item -LiteralPath $p).Length / 1GB, 1) } else { 'absent' } }

$moves = @(
  @{ Name = 'build'; Old = 'D:\WitAquaBuild\build.vhdx'; New = Join-Path $vh 'build.vhdx' },
  @{ Name = 'evox';  Old = 'D:\EvoXBuild\evox.vhdx';     New = Join-Path $vh 'source.vhdx' }
)
$distro = 'Ubuntu-24.04'
$distroDir = Join-Path $vh 'wsl-ubuntu-24.04'
$swapOld = 'C:\WSL\swap.vhdx'
$swapNew = Join-Path $vh 'wsl-swap.vhdx'

Log "start; free D: $([math]::Round((Get-PSDrive D).Free/1GB,1)) GB"
foreach ($m in $moves) { Log ("{0}: {1} ({2} GB)" -f $m.Name, $m.Old, (SizeGB $m.Old)) }

# 1. The old WSL keepalive (a PowerShell loop started for evox16) would restart WSL during the move.
$keep = Get-CimInstance Win32_Process -Filter 'ProcessId=53808' -ErrorAction SilentlyContinue
if ($keep -and $keep.Name -eq 'powershell.exe') { Stop-Process -Id 53808 -Force; Log 'stopped old keepalive PID 53808' }

# 2. Detach the build disks and stop WSL (needed to move the distro and the swap file).
foreach ($m in $moves) { if (Test-Path -LiteralPath $m.Old) { Run 'wsl.exe' @('--unmount', $m.Old) } }
Run 'wsl.exe' @('--shutdown')
Start-Sleep -Seconds 8

# 3. Compact the two dynamic VHDX files (space freed and trimmed inside them goes back to D:).
foreach ($m in $moves) {
  if (-not (Test-Path -LiteralPath $m.Old)) { continue }
  $before = SizeGB $m.Old
  $dp = Join-Path $env:TEMP ("compact-{0}.txt" -f $m.Name)
  "select vdisk file=`"$($m.Old)`"`r`nattach vdisk readonly`r`ncompact vdisk`r`ndetach vdisk`r`n" | Out-File -Encoding ascii $dp
  Run 'diskpart.exe' @('/s', $dp)
  Log ("{0}: {1} GB -> {2} GB" -f $m.Name, $before, (SizeGB $m.Old))
}

# 4. Move the build disks (same volume: a rename).
foreach ($m in $moves) {
  if ((Test-Path -LiteralPath $m.Old) -and -not (Test-Path -LiteralPath $m.New)) {
    Move-Item -LiteralPath $m.Old -Destination $m.New; Log ("moved {0} -> {1}" -f $m.Old, $m.New)
  }
}

# 5. Swap file: point .wslconfig at the new place and move the file (WSL recreates it if absent).
$cfg = Join-Path $env:USERPROFILE '.wslconfig'
if (-not $env:USERPROFILE -or -not (Test-Path $cfg)) { $cfg = 'C:\Users\diogo\.wslconfig' }
if (Test-Path $cfg) {
  Copy-Item $cfg (Join-Path $logDir 'wslconfig.before-relocation.txt') -Force
  $text = Get-Content -Raw $cfg
  $text = $text -replace 'swapFile=.*', ('swapFile=' + ($swapNew -replace '\\', '\\'))
  $text = $text -replace '# Swap lives on C:, build files live on an ext4 VHDX in D:\\WitAquaBuild', '# Swap, the distro and both build disks live in D:\android_rom_building\vhdx-images'
  Set-Content -Path $cfg -Value $text -Encoding ascii -NoNewline
  Log ".wslconfig swapFile -> $swapNew"
}
if ((Test-Path -LiteralPath $swapOld) -and -not (Test-Path -LiteralPath $swapNew)) {
  Move-Item -LiteralPath $swapOld -Destination $swapNew; Log "moved $swapOld -> $swapNew"
}

# 6. Move the Ubuntu distro (its own ext4.vhdx) next to the build disks.
if (-not (Test-Path (Join-Path $distroDir 'ext4.vhdx'))) {
  New-Item -ItemType Directory -Force -Path $distroDir | Out-Null
  Run 'wsl.exe' @('--manage', $distro, '--move', $distroDir)
}

# 7. Attach the build disks again under the same names and check them.
foreach ($m in $moves) { $p = if (Test-Path -LiteralPath $m.New) { $m.New } else { $m.Old }; Run 'wsl.exe' @('--mount', '--vhd', $p, '--name', $m.Name) }
Run 'wsl.exe' @('-d', $distro, '--', 'df', '-h', '/mnt/wsl/build', '/mnt/wsl/evox')
Run 'wsl.exe' @('-d', $distro, '--', 'test', '-e', '/mnt/wsl/evox/src/build/envsetup.sh')
foreach ($m in $moves) { Log ("{0} now: {1} ({2} GB)" -f $m.Name, $m.New, (SizeGB $m.New)) }
Log ("distro: " + ((Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' | ForEach-Object { (Get-ItemProperty $_.PSPath).BasePath }) -join ', '))
Log "end; free D: $([math]::Round((Get-PSDrive D).Free/1GB,1)) GB"
'DONE' | Out-File -Encoding ascii (Join-Path $logDir 'relocate-vhdx.done')
