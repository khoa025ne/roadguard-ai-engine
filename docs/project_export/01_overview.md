# 01 — Tổng Quan Kiến Trúc & Tech Stack Dự Án RoadGuard AI

## 1. Mục Tiêu Dự Án (Project Goals)

RoadGuard AI là hệ thống kiểm định và đánh giá tự động khuyết tật mặt đường (Ổ gà, Vết nứt) từ dữ liệu khảo sát Video Flycam/Drone và các Bộ dữ liệu ảnh thực địa. Dự án giải quyết các mục tiêu cốt lõi:
- **Phát hiện đa lớp khuyết tật:** Ổ gà (`pothole` - ID 0) và Vết nứt bề mặt (`crack` - ID 1) trên bề mặt đường bê tông xi măng / bê tông nhựa asphalt.
- **Phân loại chuyên sâu (Fine-grained Taxonomy):** Phân loại vết nứt dọc (`crack_longitudinal`), vết nứt ngang (`crack_transverse`), vết nứt chân chim mai rùa (`crack_alligator`), nứt mép (`crack_edge`), khe co giãn mối nối (`joint_gap`) và ổ gà nông/sâu/đọng nước.
- **Triệt tiêu báo động giả (False Alarm Suppression):** Loại bỏ bóng râm cây cối, bóng xe, bóng dây điện, vết lóa nắng hoặc rác thải đường thông qua cơ chế kiểm duyệt 2 Tầng.
- **Khử trùng lặp đối tượng (Deduplication):** Đảm bảo cùng một đối tượng khuyết tật xuất hiện qua nhiều frame video không bị tính lặp bằng thuật toán ghép khoảng cách Haversine GPS & ma trận độ tương đồng hình ảnh SSIM/Cosine (`src/curation/deduplicator.py:22`).
- **Xuất bản Dataset YOLO:** Tự động chuẩn hóa Bounding Box, phân luồng Train/Val và nén file ZIP phục vụ huấn luyện tiếp diễn trên Google Colab / Kaggle.

---

## 2. Sơ Đồ Kiến Trúc Hệ Thống (Text Architecture Diagram)

```
                       DỮ LIỆU ĐẦU VÀO (INPUT)
      ┌───────────────────────────┴───────────────────────────┐
      │                                                       │
  Video Flycam (.mp4, .mov)                            Tệp Nén Dataset (.zip)
  + Telemetry DJI (.srt GPS)                           hoặc Thư Mục Ảnh
      │                                                       │
      ▼                                                       ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │ TẦNG 1: STAGE 1 — LOCAL YOLOv11 SCANNER (TỐC ĐỘ CAO / EDGE INFERENCE)    │
 ├─────────────────────────────────────────────────────────────────────────┤
 │ • RawVideoAnalyzer (src/ingestion/raw_video_analyzer.py:31)            │
 │ • VideoFrameExtractor & DJISRTParser (src/ingestion/srt_parser.py:33)   │
 │ • TileSplitter (src/inference/tiling_engine.py:12) [Tiling 640x640]     │
 │ • RoadDefectPredictor (src/inference/predictor.py:15)                   │
 │   => Output: Bounding Box [x1, y1, x2, y2], Class Base ID (0/1), Conf     │
 └────────────────────────────────────┬────────────────────────────────────┘
                                      │ Crops (Ảnh Cận Cảnh) + Metadata
                                      ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │ TẦNG 2: STAGE 2 — KTV AI INSPECTOR & AUTO-TAGGER (GPT-5.4 VISION)       │
 ├─────────────────────────────────────────────────────────────────────────┤
 │ • AIAutoTagger (src/curation/auto_tagger.py:21)                         │
 │ • CrackAnalyzer (src/curation/crack_analyzer.py:66) [Độ mở/Góc nứt]    │
 │ • KDVInspector (src/curation/kdv_inspector.py:65) [Dual-View Context]   │
 │ • DefectDeduplicator (src/curation/deduplicator.py:22)                  │
 │   => Phán quyết: Valid / False Alarm (Bóng râm), Relabel, Severity      │
 └────────────────────┬──────────────────────────────────┬─────────────────┘
                      │                                  │
                      ▼                                  ▼
 ┌──────────────────────────────────────┐ ┌────────────────────────────────┐
 │ WEB UI SPA DASHBOARD                 │ │ DATASET EXPORTER               │
 ├──────────────────────────────────────┤ ├────────────────────────────────┤
 │ • Single Page App (index.html:1)     │ │ • DatasetExporter              │
 │ • FastAPI Server (ui_server.py:95)   │ │   (src/curation/               │
 │ • 4 Golden Metrics Evaluation        │ │    dataset_exporter.py:21)     │
 │ • Visual Crop Cards + Relabel Matrix │ │ => Output: YOLO Dataset (.zip) │
 └──────────────────────────────────────┘ └────────────────────────────────┘
```

---

## 3. Tech Stack & Dependencies Chi Tiết

Dự án sử dụng bộ công nghệ tiêu chuẩn Python 3.12 (tham chiếu [`requirements.txt:1-25`](file:///f:/train%20AI%20đồ%20án/requirements.txt#L1-L25)):

### Core AI & Machine Learning
- **`ultralytics>=8.3.0`** ([`requirements.txt:5`](file:///f:/train%20AI%20đồ%20án/requirements.txt#L5)): Framework YOLOv11 chính để load weights `.pt`, thực hiện forward pass inference tile 640x640 và export dataset.
- **`torch>=2.0.0` & `torchvision>=0.15.0`** ([`requirements.txt:6-7`](file:///f:/train%20AI%20đồ%20án/requirements.txt#L6-L7)): Engine tính toán ma trận Tensor, hỗ trợ tăng tốc CUDA GPU.

### Computer Vision & Image Processing
- **`opencv-python>=4.8.0`** ([`requirements.txt:10`](file:///f:/train%20AI%20đồ%20án/requirements.txt#L10)): Giải mã video, crop bounding box, biến đổi không gian màu BGR $\rightarrow$ GRAY $\rightarrow$ HSV, tính toán ma trận Canny Edge và Adaptive Thresholding (`src/curation/auto_tagger.py:86`, `src/curation/crack_analyzer.py:90`).
- **`numpy>=1.24.0`** ([`requirements.txt:11`](file:///f:/train%20AI%20đồ%20án/requirements.txt#L11)): Tính toán độ sáng trung bình (`np.mean`), độ lệch chuẩn (`np.std`), khoảng cách hình học NMS.
- **`Pillow>=9.0.0`** ([`requirements.txt:15`](file:///f:/train%20AI%20đồ%20án/requirements.txt#L15)): Mã hóa ảnh base64 gửi sang API Multimodal Vision.

### Backend REST API & Web Server
- **`fastapi>=0.100.0`** ([`src/api/ui_server.py:25`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L25)): Framework xây dựng 20 REST API Endpoints hỗ trợ bất đồng bộ `async/await`, BackgroundTasks.
- **`uvicorn>=0.22.0`** ([`run_ui.py:46`](file:///f:/train%20AI%20đồ%20án/run_ui.py#L46)): Server ASGI đa luồng phục vụ ứng dụng tại `http://127.0.0.1:8080`.

### Utilities & Helpers
- **`tqdm>=4.65.0`** ([`requirements.txt:14`](file:///f:/train%20AI%20đồ%20án/requirements.txt#L14)): Hiển thị thanh tiến trình khi quét ảnh dataset.
- **`httpx` & `requests`**: Gọi API đến KTV GPT-5.4 Vision endpoint (`src/curation/kdv_inspector.py:90`).
