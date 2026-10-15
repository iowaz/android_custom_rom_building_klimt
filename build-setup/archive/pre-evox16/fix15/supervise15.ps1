$ErrorActionPreference = 'Continue'
$watchLog = 'C:\XiaomiBuilds\debug\noise15\supervisor15.log'
while ($true) {
    $attemptTime = Get-Date -Format o
    "[$attemptTime] Connecting WSL monitor/verification supervisor" | Add-Content -LiteralPath $watchLog -Encoding utf8
    $watchOutput = [Collections.Generic.List[string]]::new()
    & wsl.exe -d Ubuntu-24.04 --cd / -- bash /mnt/c/XiaomiBuilds/build-setup/evox/fix15/supervise15.sh 2>&1 | ForEach-Object {
        $watchLine = ("$_").Replace([string][char]0,'')
        $watchOutput.Add($watchLine)
        $watchLine | Add-Content -LiteralPath $watchLog -Encoding utf8
    }
    $watchExit = $LASTEXITCODE
    "[$(Get-Date -Format o)] WSL supervisor exit=$watchExit" | Add-Content -LiteralPath $watchLog -Encoding utf8
    $watchCombined = $watchOutput -join "`n"
    if ($watchExit -eq 0 -or $watchCombined -match 'Existing verification supervisor') { break }
    if ($watchCombined -match 'WSAETIMEDOUT|connection attempt failed|host has failed to respond') {
        'Retrying the WSL connection in 60 seconds; build is not restarted.' | Add-Content -LiteralPath $watchLog -Encoding utf8
        Start-Sleep -Seconds 60
        continue
    }
    'Verification or helper failed; manual diagnosis needed, no automatic build restart.' | Add-Content -LiteralPath $watchLog -Encoding utf8
    break
}
