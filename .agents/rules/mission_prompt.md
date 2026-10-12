# MISSION: ROADGUARD AUTONOMOUS RUN — chạy tới khi hết dự án
*Paste 1 lần duy nhất cho Antigravity agent trước khi đi ngủ. Từ đây agent tự hành.*

Bạn là Antigravity agent. Nhiệm vụ: thực hiện TUẦN TỰ hàng đợi bên dưới tới khi hết dự án,
đồng bộ với điều phối viên (đào kara) qua GitHub repo này. Không cần hỏi lại từng bước.

## 0. Kỷ luật chung (giữ nguyên mọi quy tắc đã chốt trước đây)
- Task phức tạp: dùng sequential-thinking MCP, phân rã từng bước, verify rồi mới làm.
- Mọi khẳng định kỹ thuật phải có bằng chứng: file:dòng hoặc output lệnh. Không đoán mò.
- Xóa/di chuyển file: CHỈ xóa những mục đã liệt kê trong audit được duyệt. Mục mới phát hiện
  → ghi "xem lại sau", KHÔNG tự xóa.
- Không commit secret, không push file >500MB ngoài dataset đã duyệt.

## 1. Cơ chế đồng bộ (BẮT BUỘC sau mỗi task)
1. `mkdir -p inbox reports/agent_reports` (lần đầu).
2. Viết báo cáo task → `reports/agent_reports/<task-slug>.md` (ngắn gọn: đã làm gì, bằng chứng,
   metrics, còn lại gì).
3. `git add` (chỉ file liên quan task) → `git commit -m "<task-slug>: <tóm tắt>"` → `git push`.
   Push fail (auth/mạng) → ghi rõ trong báo cáo, KHÔNG dừng, làm task tiếp theo.
4. `git pull` → đọc `inbox/NEXT_PROMPT.md`:
   - CÓ chỉ thị mới từ đào kara → ƯU TIÊN làm theo, thay thế task tiếp theo trong hàng đợi.
     Xong thì đổi tên file thành `inbox/_done_<giờ>.md` để không làm lại.
   - KHÔNG có → làm task tiếp theo trong hàng đợi.
5. Blocker không tự giải được → ghi `reports/agent_reports/BLOCKER.md` (mô tả + đã thử gì)
   → push → DỪNG, chờ người.

## 2. Hàng đợi nhiệm vụ (làm tuần tự)

> ✅ TASK P0-1b (đo hiệu quả mask filter) ĐÃ HOÀN THÀNH ngày 2026-10-12: FP cỏ/cây 6→0,
> giữ 22/22 detection thật, CPU 1.76 FPS (seg bottleneck 86.7%). Bắt đầu từ task tiếp theo.

### TASK INTEGRATE-MULTICLASS — Đấu model multi-class mới
1. Kiểm tra `weights/trained/roadguard_multiclass_v1_best.pt` tồn tại không.
   CHƯA CÓ → ghi "SKIP — chờ file từ Kaggle", sang task tiếp. KHÔNG chờ, KHÔNG hỏi.
2. CÓ → eval per-class AP trên test split của data/merged; so với baseline
   (pothole AP@50 89.06%, crack 94.30%); cập nhật model path trong configs/pipeline.yaml (02_detect);
   chạy e2e 1 video ngắn.
DONE khi: báo cáo AP từng class + không regression quá 3% (regression → báo cáo, không tự rollback).

### TASK SEVERITY-RULES — Chuẩn hóa đo mức độ hư hỏng
Ngưỡng FHWA tham khảo: nứt dọc <3mm nhẹ / 3–13mm TB / ≥13mm nặng;
nứt ngang <3mm nhẹ / 3–6mm TB / ≥6mm nặng. Quy tắc GSD: chi tiết nhỏ nhất đo được ≈ 2×GSD
(muốn đo 3mm cần GSD ≤1.5mm/px).
1. Kiểm tra `05_measure.py` (hoặc module tương đương): đã áp RULES theo ngưỡng trên chưa?
   GSD đang tính từ đâu?
2. Thông số camera drone thật CHƯA CÓ → dùng tạm GSD ước lượng từ độ cao bay, đánh dấu mọi
   giá trị tạm bằng comment `# TẠM — chờ thông số camera thật`.
DONE khi: severity tính theo RULES có tài liệu, giá trị tạm được đánh dấu rõ.

### TASK KTV-WIRING — Đấu nối KTV tầng 2
1. Kiểm tra `kdv_inspector.py` đã được pipeline stage 06_inspect GỌI thật chưa (không chỉ tồn tại file).
2. Chạy e2e 1 video ngắn, xác nhận log cho thấy 06_inspect đã chạy (không skip silently).
DONE khi: e2e exit 0 + bằng chứng 06_inspect hoạt động.

### TASK PDF-REPORT — Báo cáo PDF
1. Kiểm tra export PDF (weasyprint): chưa có → triển khai, template đơn giản theo design tokens:
   nền #FFFFFF/#F4F7FA, chữ #0A2540/#3D4F61, accent #1E88C7, font Be Vietnam Pro/Inter,
   nút bo 4px, card bo 12px, KHÔNG box-shadow.
2. Sinh PDF mẫu từ 1 task thật: phải mở được, đủ trường (detections, severity, thời gian, GPS).
DONE khi: có file PDF mẫu + lệnh sinh lại được.

### TASK UI-POLISH — Khoác áo Thủy Mệnh cho Web UI
1. Áp design tokens (như trên) vào Web UI (ui_server.py/templates).
2. Tự chạy checklist anti-AI-slop 10 mục, mục nào vi phạm thì sửa:
   (1) cấm gradient tím-xanh mọi hình thức (2) cấm gradient text (3) cấm glassmorphism tràn lan
   (4) cấm emoji làm icon (5) cấm rounded-2xl + shadow đồng loạt (6) cấm layout SaaS generic
   (7) cấm số liệu/testimonial bịa (8) cấm ảnh stock generic (9) cấm màu ngoài palette
   (10) copy tiếng Việt: cấm "được...bởi", cấm chuỗi "của" liên hoàn, cấm giọng chatbot.
DONE khi: checklist 10/10 pass + UI chạy không lỗi.

### TASK FIELD-TEST — Test thực địa
1. Chạy full pipeline trên 1 video drone ĐẦY ĐỦ (không cắt 3s).
2. Báo cáo: tổng thời gian, FPS, số detection, % detection bị mask loại, phân bố severity,
   3 case tốt nhất + 3 case tệ nhất (kèm frame minh họa).
DONE khi: báo cáo field test hoàn chỉnh.

## 3. Kết thúc
Hết hàng đợi → ghi `reports/agent_reports/PROJECT_COMPLETE.md` (tổng kết từng task + metrics cuối
+ việc còn lại nếu có) → push → DỪNG. Chờ nghiệm thu.
