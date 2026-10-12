# tools/inbox_runner/install_windows.ps1
# Dang ky Windows Task Scheduler cho RoadGuard Inbox Runner (30 phut/lan)

param(
    [Parameter(Mandatory=$false)]
    [string]$RepoPath = "$PSScriptRoot\..\.."
)

$ErrorActionPreference = "Stop"

try {
    $ResolvedRepoPath = (Resolve-Path $RepoPath).Path
} catch {
    $ResolvedRepoPath = $RepoPath
}

$TaskName = "RoadGuard_InboxRunner"
$RunnerPy = Join-Path $ResolvedRepoPath "tools\inbox_runner\runner.py"

if (-not (Test-Path $RunnerPy)) {
    Write-Error "Khong tim thay file runner.py tai: $RunnerPy"
    exit 1
}

# Tim Python executable
$PythonCmd = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $PythonCmd) {
    Write-Error "Khong tim thay python trong PATH."
    exit 1
}
$PythonExe = $PythonCmd.Source

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "CAI DAT WINDOWS TASK SCHEDULER -- ROADGUARD INBOX RUNNER" -ForegroundColor Cyan
Write-Host "Thu muc Repo : $ResolvedRepoPath"
Write-Host "Trinh chay   : $PythonExe"
Write-Host "Script       : $RunnerPy"
Write-Host "Chu ky       : 30 phut / 1 lan"
Write-Host "=================================================================" -ForegroundColor Cyan

# Dam bao agy CLI co trong User PATH
$AgyBinDir = "$env:LOCALAPPDATA\agy\bin"
if (Test-Path $AgyBinDir) {
    $CurrentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($CurrentPath -notlike "*$AgyBinDir*") {
        Write-Host "Dang them $AgyBinDir vao User PATH..." -ForegroundColor Yellow
        [Environment]::SetEnvironmentVariable("Path", "$CurrentPath;$AgyBinDir", "User")
    }
}

# Tao wrapper bat de dam bao chay muot ma trong background
$WrapperBat = Join-Path $ResolvedRepoPath "tools\inbox_runner\run_inbox_task.bat"
$BatContent = @"
@echo off
set "PATH=%LOCALAPPDATA%\agy\bin;%PATH%"
pushd "%~dp0..\.."
python "tools\inbox_runner\runner.py" >> "tools\inbox_runner\runner.log" 2>&1
popd
"@
Set-Content -Path $WrapperBat -Value $BatContent -Encoding ASCII

# Dang ky Task Scheduler
$TaskRegistered = $false

try {
    # Chay cmd.exe /c "WrapperBat"
    $Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$WrapperBat`"" -WorkingDirectory $ResolvedRepoPath
    $Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration ([TimeSpan]::FromDays(3650))
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "RoadGuard AI Inbox Runner Loop (30 phut/lan)" -Force | Out-Null
    $TaskRegistered = $true
} catch {
    Write-Host "Loi khi dung Register-ScheduledTask: $_" -ForegroundColor Yellow
    # Fallback schtasks.exe
    $SchTr = "\`"cmd.exe /c \`\`\`"$WrapperBat\`\`\`"\`""
    $SchCmd = "schtasks /create /tn `"$TaskName`" /tr $SchTr /sc minute /mo 30 /f"
    Invoke-Expression $SchCmd
    if ($LASTEXITCODE -eq 0) {
        $TaskRegistered = $true
    }
}

if ($TaskRegistered) {
    Write-Host "DA DANG KY TASK THANH CONG: $TaskName" -ForegroundColor Green
    Write-Host "Kiem tra tac vu: Get-ScheduledTask -TaskName '$TaskName'"
    Write-Host "File log ghi nhan tai: $ResolvedRepoPath\tools\inbox_runner\runner.log"
} else {
    Write-Error "Khong the dang ky Task Scheduler."
    exit 1
}
