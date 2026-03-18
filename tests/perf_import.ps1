

# --- Paths ---
$scriptRoot = $PSScriptRoot
$dbPath = Join-Path $scriptRoot "test_perf.db"
$mainPy = (Resolve-Path (Join-Path $scriptRoot "..\main.py")).Path
# Read import_dir from tests.json
$configPath = Join-Path $scriptRoot "tests.json"
if (-not (Test-Path $configPath)) {
    Write-Host "ERROR: tests.json not found"
    exit 1
}
$config = Get-Content $configPath | ConvertFrom-Json
$folderPath = $config.import_dir

# --- Validate ---
if (-not (Test-Path $mainPy)) {
    Write-Host "ERROR: main.py not found"
    exit 1
}

if (-not (Test-Path $folderPath)) {
    Write-Host "ERROR: Spotify folder not found"
    exit 1
}

Write-Host "Resolved main.py: $mainPy"
Write-Host "Import folder: $folderPath"

# --- Clean DB ---
if (Test-Path $dbPath) {
    Remove-Item $dbPath -Force
    Write-Host "Removed existing test database"
}

# --- Logs ---
$log = Join-Path $scriptRoot "perf_log.csv"
$stdout = Join-Path $scriptRoot "stdout.log"
$stderr = Join-Path $scriptRoot "stderr.log"

"Timestamp,CPUSeconds,WorkingSetMB,ProcessId" | Out-File $log

# --- Start timer ---
$start = Get-Date
$peakMem = 0


# --- Run process ---
$importArgs = "-u `"$mainPy`" `"$folderPath`""

Write-Host "Starting import..."
Write-Host "Command: python $importArgs"

# Set environment variable for DB file (compatible with all PowerShell versions)
$oldDbEnv = $env:SPOOLIFY_DB_FILE
$env:SPOOLIFY_DB_FILE = $dbPath
# Run process and capture output
$processInfo = New-Object System.Diagnostics.ProcessStartInfo
$processInfo.FileName = "python"
$processInfo.Arguments = $importArgs
$processInfo.RedirectStandardOutput = $true
$processInfo.RedirectStandardError = $true
$processInfo.UseShellExecute = $false
$processInfo.CreateNoWindow = $true
$processInfo.Environment["SPOOLIFY_DB_FILE"] = $dbPath
$proc = New-Object System.Diagnostics.Process
$proc.StartInfo = $processInfo
$proc.Start() | Out-Null
$stdoutContent = $proc.StandardOutput.ReadToEnd()
$stderrContent = $proc.StandardError.ReadToEnd()
$proc.WaitForExit()
$env:SPOOLIFY_DB_FILE = $oldDbEnv

# --- Monitor ---
while (-not $proc.HasExited) {
    try {
        $p = Get-Process -Id $proc.Id -ErrorAction Stop

        $cpu = $p.CPU
        $mem = [math]::Round($p.WorkingSet64 / 1MB, 2)

        if ($mem -gt $peakMem) {
            $peakMem = $mem
        }

        "$((Get-Date).ToString('o')),$cpu,$mem,$($proc.Id)" | Out-File $log -Append
    }
    catch {
        # Process may have exited between loop
    }

    Start-Sleep 1
}

# --- End timer ---
$end = Get-Date
$duration = [math]::Round(($end - $start).TotalSeconds, 2)

# --- Parse output ---
$inserted = 0
$stdoutLines = $stdoutContent -split "`r?`n"
$insertLines = $stdoutLines | Where-Object { $_ -match "^Inserted:" }
if ($insertLines) {
    $inserted = ($insertLines | ForEach-Object { [int](($_ -split ":")[1].Trim()) }) | Measure-Object -Sum | Select-Object -ExpandProperty Sum
}

# --- Metrics ---
$rowsPerSec = 0
if ($duration -gt 0 -and $inserted -gt 0) {
    $rowsPerSec = [math]::Round($inserted / $duration, 2)
}

# --- Output summary ---
Write-Host ""
Write-Host "===== PERFORMANCE SUMMARY ====="
Write-Host "Duration: $duration seconds"
Write-Host "Inserted rows: $inserted"
Write-Host "Rows/sec: $rowsPerSec"
Write-Host "Peak memory: $peakMem MB"
Write-Host "Logs:"
Write-Host "  CSV: $log"
Write-Host ""
Write-Host "--- STDOUT ---"
Write-Host $stdoutContent
Write-Host "--- STDERR ---"
Write-Host $stderrContent

# --- Clean up test DB ---
if (Test-Path $dbPath) {
    Remove-Item $dbPath -Force
    Write-Host "Removed test database after speed test."
}