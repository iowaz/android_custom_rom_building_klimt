# Wait (tolerating WSL timeouts while it thrashes) until build <name> finishes/fails or <minutes> pass.
param([string]$Name, [int]$Minutes = 115)
$deadline = (Get-Date).AddMinutes($Minutes)
$cmd = "bash /mnt/c/XiaomiBuilds/build-setup/evox/progress.sh $Name; grep -aE '^(FAILED:|error:)|ninja: build stopped' /mnt/wsl/evox/logs/$Name.log | head -8"
do {
  $j = Start-Job { param($c) wsl -d Ubuntu-24.04 --cd / -e bash -c $c 2>&1 } -ArgumentList $cmd
  if (Wait-Job $j -Timeout 90) {
    $out = Receive-Job $j | Out-String
    if ($out -match 'DONE exit|FAILED:') { "{0:T}" -f (Get-Date); $out; Remove-Job $j -Force; exit 0 }
    $last = $out
  }
  Remove-Job $j -Force
  Start-Sleep 60
} while ((Get-Date) -lt $deadline)
"{0:T} timeout; last status:" -f (Get-Date); $last
