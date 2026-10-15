# Elevated, one-time: create D:\EvoXBuild\evox.vhdx (200 GB dynamic), format ext4, mount at /mnt/wsl/evox
$log = 'C:\XiaomiBuilds\build-setup\evox\create-evox-disk.log'
$vhd = 'D:\EvoXBuild\evox.vhdx'
function L($m) { $m | Add-Content -Encoding utf8 $log }
"start $(Get-Date)" | Out-File -Encoding utf8 $log
New-Item -ItemType Directory -Force D:\EvoXBuild | Out-Null
if (-not (Test-Path $vhd)) { L (& diskpart.exe /s 'C:\XiaomiBuilds\build-setup\evox\create-evox-vhdx.txt' 2>&1 | Out-String) }
L (& wsl.exe --mount --vhd $vhd --bare 2>&1 | Out-String)
L (& wsl.exe -d Ubuntu-24.04 -u root --cd / -- bash /mnt/c/XiaomiBuilds/build-setup/evox/format-evox.sh 2>&1 | Out-String)
L (& wsl.exe --unmount $vhd 2>&1 | Out-String)
L (& wsl.exe --mount --vhd $vhd --name evox 2>&1 | Out-String)
L (& wsl.exe -d Ubuntu-24.04 -u root --cd / -- bash -c 'df -h /mnt/wsl/evox && chown 1000:1000 /mnt/wsl/evox' 2>&1 | Out-String)
L "end $(Get-Date)"
