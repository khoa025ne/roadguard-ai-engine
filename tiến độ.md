# 📌 BẢNG THEO DÕI TIẾN ĐỘ & QUY TẮC BỘ PHẬN AI (TIẾN ĐỘ.MD)
> **DỰ ÁN: RoadGuard / CrackScan VN — Hệ thống AI Phân tích khuyết tật cầu đường nông thôn**  
> **Phiên bản:** v1.0.0  
> **Cập nhật lần cuối:** 2026-09-28  
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
>      * `src/api/worker_service.py` / `src/contracts/mock_ai_adapter.py` (API tích hợp)
>    - Đảm bảo **tuyệt đối không để xảy ra xung đột logic** hoặc vỡ hợp đồng dữ liệu với Backend ASP.NET Core.
> 3. **SAU KHI HOÀN THÀNH MỖI SECTION / TASK (Post-session):**
>    - CẬP NHẬT NGAY trạng thái checklist trong file `tiến độ.md` này (`[ ]` $\rightarrow$ `[x]`).
>    - Ghi nhận chi tiết vào phần **Nhật ký thay đổi (Changelog)** ở cuối file.
>    - Kiểm tra tính nguyên vẹn của toàn bộ pipeline trước khi kết thúc phiên.
> 4. **QUY TẮC NHÁNH & COMMIT GIT (Branching & Commits):**
>    - **Nhánh:** `main` (BẤT KHẢ XÂM PHẠM - cấm code trực tiếp); `dev` (Nhánh gốc phát triển); `feature/<ten-tinh-nang>` hoặc `fix/<ten-loi>` (Nhánh làm việc).
>    - **Commit:** Bắt buộc định dạng `<type>: <Mô tả bằng tiếng Việt>` (VD: `feat: tích hợp OpenCV cắt frame video`, `fix: sửa lỗi crash khi video không có frame`). Chi tiết xem [.agents/rules/git_workflow.md](file:///f:/train%20AI%20đồ%20án/.agents/rules/git_workflow.md).

---

## 📊 BẢNG TỔNG QUAN TIẾN ĐỘ THEO TỪNG EPIC

| Mã Epic | Tên Epic | Số Task | Đã xong | Đang làm | Chưa làm | Tiến độ |
|:---|:---|:---:|:---:|:---:|:---:|:---:|
| **EPIC 1** | Ingestion, Telemetry Sync & Quality Gate | 4 | 4 | 0 | 0 | **100%** |
| **EPIC 2** | Model Architecture & Training Pipeline | 4 | 3 | 0 | 1 | **75%** |
| **EPIC 3** | Spatial Tiling & Inference Engine | 4 | 4 | 0 | 0 | **100%** |
| **EPIC 4** | 2D Metric Estimation & Spatial Tracking | 3 | 3 | 0 | 0 | **100%** |
| **EPIC 5** | API Contract & Distributed Async Worker | 4 | 4 | 0 | 0 | **100%** |
| **EPIC 6** | Quality Gate & Field Validation Benchmark | 3 | 0 | 0 | 3 | **0%** |
| **TỔNG** | **Toàn bộ hệ thống AI Analysis** | **22** | **18** | **0** | **4** | **~82%** |

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
- [x] **Task 2.3: Huấn luyện hoàn tất & Xuất xưởng `crack_best.pt` / `pothole_best.pt`:** Mô hình YOLOv11 đã huấn luyện, lưu tại [weights/trained/crack_best.pt](file:///f:/train%20AI%20đồ%20án/weights/trained/crack_best.pt) và kiểm thử thành công trên video thực tế.
- [ ] **Task 2.4: Mở rộng Dataset 8 Classes (Active Learning):** [src/training/train_crack.py](file:///f:/train%20AI%20đồ%20án/src/training/train_crack.py) và [configs/crack_8classes.yaml](file:///f:/train%20AI%20đồ%20án/configs/crack_8classes.yaml).

### 📌 EPIC 3: Spatial Tiling & Inference Engine
- [x] **Task 3.1: Tile Splitter 640x640 (Overlap 20%):** Chia khung hình $2720 \times 1530$ thành lưới tile ([src/inference/tiling_engine.py](file:///f:/train%20AI%20đồ%20án/src/inference/tiling_engine.py)).
- [x] **Task 3.2: Base Inference & Visualization:** Chạy YOLO trên ảnh và vẽ kết quả ([src/inference/predictor.py](file:///f:/train%20AI%20đồ%20án/src/inference/predictor.py)).
- [x] **Task 3.3: Cross-Tile NMS Merging:** Hợp nhất các bounding box ở vùng gối đầu $20\%$ về tọa độ gốc $2720 \times 1530$ không bị phân mảnh ([src/inference/tiling_engine.py](file:///f:/train%20AI%20đồ%20án/src/inference/tiling_engine.py)).
- [x] **Task 3.4: Target Bands & Context Overlap (AI15, AI17):** Hỗ trợ phân dải `SURFACE`, `LEFT_EDGE`, `RIGHT_EDGE` (quy chuẩn lý trình bất biến theo chiều bay) và gắn cờ `is_context_overlap` cho các khuyết tật thuộc vùng biên block ([src/inference/tiling_engine.py](file:///f:/train%20AI%20đồ%20án/src/inference/tiling_engine.py)).

### 📌 EPIC 4: 2D Metric Estimation & Spatial Tracking
- [x] **Task 4.1: Tính kích thước 2D từ GSD:** Ước lượng chiều rộng (mm), chiều dài (m) và phân cấp severity ([src/measurement/metric_estimator.py](file:///f:/train%20AI%20đồ%20án/src/measurement/metric_estimator.py)).
- [x] **Task 4.2: Phép chiếu tọa độ địa lý (Georeferencing):** Tách biệt `aircraft_location` và `geometry` của vết nứt dưới đất, gán `defect_location_method`.
- [x] **Task 4.3: Tracking đa khung hình & Đề xuất gộp (ByteTrack - AI08):** Khử trùng lặp qua các frame kế tiếp, tạo danh sách `DefectObservation` đề xuất cho PM gộp ([src/measurement/spatial_tracker.py](file:///f:/train%20AI%20đồ%20án/src/measurement/spatial_tracker.py)).

### 📌 EPIC 5: Backend Integration & Distributed Async Worker
- [x] **Task 5.1: Chuẩn hóa JSON Payload Contract & GeoJSON:** Khớp 100% trường dữ liệu với bảng `AIDetection` (bổ sung `target_band`, `is_context_overlap`, `projected_station_m`) và xuất GeoJSON FeatureCollection cho bản đồ số hóa ([src/contracts/aidetection_schema.py](file:///f:/train%20AI%20đồ%20án/src/contracts/aidetection_schema.py)).
- [x] **Task 5.2: Idempotency & Error Classification:** Phân loại lỗi `INFRASTRUCTURE_ERROR` (cho phép retry với exponential backoff) vs `DATA_ERROR` (hỏng định dạng, cấm retry), quản lý `deduplication_key` bằng mã SHA256 chống duplicate processing ([src/contracts/idempotency.py](file:///f:/train%20AI%20đồ%20án/src/contracts/idempotency.py)).
- [x] **Task 5.3: Mock AI Adapter:** Module sinh dữ liệu giả lập có tọa độ hợp lệ, đầy đủ TargetBand và Context Overlap để đội Backend ASP.NET Core test quy trình sớm ([src/contracts/mock_ai_adapter.py](file:///f:/train%20AI%20đồ%20án/src/contracts/mock_ai_adapter.py)).
- [x] **Task 5.4: FastAPI Async Worker & Webhook Service (AI15, AI16, US-26):** Dịch vụ API bất đồng bộ nhận `ProcessingInputManifest`, quản lý hàng đợi tác vụ nền (BackgroundTasks), truy vấn trạng thái job và tự động gửi Webhook Callback về Backend ASP.NET Core ([src/api/worker_service.py](file:///f:/train%20AI%20đồ%20án/src/api/worker_service.py)).

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
| **2026-09-23 00:19** | AI Pair Programmer | **KẾT NỐI & PUSH GITHUB REPOSITORY THÀNH CÔNG:** Thiết lập `.gitignore` chuẩn, cấu hình remote `https://github.com/khoa025ne/roadguard-ai-engine.git`, commit 40 files sạch sẽ và push thành công nhánh `main` lên GitHub. | Git Remote, `.gitignore`, `main` branch | Repo trực tuyến 100% |
| **2026-09-23 00:27** | AI Pair Programmer | **THIẾT LẬP NHÁNH DEV & QUY CHUẨN GIT MỚI:** Tạo nhánh `dev` từ `main`, push lên `origin/dev`, tích hợp bộ quy tắc Branching 3 cấp độ và Conventional Commits tiếng Việt vào `.agents/rules/git_workflow.md` và `tiến độ.md`. | `.agents/rules/git_workflow.md`, `tiến độ.md`, branch `dev` | Sẵn sàng code trên dev |
| **2026-09-25 12:55** | AI Pair Programmer | **TẠO FEATURE HUẤN LUYỆN VẾT NỨT (GPU T4 COLAB):** Tạo nhánh `feature/train-crack-detection`, biên soạn notebook [train_crack_yolo11_colab.ipynb](file:///f:/train%20AI%20đồ%20án/notebooks/train_crack_yolo11_colab.ipynb), mở Google Chrome đúng profile `khoamap5544@gmail.com` và mở thư mục chứa notebook sẵn sàng nạp lên Colab. | `notebooks/train_crack_yolo11_colab.ipynb`, branch `feature/train-crack-detection` | Sẵn sàng bấm Run All |
| **2026-09-25 15:15** | AI Pair Programmer | **TÍCH HỢP & TEST THỰC NGHIỆM MODEL `crack_best.pt`:** Nhận file `crack_best.pt` vào `weights/trained/`, chạy phân tích video thực tế góc nhìn từ trên cao, phát hiện 19 ổ gà/vết nứt trong 7.07s, ước lượng bề rộng mm và xuất báo cáo CSDL + GIS đầy đủ. | `weights/trained/crack_best.pt`, `results/test_pothole_stock/` | Hoàn thành Task 2.3 |
| **2026-09-25 16:19** | AI Pair Programmer | **HỢP NHẤT & CHUẨN HÓA DATASET (4,340 ẢNH):** Viết `tools/merge_datasets.py`, tích hợp 3,940 ảnh ổ gà từ `archive.zip` với 400 mẫu âm tính (Negative samples) từ `surface-crack-detection.zip`. Tạo 400 file nhãn rỗng `.txt` chuẩn YOLO, xuất `data/unified_dataset` và đóng gói sẵn `unified_road_dataset.zip` (217MB) để đưa lên Colab. | `tools/merge_datasets.py`, `data/unified_dataset/`, `unified_road_dataset.zip` | Sẵn sàng Train V2 chống nhận nhầm |
| **2026-09-25 16:25** | AI Pair Programmer | **TỔNG HỢP TOÀN BỘ 100% (~44,000 ẢNH + 44,000 NHÃN TXT):** Viết `tools/build_full_44k_dataset.py`, tích hợp trọn vẹn 3,940 ảnh ổ gà (Class 0: pothole) + 20,000 ảnh vết nứt (Class 1: crack có BBox tự động) + 20,000 mẫu âm tính (nhãn rỗng). Phân bổ 35,345 Train / 6,397 Valid / 2,198 Test và đóng gói `unified_road_dataset_full.zip` (453MB). | `tools/build_full_44k_dataset.py`, `unified_road_dataset_full.zip` | Đạt chuẩn bộ dữ liệu lớn |
| **2026-09-27 22:15** | AI Pair Programmer | **TẠO DATASET 20K TỐI ƯU COLAB FREE:** Viết `tools/build_20k_dataset.py`, tạo bộ dữ liệu cân bằng ~20,000 ảnh gồm 3,940 pothole + 8,000 crack + 8,060 negative. Phân bổ 80/15/5, đóng gói `unified_road_dataset_20k.zip` (308.8 MB). Phù hợp GPU T4 Colab Free: ~45–70 phút / 50 epoch, batch=16, imgsz=640. | `tools/build_20k_dataset.py`, `data/unified_road_dataset_20k/` | Sẵn sàng train Colab Free |
| **2026-09-27 22:18** | AI Pair Programmer | **TẠO NOTEBOOK COLAB TRAIN 20K:** Viết `notebooks/train_roadguard_20k_yolo11_colab.ipynb` gồm 8 bước hoàn chỉnh: kiểm tra GPU, giải nén, trực quan hóa mẫu dataset, train YOLOv11n, vẽ biểu đồ kết quả, kiểm thử tập Test, xuất `roadguard_best_20k.pt` và sao lưu Drive. | `notebooks/train_roadguard_20k_yolo11_colab.ipynb` | Sẵn sàng mở Colab chạy |
| **2026-09-28 15:30** | AI Pair Programmer | **TÍCH HỢP TARGETBAND, IDEMPOTENCY & FASTAPI WORKER:** Triển khai hoàn chỉnh Task 3.4 (`TargetBandClassifier`, `ContextOverlapHandler`), Task 5.1/5.3 (Schema v1.1.0 & Mock Adapter đầy đủ trường `target_band`, `is_context_overlap`, `projected_station_m`), Task 5.2 (`IdempotencyManager` SHA256 & `ErrorClassifier` retry backoff), Task 5.4 (`FastAPI` Worker REST API, background processing, Webhook Callback). Vượt qua 10/10 automated unit test. | `src/inference/tiling_engine.py`, `src/contracts/`, `src/api/worker_service.py`, `tests/test_pipeline.py` | Sẵn sàng tích hợp Backend |
