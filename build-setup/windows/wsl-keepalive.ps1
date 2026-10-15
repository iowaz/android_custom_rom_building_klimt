# Not elevated: keep the WSL VM running so detached builds survive when no terminal is open
# (WSL stops an idle VM, and the build disks are detached with it).
# Start:  powershell -NoProfile -WindowStyle Hidden -File wsl-keepalive.ps1
# Stop:   Get-CimInstance Win32_Process -Filter "Name='wsl.exe'" | ? CommandLine -match 'klimt-keepalive' | % { Stop-Process -Id $_.ProcessId }
while ($true) {
  & wsl.exe -d Ubuntu-24.04 --exec /bin/sh -c 'exec -a klimt-keepalive sleep 86400'
  Start-Sleep -Seconds 5
}
