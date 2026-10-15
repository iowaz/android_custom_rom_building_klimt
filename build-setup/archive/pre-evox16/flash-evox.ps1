# Flash an evox img zip: adb reboot bootloader + fastboot update, no wipe (the user wipes only when needed).
# Usage: powershell -File flash-evox.ps1 -Name evox10 [-Serial <fastboot serial>]   (needs USB: fastboot has no Wi-Fi mode)
param([string]$Name = "evox10", [string]$Serial = "")
$ErrorActionPreference = 'Continue'
$zip = "D:\WitAquaBuild\out-evox\lineage_klimt-$Name-img.zip"
$log = "C:\XiaomiBuilds\flash-$Name.log"
if (-not (Test-Path $zip)) { "missing $zip"; exit 1 }
"=== $(Get-Date) adb reboot bootloader" | Out-File -Encoding utf8 $log
adb reboot bootloader 2>&1 | Add-Content -Encoding utf8 $log
# wait up to 90 s for the bootloader fastboot device
$ok = $false
for ($i = 0; $i -lt 45; $i++) {
  Start-Sleep 2
  $d = (fastboot devices 2>&1 | Out-String)
  # any device in fastboot, or only -Serial when given
  if ($d -match $(if ($Serial) { [regex]::Escape($Serial) } else { "\tfastboot" })) { $ok = $true; break }
}
"fastboot device: $ok ($d)" | Add-Content -Encoding utf8 $log
if (-not $ok) { Get-Content $log; exit 1 }
fastboot getvar current-slot 2>&1 | Add-Content -Encoding utf8 $log
fastboot getvar unlocked 2>&1 | Add-Content -Encoding utf8 $log
"=== $(Get-Date) fastboot update --skip-reboot $(Split-Path $zip -Leaf)" | Add-Content -Encoding utf8 $log
Push-Location (Split-Path $zip)
fastboot update --skip-reboot (Split-Path $zip -Leaf) 2>&1 | ForEach-Object { "$_" } | Add-Content -Encoding utf8 $log
$rc = $LASTEXITCODE
Pop-Location
"=== $(Get-Date) exit $rc" | Add-Content -Encoding utf8 $log
fastboot getvar current-slot 2>&1 | Add-Content -Encoding utf8 $log
Select-String -Path $log -Pattern 'FAILED|error' | Select-Object -First 10
Get-Content $log -Tail 6
