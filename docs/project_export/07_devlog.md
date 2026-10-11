# 07 — Nhật Ký Phát Triển, Tình Trạng & TODOs (DevLog & Status)

## 1. Danh Sách Tính Năng Đã Hoàn Tất (Completed Features)

1. **Web UI SPA & FastAPI Server (`http://127.0.0.1:8080`):**
   - Hoàn thiện 20 REST API Endpoints ([`src/api/ui_server.py:86-1144`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L86-L1144)).
   - Tự động quét và sắp xếp mô hình mới nhất theo thời gian sửa đổi `mtime` ([`src/api/ui_server.py:98-113`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L98-L113)).
   - Sửa triệt để bug chọn mặc định mô hình ở vị trí chỉ số 0 (`idx === 0`) trong [`src/api/web/index.html:816`](file:///f:/train%20AI%20đồ%20án/src/api/web/index.html#L816).

2. **Stage 2 AI KTV Inspector (GPT-5.4 Vision):**
   - Hỗ trợ chế độ DUAL-VIEW CONTEXT thẩm định ảnh toàn cảnh (Overview Frame) kết hợp mảng cắt phóng to ([`src/curation/kdv_inspector.py:256`](file:///f:/train%20AI%20đồ%20án/src/curation/kdv_inspector.py#L256)).
   - Tự động hiển thị 4 Golden Metrics, Tag Chips linh hoạt và Bảng so sánh Matrix trên Web UI.

3. **Hệ Thống Đóng Gói Dataset & Test Cases MVP:**
   - Xây dựng thành công 7 bộ Test Case tiêu chuẩn MVP tại [`data/mvp_test_cases/`](file:///f:/train%20AI%20đồ%20án/data/mvp_test_cases).
   - Đóng gói 2 tập dữ liệu cốt lõi: `unified_road_dataset_15k.zip` (15,000 ảnh) và `pothole_dataset_5k.zip` (5,000 ảnh).

4. **Kịch Bản & Notebook Huấn Luyện:**
   - Hoàn thành script Transfer Learning `train_upgrade_model.py` và `train_phase2_local.py` với cơ chế khóa Backbone (`freeze=10`, `lr0=0.001`).
   - Khởi tạo 2 Jupyter Notebooks chuẩn hóa Colab Free: `RoadGuard_Phase2_Upgrade_Colab.ipynb` và `RoadGuard_Pothole_5K_Colab.ipynb`.

---

## 2. Các Bug Đã Biết & Lưu Ý Vận Hành (Known Bugs & Gotchas)

1. **Hiện tượng nhận diện nhầm bóng cây của Model 1-Class (`roadguard_pothole_best_5k.pt`):**
   - **Mô tả:** Khi chạy model 1-class ổ gà trên video nắng gắt (`DJI_0061.MP4`), các mảng bóng râm cây cối bị khoanh nhầm thành `ổ gà`.
   - **Nguyên nhân:** Model 1-class không có đầu ra cho lớp `crack` nên bị ép gán các mảng tối tương phản cao vào nhãn `pothole`.
   - **Giải pháp:** Chuyển sang mô hình Unified 2-class `roadguard_best_15k.pt` (chứa 40.4% mẫu âm tính) và tích chọn ô **`☑ Tự động thẩm định KTV Tầng 2`** trên Web UI để triệt tiêu bóng râm (`false_alarm_shadow`).

2. **Khóa Mã Hóa Encoding Console Windows:**
   - Khi chạy script Python xuất ra console Windows tiếng Việt, cần dùng `sys.stdout.reconfigure(encoding='utf-8')` để tránh lỗi `UnicodeEncodeError`.

---

## 3. Danh Sách TODOs & Định Hướng Tiếp Theo

Quét toàn bộ comment `TODO` / `FIXME` trong codebase:

1. **`[TODO]` Xuất Báo Cáo Định Dạng PDF (`docs/antigravity_prompt.md:85`):**
   - Tích hợp thư viện `weasyprint>=60.0` để tự động chuyển đổi file HTML báo cáo nghiệm thu sang định dạng PDF phục vụ bàn giao cho chủ đầu tư.
2. **`[TODO]` Tăng Tốc Xử Lý Video 4K 60FPS Stream:**
   - Tối ưu hóa luồng Queue trong `worker_service.py` để hỗ trợ giải mã phần cứng GPU (NVDEC/FFmpeg) khi xử lý các video flycam độ phân giải 4K 60FPS dung lượng lớn.
