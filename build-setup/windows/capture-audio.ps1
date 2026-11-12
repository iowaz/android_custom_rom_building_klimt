[CmdletBinding()]
param(
    [string]$Serial,
    [ValidateRange(10, 60)][int]$Seconds = 45,
    [string]$Workspace = 'D:\android_rom_building'
)

$ErrorActionPreference = 'Stop'
$adb = Join-Path $Workspace 'tools\platform-tools\adb.exe'
if (-not (Test-Path -LiteralPath $adb)) { throw "adb not found: $adb" }

$deviceLines = @(& $adb devices)
if ($LASTEXITCODE -ne 0) { throw 'Cannot enumerate adb devices.' }
$online = @($deviceLines | ForEach-Object {
    if ($_ -match '^(\S+)\s+device\s*$') { $Matches[1] }
})
if ($Serial) {
    if ($Serial -notin $online) { throw 'Selected device is not connected and authorized.' }
} elseif ($online.Count -eq 1) {
    $Serial = $online[0]
} else {
    throw 'Connect one authorized phone, or select an online device with -Serial.'
}

$capture = Join-Path $Workspace ('diagnostics\audio\' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
$private = Join-Path $capture 'private'
New-Item -ItemType Directory -Path $private -Force | Out-Null

function Save-Adb([string]$Name, [string[]]$AdbArguments) {
    $content = & $adb -s $Serial @AdbArguments 2>&1
    $exitCode = $LASTEXITCODE
    $content | Set-Content -LiteralPath (Join-Path $private $Name) -Encoding utf8
    if ($exitCode -ne 0) { throw "adb failed while capturing $Name (exit $exitCode)." }
}

function Save-AudioState([string]$Phase) {
    Save-Adb "$Phase-audio.txt" @('shell', 'dumpsys', 'audio')
    Save-Adb "$Phase-policy.txt" @('shell', 'dumpsys', 'media.audio_policy')
    Save-Adb "$Phase-flinger.txt" @('shell', 'dumpsys', 'media.audio_flinger')
    Save-Adb "$Phase-media-session.txt" @('shell', 'dumpsys', 'media_session')
}

# No logcat clear, notification injection, settings writes, root or reboot.
Save-Adb 'device-time.txt' @('shell', 'date')
Save-Adb 'framework-media-steps.txt' @('shell', 'getprop', 'ro.config.media_vol_steps')
Save-Adb 'xiaomi-media-steps.txt' @('shell', 'getprop', 'ro.vendor.audio.media.volume.steps')
Save-AudioState 'before'

$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = $adb
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
foreach ($argument in @('-s', $Serial, 'logcat', '-b', 'main', '-b', 'system', '-v', 'threadtime', '-T', '1')) {
    $startInfo.ArgumentList.Add($argument)
}
$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $startInfo
$writer = $null
$errorTask = $null
$copyTask = $null
$started = $false
try {
    $writer = [System.IO.File]::Create((Join-Path $private 'logcat.txt'))
    if (-not $process.Start()) { throw 'Cannot start logcat.' }
    $started = $true
    $copyTask = $process.StandardOutput.BaseStream.CopyToAsync($writer)
    $errorTask = $process.StandardError.ReadToEndAsync()
    Write-Host "Capturing for $Seconds seconds. With the car parked, play Spotify over wireless Android Auto and reproduce one notification."
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $duringSaved = $false
    while ($timer.Elapsed.TotalSeconds -lt $Seconds) {
        if ($process.HasExited) { throw 'logcat stopped before the capture finished.' }
        if (-not $duringSaved -and $timer.Elapsed.TotalSeconds -ge ($Seconds / 2)) {
            Save-AudioState 'during'
            $duringSaved = $true
        }
        Start-Sleep -Milliseconds 200
    }
} finally {
    if ($started -and -not $process.HasExited) { $process.Kill() }
    if ($started) {
        $process.WaitForExit()
        if ($copyTask) { $copyTask.GetAwaiter().GetResult() }
        if ($errorTask) {
            $errorTask.GetAwaiter().GetResult() | Set-Content -LiteralPath (Join-Path $private 'logcat-stderr.txt') -Encoding utf8
        }
    }
    if ($writer) { $writer.Dispose() }
    $process.Dispose()
}
Save-AudioState 'after'
Write-Host "Saved local private capture: $capture"
