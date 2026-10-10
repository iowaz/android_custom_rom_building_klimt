# Elevated: create the 480 GB dynamic build disk on D:
$log = 'C:\XiaomiBuilds\build-setup\create-vhdx.log'
if (Test-Path 'D:\WitAquaBuild\build.vhdx') { 'already exists' | Out-File -Encoding utf8 $log; exit 0 }
& diskpart.exe /s 'C:\XiaomiBuilds\build-setup\create-vhdx.txt' 2>&1 | Out-File -Encoding utf8 $log
"diskpart exit $LASTEXITCODE" | Add-Content -Encoding utf8 $log
