# RoadGuard AI — Bộ Tài Liệu Bàn Giao & Đánh Giá Dự Án

> **Thời điểm xuất tài liệu (Export Timestamp):** 2026-10-10 16:30 (Giờ địa phương)  
> **Phiên bản hệ thống:** RoadGuard AI v2.0 MVP  
> **Tổng số file source code/cấu hình:** 56 file  
> **Tổng số dòng code & tài liệu:** ~18,450 dòng (Python, HTML, YAML, Markdown)  

---

## 📌 Tóm Tắt Dự Án (10 Dòng)

1. **Tên dự án:** RoadGuard AI — Hệ thống phát hiện, phân loại chuyên sâu và thẩm định khuyết tật mặt đường (Ổ gà, Vết nứt) từ Video Flycam/Drone và Dataset.
2. **Kiến trúc chính:** Mô hình xử lý 2 Tầng (Stage 1: Local YOLOv11 Scanner phát hiện BBox siêu tốc; Stage 2: KTV AI Inspector dùng GPT-5.4 Vision thẩm định bối cảnh, lọc bóng râm và phân loại chi tiết).
3. **Mô hình AI Local:** Sử dụng YOLOv11n (2.59M tham số, 5.22 MB) hỗ trợ các lớp `0: pothole` (Ổ gà), `1: crack` (Vết nứt mặt đường bê tông / nhựa).
4. **Hệ thống Curation:** Module `auto_tagger`, `crack_analyzer`, `kdv_inspector`, `deduplicator`, `dataset_exporter` tự động lọc mẫu giả (False Alarms), khử trùng lặp và đóng gói dataset YOLO.
5. **Giao diện người dùng:** Single Page Application (SPA) HTML5/JS thuần kết hợp FastAPI Web Server (`run_ui.py`) phục vụ tại cổng `8080`.
6. **Tập dữ liệu cốt lõi:** Bộ dữ liệu `unified_road_dataset_15k` (15,000 ảnh) và `pothole_dataset_5k` (5,000 ảnh) tích hợp 40.4% mẫu âm tính (Hard Negatives) triệt tiêu báo động giả do bóng râm.
7. **Hệ thống Test Cases:** 7 bộ test case tiêu chuẩn trong `data/mvp_test_cases/` (`01_pothole_deep` đến `07_hard_negatives`).
8. **Kịch bản huấn luyện:** Hỗ trợ fine-tune Transfer Learning với cơ chế khóa Backbone (`freeze=10`, `lr0=0.001`) bảo vệ tri thức cũ.
9. **Tích hợp GPS/GSD:** Module `srt_parser` đọc dữ liệu telemetry Flycam DJI, tính toán độ phân giải mặt đất GSD (cm/pixel) và khoảng cách tọa độ Haversine.
10. **Trạng thái vận hành:** Server Web UI đang chạy ổn định tại `http://127.0.0.1:8080` sẵn sàng phục vụ thực nghiệm và demo.

---

## ⚡ Cẩm Nang Chạy Nhanh (Quick Start)

### 1. Môi trường & Dependencies
```bash
# Đảm bảo Python 3.10+
pip install -r requirements.txt
```

### 2. Cấu hình Biến Môi Trường (KTV Tầng 2)
Tạo file `.env` từ file mẫu `.env.example`:
```env
KDV_API_KEY=your_actual_api_key_here
KDV_BASE_URL=https://api.xah.io/v1
KDV_MODEL=gpt-5.4
```

### 3. Khởi Chạy Web Server UI
```bash
python run_ui.py
# Truy cập giao diện tại: http://127.0.0.1:8080
```

### 4. Lệnh Chạy Huấn Luyện / Nâng Cấp Model
```bash
# Huấn luyện nâng cấp Phase 2 (Local GPU)
python tools/train_phase2_local.py --weights weights/trained/roadguard_crack_yolo11n_v1.pt --data data/unified_road_dataset_15k/data_phase2.yaml --epochs 35 --batch 16 --freeze 10

# Quét & Trích xuất Test Cases
python tools/extract_testcases_and_export_dataset.py
```

---

## 📑 Danh Mục Tài Liệu Bàn Giao

- [01_overview.md](file:///f:/train%20AI%20đồ%20án/docs/project_export/01_overview.md) — Tổng quan mục tiêu, sơ đồ kiến trúc hệ thống và Tech Stack chi tiết.
- [02_codebase.md](file:///f:/train%20AI%20đồ%20án/docs/project_export/02_codebase.md) — Cây thư mục dự án và đặc tả từng file `.py` (Class, Function, Line Ref).
- [03_api_ui.md](file:///f:/train%20AI%20đồ%20án/docs/project_export/03_api_ui.md) — Chi tiết 20 REST API Endpoints và luồng xử lý JavaScript trên Web UI.
- [04_models_training.md](file:///f:/train%20AI%20đồ%20án/docs/project_export/04_models_training.md) — Đặc tả các Checkpoints YOLOv11, siêu tham số train và kết quả Benchmark.
- [05_data.md](file:///f:/train%20AI%20đồ%20án/docs/project_export/05_data.md) — Cấu trúc các bộ dữ liệu 5K, 15K, 20K, 44K và 7 tập Test Case MVP.
- [06_config.md](file:///f:/train%20AI%20đồ%20án/docs/project_export/06_config.md) — Toàn bộ file cấu hình `.yaml`, hằng số ngưỡng KTV/Inference và biến môi trường.
- [07_devlog.md](file:///f:/train%20AI%20đồ%20án/docs/project_export/07_devlog.md) — Nhật ký phát triển, danh sách tính năng hoàn tất, bug đã khắc phục và TODO comments.
