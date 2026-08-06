# Local failover watchdog: publishes only when the blog feed goes stale.
# Runs on this machine, free and independent of every CI provider.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\local_watchdog.ps1
#
# Optional env tuning:
#   LOCAL_WATCHDOG_INTERVAL_SECONDS (default 900 = every 15 min)
#   LOCAL_WATCHDOG_MAX_MINUTES     (default 0 = run forever)
#
# To run in the background on login, create a Task Scheduler task:
#   - Trigger: At log on (or every hour, repeat every 15 minutes)
#   - Action: Start a program
#       Program: powershell.exe
#       Arguments: -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\path\to\repo\scripts\local_watchdog.ps1"

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

$lockFile = Join-Path $root "data\local_watchdog.lock"
$lockPid = 0
if (Test-Path -LiteralPath $lockFile) {
    try {
        $lockPid = [int](Get-Content -LiteralPath $lockFile -ErrorAction Stop)
    } catch {
        $lockPid = 0
    }
    if ($lockPid -gt 0 -and (Get-Process -Id $lockPid -ErrorAction SilentlyContinue)) {
        "Watchdog already running (PID $lockPid); exiting."
        exit 0
    }
    Remove-Item -LiteralPath $lockFile -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $lockFile) | Out-Null
$PID | Out-File -FilePath $lockFile

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}
$log = Join-Path $root "data\local_watchdog.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log) | Out-Null
$outFile = Join-Path $root "data\watchdog_run_out.txt"
$errFile = Join-Path $root "data\watchdog_run_err.txt"

$interval = 900
if ($env:LOCAL_WATCHDOG_INTERVAL_SECONDS) {
    $interval = [int]$env:LOCAL_WATCHDOG_INTERVAL_SECONDS
}
$maxMinutes = 0
if ($env:LOCAL_WATCHDOG_MAX_MINUTES) {
    $maxMinutes = [int]$env:LOCAL_WATCHDOG_MAX_MINUTES
}
$deadline = $null
if ($maxMinutes -gt 0) {
    $deadline = (Get-Date).AddMinutes($maxMinutes)
}

$runTimeoutSec = 180
if ($env:LOCAL_WATCHDOG_RUN_TIMEOUT_SECONDS) {
    $runTimeoutSec = [int]$env:LOCAL_WATCHDOG_RUN_TIMEOUT_SECONDS
}

while ($true) {
    if ($deadline -and (Get-Date) -gt $deadline) {
        break
    }
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    "== $stamp ==" | Out-File -Append -FilePath $log
    $err = $null
    $out = $null
    try {
        $proc = Start-Process -FilePath $python -ArgumentList "src\wp_failover_publish.py" `
            -NoNewWindow -PassThru -RedirectStandardOutput $outFile -RedirectStandardError $errFile `
            -ErrorAction Stop
        if (-not $proc.WaitForExit($runTimeoutSec * 1000)) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            "KILLED after $runTimeoutSec s timeout" | Out-File -Append -FilePath $log
        } else {
            $out = Get-Content -LiteralPath $outFile -Raw -ErrorAction SilentlyContinue
            $err = Get-Content -LiteralPath $errFile -Raw -ErrorAction SilentlyContinue
            if ($out) { $out.Trim() | Out-File -Append -FilePath $log }
            if ($err) { ("STDERR: " + $err.Trim()) | Out-File -Append -FilePath $log }
        }
        Remove-Item -LiteralPath $outFile, $errFile -Force -ErrorAction SilentlyContinue
    } catch {
        ("WATCHDOG ERROR: " + $_.Exception.Message) | Out-File -Append -FilePath $log
    }
    Start-Sleep -Seconds $interval
}
Remove-Item -LiteralPath $lockFile -ErrorAction SilentlyContinue
