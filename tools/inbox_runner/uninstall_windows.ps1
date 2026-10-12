# tools/inbox_runner/uninstall_windows.ps1
# Gỡ bỏ Windows Task Scheduler cho RoadGuard Inbox Runner

$TaskName = "RoadGuard_InboxRunner"

try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
    Write-Host "✅ Đã gỡ bỏ thành công Scheduled Task: $TaskName" -ForegroundColor Green
} catch {
    schtasks /delete /tn "$TaskName" /f
    Write-Host "✅ Đã gỡ bỏ Scheduled Task: $TaskName" -ForegroundColor Green
}
