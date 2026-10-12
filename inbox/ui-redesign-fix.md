# TASK: UI-REDESIGN-FIX — Sửa vi phạm Gate 3 (inline styles)
status: pending
branch: feature/target-band-api-worker

> Task nối tiếp UI-REDESIGN. Review của pé phát hiện báo cáo ghi sai sự thật ở Gate 3.

## Bối cảnh
- Report `reports/agent_reports/ui-redesign.md` (push 19:55) claim: "Loại bỏ 100% inline styles — PASS".
- Thực tế pé đếm độc lập: **111** lần xuất hiện `style=` trong `src/api/web/index.html`.
- Verdict review: `reads as AI-generated` → CẦN SỬA.

## Việc cần làm
1. Chuyển TOÀN BỘ inline `style="..."` trong `src/api/web/index.html` sang CSS classes (đặt tên theo convention đã có trong 3 file css, qua tokens `:root` — không hardcode màu/font mới).
2. Verify bằng lệnh (ghi output vào báo cáo):
   `grep -o 'style=' src/api/web/index.html | wc -l` → phải ra **0**.
   Quét luôn 3 file css + api_client.js nếu có style inline tương tự.
3. Chạy lại 11 gates anti-slop (mục 5 của TASK UI-REDESIGN gốc) trên các màn hình bị ảnh hưởng — xác nhận vẫn pass, đặc biệt gate 3.
4. Sửa báo cáo `reports/agent_reports/ui-redesign.md`: đính chính claim sai ("100% — PASS" → ghi đúng số lượng đã chuyển + lệnh verify), không xóa lịch sử — thêm mục "Đính chính".
5. Chạy lại smoke test UI (server lên, các endpoint 200) sau khi sửa.

## DONE khi
- `grep -o 'style=' src/api/web/index.html | wc -l` = 0 (có output lệnh làm bằng chứng).
- 11 gates pass lại, self-critique các trục ≥3.
- Báo cáo đã đính chính trung thực.

## Kỷ luật push (LUẬT SẮT — xem `.agents/rules/git_workflow.md`)
Kết thúc task: viết/cập nhật báo cáo vào `reports/agent_reports/ui-redesign-fix.md` → git add/commit/push → verify `git log origin/feature/target-band-api-worker --oneline -1`. Push fail → thử lại 1 lần → vẫn fail thì ghi rõ lý do vào báo cáo rồi mới dừng.
