# TASK: Đổi Inbox Runner scheduler từ 30 phút xuống 5 phút
status: pending
branch: feature/target-band-api-worker

## Bối cảnh
Task Scheduler `RoadGuard_InboxRunner` hiện chạy mỗi 30 phút → task mới vào `inbox/` phải chờ
tối đa 30' mới được pick up. Đổi xuống 5 phút để vòng lặp phản ứng nhanh hơn.

## Spec
1. Mở PowerShell **Administrator** (nếu báo access denied thì chạy lại dưới quyền admin).
2. Đổi repetition interval:
   ```
   schtasks /change /tn "RoadGuard_InboxRunner" /ri 5
   ```
   (Nếu schtasks báo lỗi, dùng PowerShell thay thế:
   ```
   $tr = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
        -RepetitionInterval (New-TimeSpan -Minutes 5) `
        -RepetitionDuration (New-TimeSpan -Days 3650)
   Set-ScheduledTask -TaskName "RoadGuard_InboxRunner" -Trigger $tr
   ```)
3. VERIFY — chạy và đọc output xác nhận:
   ```
   schtasks /query /tn "RoadGuard_InboxRunner" /v /fo list | Select-String "Repeat|Interval"
   ```
   DONE khi output thể hiện repeat mỗi 5 phút (VD: "Every 5 minute(s)").
4. KHÔNG đụng vào nội dung task, action, hay user chạy task — chỉ đổi repetition interval.

## DONE khi
`schtasks /query` xác nhận scheduler chạy mỗi 5 phút.

## Kỷ luật push (LUẬT SẮT — xem `.agents/rules/git_workflow.md`)
Viết báo cáo `reports/agent_reports/sys-scheduler-5min.md` (đã làm gì, output verify) →
git add/commit/push → verify `git log origin/feature/target-band-api-worker --oneline -1`.
