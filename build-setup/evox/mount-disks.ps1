# Elevated: attach both build disks to WSL after a reboot / WSL shutdown
$log = 'C:\XiaomiBuilds\build-setup\evox\mount-disks.log'
"start $(Get-Date)" | Out-File -Encoding utf8 $log
& wsl.exe --mount --vhd 'D:\WitAquaBuild\build.vhdx' --name build 2>&1 | Out-String | Add-Content -Encoding utf8 $log
& wsl.exe --mount --vhd 'D:\EvoXBuild\evox.vhdx' --name evox 2>&1 | Out-String | Add-Content -Encoding utf8 $log
