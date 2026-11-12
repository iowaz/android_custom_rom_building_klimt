[CmdletBinding()]
param(
    [ValidateSet('Start','Status','Collect')][string]$Action = 'Status',
    [ValidateRange(1,30)][int]$Minutes = 10,
    [string]$Workspace = 'D:\android_rom_building'
)
$ErrorActionPreference = 'Stop'
$adb = Join-Path $Workspace 'tools\platform-tools\adb.exe'
$pointer = Join-Path $Workspace 'tmp\last-phone-audio-capture.txt'
$remoteScript = '/data/local/tmp/klimt-audio-recorder.sh'

function Invoke-Adb([string[]]$AdbArguments) {
    $output = & $adb @AdbArguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "adb failed: $($AdbArguments[0])" }
    return $output
}

$devices = @(Invoke-Adb @('devices') | ForEach-Object {
    if ($_ -match '^(\S+)\s+device\s*$') { $Matches[1] }
})
if ($devices.Count -ne 1) { throw 'Connect exactly one authorized phone.' }
$serial = $devices[0]

if ($Action -eq 'Start') {
    if (Test-Path -LiteralPath $pointer) {
        $oldControl = Get-Content -Raw -LiteralPath ((Get-Content -LiteralPath $pointer).Trim()) | ConvertFrom-Json
        if ($oldControl.serial -eq $serial) {
            if ($oldControl.remote -notmatch '^/data/local/tmp/klimt-audio-\d{8}-\d{6}$') { throw 'Invalid previous remote directory.' }
            $oldStatus = (Invoke-Adb @('-s',$serial,'shell','sh',$remoteScript,'status',$oldControl.remote) | Out-String).Trim()
            if ($oldStatus -eq 'RUNNING') { throw 'The previous audio capture is still running. Collect it first.' }
        }
    }
    $identifier = Get-Date -Format 'yyyyMMdd-HHmmss'
    $capture = Join-Path $Workspace "diagnostics\audio\$identifier-untethered"
    $private = Join-Path $capture 'private'
    New-Item -ItemType Directory -Path $private -Force | Out-Null
    $remote = "/data/local/tmp/klimt-audio-$identifier"
    $source = Join-Path $PSScriptRoot 'phone-audio-recorder.sh'
    $normalized = Join-Path $private 'recorder.sh'
    [IO.File]::WriteAllText($normalized, ([IO.File]::ReadAllText($source).Replace("`r`n","`n")), [Text.UTF8Encoding]::new($false))
    Invoke-Adb @('-s',$serial,'push',$normalized,$remoteScript) | Out-Null
    Invoke-Adb @('-s',$serial,'shell','sh','-n',$remoteScript) | Out-Null
    $pidText = Invoke-Adb @('-s',$serial,'shell','sh',$remoteScript,'start',$remote,([string]($Minutes * 60)))
    $controlPath = Join-Path $private 'control.json'
    [pscustomobject]@{serial=$serial;remote=$remote;local=$capture;minutes=$Minutes;started=(Get-Date -Format o)} |
        ConvertTo-Json | Set-Content -LiteralPath $controlPath -Encoding utf8
    $controlPath | Set-Content -LiteralPath $pointer -Encoding utf8
    Start-Sleep -Seconds 1
    $status = Invoke-Adb @('-s',$serial,'shell','sh',$remoteScript,'status',$remote)
    if (($status | Out-String).Trim() -ne 'RUNNING') { throw "Recorder did not start: $status" }
    Write-Host "Recording on the phone for up to $Minutes min. You may disconnect USB. Reproduce Android Auto only while parked, then reconnect and run -Action Collect."
    return
}

if (-not (Test-Path -LiteralPath $pointer)) { throw 'No capture has been started by this helper.' }
$control = Get-Content -Raw -LiteralPath ((Get-Content -LiteralPath $pointer).Trim()) | ConvertFrom-Json
if ($control.serial -ne $serial) { throw 'The connected phone differs from the recorded capture device.' }
if ($control.remote -notmatch '^/data/local/tmp/klimt-audio-\d{8}-\d{6}$') { throw 'Invalid recorded remote directory.' }
$status = (Invoke-Adb @('-s',$serial,'shell','sh',$remoteScript,'status',$control.remote) | Out-String).Trim()
if ($Action -eq 'Status') { Write-Host $status; return }
if ($status -eq 'RUNNING') {
    Invoke-Adb @('-s',$serial,'shell','sh',$remoteScript,'stop',$control.remote) | Out-Null
    for ($attempt = 0; $attempt -lt 40 -and $status -eq 'RUNNING'; $attempt++) {
        Start-Sleep -Seconds 1
        $status = (Invoke-Adb @('-s',$serial,'shell','sh',$remoteScript,'status',$control.remote) | Out-String).Trim()
    }
    if ($status -eq 'RUNNING') { throw 'Recorder is still finishing. Retry Collect shortly.' }
}
$destination = Join-Path $control.local 'private\recording'
Invoke-Adb @('-s',$serial,'pull',$control.remote,$destination) | Out-Null
Write-Host "Saved private capture: $destination ($status). Remote diagnostic files are retained; no settings were changed."
