# 📌 BẢNG THEO DÕI TIẾN ĐỘ & QUY TẮC BỘ PHẬN AI (TIẾN ĐỘ.MD)
> **DỰ ÁN: RoadGuard / CrackScan VN — Hệ thống AI Phân tích khuyết tật cầu đường nông thôn**  
> **Phiên bản:** v1.0.0  
> **Cập nhật lần cuối:** 2026-09-22  
> **Tài liệu nền tảng:** [ke_hoach_thuc_thi_AI.md](file:///f:/train%20AI%20đồ%20án/ke_hoach_thuc_thi_AI.md), [AI_task.md](file:///f:/train%20AI%20đồ%20án/diagram/AI_task.md)

---

## 🛑 QUY TẮC BẮT BUỘC (MANDATORY AGENT WORKFLOW RULE)

> ⚠️ **ĐỐI VỚI BẤT KỲ AI AGENT HOẶC DEVELOPER NÀO THAM GIA CODE:**
> 
> 1. **TRƯỚC KHI LÀM BẤT CỨ VIỆC GÌ (Pre-session):**
>    - BẮT BUỘC mở và đọc file `tiến độ.md` này để nắm rõ trạng thái hiện tại, việc đang làm dở và các ràng buộc chưa giải quyết.
>    - BẮT BUỘC đọc file [ke_hoach_thuc_thi_AI.md](file:///f:/train%20AI%20đồ%20án/ke_hoach_thuc_thi_AI.md) tại đúng Epic/Task chuẩn bị triển khai để hiểu rõ **Lý do (Why)**, **Ràng buộc (Constraints)** và **User Story**.
> 2. **KHI THỰC HIỆN THAY ĐỔI (In-session):**
>    - Khi có bất kỳ thay đổi nào về **Logic thuật toán**, **Cấu trúc dữ liệu**, **API Payload** hoặc **Quy mô module**:
>    - BẮT BUỘC quét toàn bộ các file trong scope của Đội AI:
>      * `hadle_vid.py` (Xử lý video & tiling)
>      * `srt_gps_parser.py` (Định vị SRT & GSD)
>      * `trainAI_watch_img.py` (Inference & Metric viewer)
>      * `train_crack_model.py` / `train_pothole_model.py` (Huấn luyện model)
>      * `pothole_dataset.yaml` / `crack_dataset.yaml` (Cấu hình dataset)
>      * `ai_worker_service.py` / `mock_ai_adapter.py` (API tích hợp)
>    - Đảm bảo **tuyệt đối không để xảy ra xung đột logic** hoặc vỡ hợp đồng dữ liệu với Backend ASP.NET Core.
> 3. **SAU KHI HOÀN THÀNH MỖI SECTION / TASK (Post-session):**
>    - CẬP NHẬT NGAY trạng thái checklist trong file `tiến độ.md` này (`[ ]` $\rightarrow$ `[x]`).
>    - Ghi nhận chi tiết vào phần **Nhật ký thay đổi (Changelog)** ở cuối file.
>    - Kiểm tra tính nguyên vẹn của toàn bộ pipeline trước khi kết thúc phiên.

---

## 📊 BẢNG TỔNG QUAN TIẾN ĐỘ THEO TỪNG EPIC

| Mã Epic | Tên Epic | Số Task | Đã xong | Đang làm | Chưa làm | Tiến độ |
|:---|:---|:---:|:---:|:---:|:---:|:---:|
| **EPIC 1** | Ingestion, Telemetry Sync & Quality Gate | 4 | 3 | 1 | 0 | **75%** |
| **EPIC 2** | Model Architecture & Training Pipeline | 4 | 2 | 1 | 1 | **50%** |
| **EPIC 3** | Spatial Tiling & Inference Engine | 4 | 2 | 1 | 1 | **50%** |
| **EPIC 4** | 2D Metric Estimation & Spatial Tracking | 3 | 1 | 1 | 1 | **33%** |
| **EPIC 5** | API Contract & Distributed Async Worker | 4 | 0 | 1 | 3 | **15%** |
| **EPIC 6** | Quality Gate & Field Validation Benchmark | 3 | 0 | 0 | 3 | **0%** |
| **TỔNG** | **Toàn bộ hệ thống AI Analysis** | **22** | **8** | **5** | **9** | **~42%** |

---

## 📋 CHECKLIST CHI TIẾT TỪNG NHIỆM VỤ (TASK DETAIL)

### 📌 EPIC 1: Video Ingestion, Telemetry Sync & Quality Gate
- [x] **Task 1.1: Frame Sampling Engine:** Trích xuất 2 fps từ video 2.7K @ 30fps ([src/ingestion/video_extractor.py](file:///f:/train%20AI%20đồ%20án/src/ingestion/video_extractor.py)).
- [x] **Task 1.2: Motion Blur Filter (KS08):** Lọc rung mờ bằng Laplacian variance $< 100.0$ ([src/ingestion/video_extractor.py](file:///f:/train%20AI%20đồ%20án/src/ingestion/video_extractor.py)).
- [x] **Task 1.3: DJI SRT Parser & Realtime GSD:** Parse tọa độ, độ cao bay, tính GSD thời gian thực ([src/ingestion/srt_parser.py](file:///f:/train%20AI%20đồ%20án/src/ingestion/srt_parser.py)).
- [x] **Task 1.4: Pre-flight Quality Gate Report & Raw Analyzer:** Kiểm định chất lượng video thô, xuất `quality_report.json`, cảnh báo mờ/tối/bay cao, sinh lỗi `DATA_FAILURE` và chạy theo `ProcessingInputManifest` ([src/ingestion/raw_video_analyzer.py](file:///f:/train%20AI%20đồ%20án/src/ingestion/raw_video_analyzer.py), [process_raw_video.py](file:///f:/train%20AI%20đồ%20án/process_raw_video.py)).

### 📌 EPIC 2: Model Architecture & Training Pipeline
- [x] **Task 2.1: Chuẩn hóa Dataset Pothole:** 3,940 ảnh (3,345 train, 397 valid, 198 test) giải nén tại [data/pothole/](file:///f:/train%20AI%20đồ%20án/data/pothole) và cấu hình [configs/pothole_dataset.yaml](file:///f:/train%20AI%20đồ%20án/configs/pothole_dataset.yaml).
- [x] **Task 2.2: Setup Script Huấn luyện:** [src/training/train_pothole.py](file:///f:/train%20AI%20đồ%20án/src/training/train_pothole.py) cho local và [notebooks/train_pothole_colab_kaggle.ipynb](file:///f:/train%20AI%20đồ%20án/notebooks/train_pothole_colab_kaggle.ipynb) cho Cloud GPU.
- [ ] **Task 2.3: Huấn luyện hoàn tất & Xuất xưởng `pothole_best.pt`:** Chạy xong 50 epochs trên GPU T4, đạt mAP50 $> 0.65$.
- [ ] **Task 2.4: Mở rộng Dataset 8 Classes (Active Learning):** [src/training/train_crack.py](file:///f:/train%20AI%20đồ%20án/src/training/train_crack.py) và [configs/crack_8classes.yaml](file:///f:/train%20AI%20đồ%20án/configs/crack_8classes.yaml).

### 📌 EPIC 3: Spatial Tiling & Inference Engine
- [x] **Task 3.1: Tile Splitter 640x640 (Overlap 20%):** Chia khung hình $2720 \times 1530$ thành lưới tile ([src/inference/tiling_engine.py](file:///f:/train%20AI%20đồ%20án/src/inference/tiling_engine.py)).
- [x] **Task 3.2: Base Inference & Visualization:** Chạy YOLO trên ảnh và vẽ kết quả ([src/inference/predictor.py](file:///f:/train%20AI%20đồ%20án/src/inference/predictor.py)).
- [x] **Task 3.3: Cross-Tile NMS Merging:** Hợp nhất các bounding box ở vùng gối đầu $20\%$ về tọa độ gốc $2720 \times 1530$ không bị phân mảnh ([src/inference/tiling_engine.py](file:///f:/train%20AI%20đồ%20án/src/inference/tiling_engine.py)).
- [ ] **Task 3.4: Target Bands & Context Overlap (AI15, AI17):** Hỗ trợ lọc theo dải `SURFACE`, `LEFT_EDGE`, `RIGHT_EDGE` và xử lý biên block.

### 📌 EPIC 4: 2D Metric Estimation & Spatial Tracking
- [x] **Task 4.1: Tính kích thước 2D từ GSD:** Ước lượng chiều rộng (mm), chiều dài (m) và phân cấp severity ([src/measurement/metric_estimator.py](file:///f:/train%20AI%20đồ%20án/src/measurement/metric_estimator.py)).
- [x] **Task 4.2: Phép chiếu tọa độ địa lý (Georeferencing):** Tách biệt `aircraft_location` và `geometry` của vết nứt dưới đất, gán `defect_location_method`.
- [x] **Task 4.3: Tracking đa khung hình & Đề xuất gộp (ByteTrack - AI08):** Khử trùng lặp qua các frame kế tiếp, tạo danh sách `DefectObservation` đề xuất cho PM gộp ([src/measurement/spatial_tracker.py](file:///f:/train%20AI%20đồ%20án/src/measurement/spatial_tracker.py)).

### 📌 EPIC 5: Backend Integration & Distributed Async Worker
- [x] **Task 5.1: Chuẩn hóa JSON Payload Contract & GeoJSON:** Khớp 100% trường dữ liệu với bảng `AIDetection` và xuất GeoJSON FeatureCollection cho bản đồ số hóa ([src/contracts/aidetection_schema.py](file:///f:/train%20AI%20đồ%20án/src/contracts/aidetection_schema.py)).
- [ ] **Task 5.2: Idempotency & Error Classification:** Phân biệt lỗi `INFRASTRUCTURE` vs `DATA`, xử lý trùng lặp job `deduplication_key`.
- [x] **Task 5.3: Mock AI Adapter:** Module sinh dữ liệu giả lập có tọa độ hợp lệ để đội Backend ASP.NET Core test quy trình sớm ([src/contracts/mock_ai_adapter.py](file:///f:/train%20AI%20đồ%20án/src/contracts/mock_ai_adapter.py)).
- [x] **Task 5.4: Master Pipeline Runner & Raw CLI:** Script chạy End-to-End [pipeline.py](file:///f:/train%20AI%20đồ%20án/pipeline.py) và [process_raw_video.py](file:///f:/train%20AI%20đồ%20án/process_raw_video.py).

### 📌 EPIC 6: Quality Gate & Field Validation Benchmark
- [ ] **Task 6.1: Benchmark End-to-End Pipeline:** Đo thời gian xử lý video 5 phút (yêu cầu $\le 5$ phút trên GPU T4).
- [ ] **Task 6.2: Nghiệm thu độ chính xác mô hình:** Đánh giá Precision, Recall, mAP50 trên tập dữ liệu kiểm thử độc lập.
- [ ] **Task 6.3: Xuất báo cáo kiểm định nghiên cứu (RS01 - RS06):** So sánh sai số kích thước đo từ Drone vs Số đo thước cơ học thực địa.

---

## 📝 NHẬT KÝ THAY ĐỔI (CHANGELOG)

| Ngày / Giờ | Người / Agent thực hiện | Nội dung thay đổi | Các file bị tác động | Trạng thái sau cập nhật |
|:---|:---|:---|:---|:---|
| **2026-09-15** | Solo AI Dev | Khởi tạo dự án, phân tích phần cứng DJI Mini 2 SE, tạo script nền tảng. | `srt_gps_parser.py`, `hadle_vid.py` | Hoàn thành nền tảng |
| **2026-09-22 14:15** | AI Pair Programmer | Phân tích Base model `best.pt` (COCO 80 classes) và giải nén toàn vẹn 3,940 ảnh từ `archive.zip`. | `archive/`, `pothole_dataset.yaml` | Sẵn sàng dataset |
| **2026-09-22 15:35** | AI Pair Programmer | Tối ưu notebook Colab chống lỗi đường dẫn và hỗ trợ GPU T4. | `notebooks/train_pothole_colab_kaggle.ipynb` | Sẵn sàng Cloud Train |
| **2026-09-22 16:40** | AI Pair Programmer | Đọc toàn bộ tài liệu kiến trúc RoadGuard, xuất file đặc tả nhiệm vụ AI. | `docs/AI_task.md` | Hoàn tất phân tích nghiệp vụ |
| **2026-09-22 17:00** | AI Pair Programmer | Thiết lập quy tắc Agent Rule, tạo `tiến độ.md` và `ke_hoach_thuc_thi_AI.md`. | `tiến độ.md`, `ke_hoach_thuc_thi_AI.md` | Đã thiết lập chuẩn quản trị |
| **2026-09-22 17:15** | AI Pair Programmer | Tái cấu trúc toàn diện codebase thành 5 tầng kiến trúc trong `src/`, loại bỏ file thừa, tạo bộ test tự động. | Toàn bộ codebase | Hệ thống chuẩn hóa 100% |
| **2026-09-22 17:25** | AI Pair Programmer | **XÂY DỰNG TOOL XỬ LÝ DỮ LIỆU THÔ TỪ BE:** Tạo `RawVideoAnalyzer` và `process_raw_video.py` xử lý video + SRT + Manifest, tự động xuất `inspection_report.json`, `inspection_layer.geojson`, `quality_report.json` và ảnh crop bằng chứng `crops/`. Bổ sung unit test georeferencing & geojson. | `src/ingestion/raw_video_analyzer.py`, `process_raw_video.py`, `src/contracts/aidetection_schema.py`, `tests/test_pipeline.py` | Đạt 6/6 Unit Test Pass |
| **2026-09-22 17:32** | AI Pair Programmer | **TEST THỰC TẾ VIDEO FLYCAM (DJI_0057.MP4):** Chạy kiểm thử thành công trên video thực tế `F:\Fake_admin\Downloads\đồ án test vid\DJI_0057.MP4`. Quality Gate đạt PASSED (độ nét 968.86 > 100). Trích xuất 25 frame, chạy inference 640x640 tiling, phát hiện 185 đối tượng/khuyết tật, xuất đầy đủ `inspection_report.json`, `inspection_layer.geojson`, `quality_report.json`, 25 ảnh visualization và 185 ảnh crop bằng chứng. | `process_raw_video.py`, `src/ingestion/raw_video_analyzer.py`, `src/ingestion/video_extractor.py` | Test thực tế thành công 100% |
| **2026-09-23 00:16** | AI Pair Programmer | **XUẤT BẢN MASTER README.MD & ASSETS DEMO:** Tạo file `README.md` đỉnh cao với sơ đồ Mermaid, demo ảnh nhận diện, cấu trúc thư mục 5 tầng, quickstart và bộ quy tắc vận hành cho AI Agent & Dev team. Chuẩn bị sẵn Description & Topics cho GitHub repository. | `README.md`, `assets/detection_demo.jpg`, `assets/crop_demo.jpg` | Hoàn thành bộ mặt Repo |
