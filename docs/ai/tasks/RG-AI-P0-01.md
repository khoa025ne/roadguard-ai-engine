# RG-AI-P0-01 — Handoff

- Mục tiêu: kiểm kê toàn bộ AI workspace, dọn an toàn, xác lập baseline theo `docs/ai_mvp/{01,02,03,09,10,12}`; không train/refactor/đổi BE-FE.
- Kết quả chi tiết: `docs/ai_mvp/17_RG_AI_P0_01_WORKSPACE_AUDIT.md` (revision `82ae0dc`, 2026-10-22).
- Trạng thái: audit hoàn tất ở mức quan sát source/tài sản và regression; cleanup **chưa thực hiện** do lệnh xóa bị môi trường từ chối. Không ghi DoD cleanup PASS.
- Đã kiểm: 36/36 tests trước, 36/36 sau khi thêm tài liệu (không có cleanup); 4 MP4 không có SRT, metadata 1080p; 5 checkpoint nạp được; 7 stage/worker/UI; junction bảo vệ dataset; cấu trúc dữ liệu và artifact lịch sử.
- Chưa đủ: SRT/flight log, ground truth video, metric FP/km/recall, ngưỡng BA, xác nhận xóa artifact lớn, post-cleanup regression.
- Bước tiếp: RG-AI-P0-02 theo phần 4 báo cáo; nếu được phép cleanup thì chỉ xóa target đã xác minh, rồi chạy lại suite và đối chiếu.
