# One status line for a running flash-evox.ps1 (its log is locked while fastboot streams into it):
# fastboot.exe I/O counters, the phone's USB mode, and the log tail once the log is readable again.
param([string]$Name = "evox10", [string]$Serial = "")
$log = "C:\XiaomiBuilds\flash-$Name.log"
$p = Get-CimInstance Win32_Process -Filter "Name='fastboot.exe'" | Select-Object -First 1
$fb = if ($p) { "fastboot running: read {0:N2} GB, other I/O {1:N2} GB" -f ($p.ReadTransferCount/1GB), ($p.OtherTransferCount/1GB) } else { "fastboot not running" }
$usb = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { if ($Serial) { $_.InstanceId -like "USB\VID_*\$Serial" } else { $_.InstanceId -match '^USB\\VID_(0E8D|18D1|2717)&' } }
$mode = ($usb | ForEach-Object {
  $id = $_.InstanceId
  if ($id -like '*VID_0E8D&PID_201C*') { "bootloader" } elseif ($id -like '*VID_18D1&PID_4EE0*') { "fastbootd" }
  elseif ($id -like '*VID_18D1&PID_4E11*' -or $id -like '*VID_18D1&PID_D001*' -or $id -like '*VID_2717*') { "android(adb)" } else { $id }
}) -join ','
$tail = try { (Get-Content $log -Tail 3 -ErrorAction Stop | Where-Object { $_.Trim() }) -join ' | ' } catch { "log locked (fastboot writing)" }
"$fb | phone: $(if ($mode) { $mode } else { 'not on USB / re-enumerating' }) | $tail"
