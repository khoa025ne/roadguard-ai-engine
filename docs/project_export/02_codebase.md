# 02 — Cấu Trúc Thư Mục & Phân Tích Mã Nguồn (Codebase Map)

## 1. Cây Thư Mục Toàn Bộ Dự Án (Full Project Directory Tree)

```
f:\train AI đồ án\
├── .env.example                               # File mẫu cấu hình biến môi trường
├── requirements.txt                           # Danh sách thư viện phụ thuộc Python
├── run_ui.py                                  # Entry-point chính khởi chạy Web UI Server (port 8080)
├── pipeline.py                                # Pipeline xử lý video dòng lệnh CLI
├── process_raw_video.py                       # Script phân tích video thô độc lập
├── srt_gps_parser.py                          # Parser dữ liệu Telemetry DJI SRT độc lập
├── tiến độ.md                                 # Nhật ký theo dõi tiến độ dự án
│
├── configs/                                   # Các file cấu hình YAML cho dataset và huấn luyện
│   ├── crack_8classes.yaml                    # Cấu hình 8 lớp vết nứt chi tiết
│   ├── pothole_dataset.yaml                   # Cấu hình bộ dữ liệu ổ gà
│   └── road_crack_dataset.yaml                # Cấu hình bộ dữ liệu vết nứt
│
├── src/                                       # Thư mục mã nguồn cốt lõi (Core Modules)
│   ├── __init__.py
│   ├── api/                                   # Module API Backend & Worker Service
│   │   ├── __init__.py
│   │   ├── ui_server.py                       # FastAPI server chính (1,144 dòng) [CRITICAL]
│   │   └── worker_service.py                  # Background worker quản lý tiến trình phân tích (200 dòng)
│   │
│   ├── contracts/                             # Module định dạng dữ liệu & adapter
│   │   ├── __init__.py
│   │   ├── aidetection_schema.py              # Định dạng JSON Schema và GeoJSON chuẩn
│   │   ├── idempotency.py                     # Quản lý khóa chống lặp yêu cầu Idempotency
│   │   └── mock_ai_adapter.py                 # Adapter giả lập kết quả AI phục vụ unit test
│   │
│   ├── curation/                              # Module Thẩm định & Tinh tuyển dữ liệu (Stage 2 AI)
│   │   ├── __init__.py
│   │   ├── auto_tagger.py                     # Bộ phân loại chuyên sâu & gắn tag tự động (221 dòng)
│   │   ├── crack_analyzer.py                  # Module phân tích trắc diện & góc nghiêng vết nứt (223 dòng)
│   │   ├── dataset_exporter.py                # Module đóng gói dataset chuẩn YOLO (219 dòng)
│   │   ├── deduplicator.py                    # Thuật toán khử trùng lặp khuyết tật SSIM/IoU (217 dòng)
│   │   └── kdv_inspector.py                   # Giám khảo AI GPT-5.4 Vision Tầng 2 (868 dòng) [CRITICAL]
│   │
│   ├── inference/                             # Module Suy luận Local YOLOv11 (Stage 1 AI)
│   │   ├── __init__.py
│   │   ├── predictor.py                       # Wrapper dự đoán ảnh tile & frame đầy đủ (138 dòng)
│   │   └── tiling_engine.py                   # Bộ chia tile 640x640 & khôi phục BBox gốc (190 dòng)
│   │
│   ├── ingestion/                             # Module Tiếp nhận & Tiền xử lý dữ liệu
│   │   ├── __init__.py
│   │   ├── dataset_scanner.py                 # Quét và giải nén an toàn file ZIP / Folder (295 dòng)
│   │   ├── raw_video_analyzer.py              # Pipeline quét video thô & kiểm soát chất lượng (406 dòng)
│   │   ├── srt_parser.py                      # Telemetry Parser tính GSD & GPS Flycam (153 dòng)
│   │   └── video_extractor.py                 # Cắt khung hình từ video & đo độ nhòe (140 dòng)
│   │
│   ├── measurement/                           # Module Đo lường & Theo dõi Không gian
│   │   ├── __init__.py
│   │   ├── metric_estimator.py                # Ước tính kích thước thực tế (m, cm) từ GSD (79 dòng)
│   │   └── spatial_tracker.py                 # Theo dõi tọa độ vị trí Haversine (94 dòng)
│   │
│   └── training/                              # Module Huấn luyện nội bộ
│       ├── __init__.py
│       ├── train_crack.py                     # Script train model nứt
│       └── train_pothole.py                   # Script train model ổ gà
│
├── tools/                                     # Các công cụ hỗ trợ, benchmark và sinh Notebook
│   ├── benchmark_crack_v1.py                  # Benchmark độc lập model crack v1
│   ├── benchmark_curation_flow.py             # Benchmark hiệu năng 3 giai đoạn luồng Curation
│   ├── build_20k_dataset.py                   # Xây dựng bộ dữ liệu 15K/20K hợp nhất
│   ├── build_5k_pothole_dataset.py            # Đóng gói bộ dữ liệu 5,000 ảnh ổ gà Colab Free
│   ├── build_full_44k_dataset.py              # Xây dựng bộ dữ liệu đầy đủ 44K
│   ├── create_video_from_dataset.py           # Ghép video mp4 kiểm thử từ ảnh dataset
│   ├── eval_dataset_zip.py                    # CLI quét và đánh giá hiệu năng dataset ZIP
│   ├── extract_testcases_and_export_dataset.py # Trích xuất 7 tập Test Case MVP (336 dòng)
│   ├── generate_crack_notebook.py             # Sinh notebook huấn luyện vết nứt (504 dòng)
│   ├── generate_phase2_colab_notebook.py      # Sinh notebook nâng cấp Phase 2 Colab
│   ├── generate_pothole_5k_notebook.py        # Sinh notebook train ổ gà 5K Colab
│   ├── merge_datasets.py                      # Gộp các bộ dữ liệu Roboflow
│   ├── test_kdv.py / test_kdv_context.py      # Test tích hợp API KTV GPT-5.4
│   ├── test_model_web_e2e.py                  # Test End-to-End API Web UI
│   ├── test_roadguard_15k.py                  # Kiểm thử đánh giá bộ dữ liệu 15K
│   ├── train_phase2_local.py                  # Kịch bản train nâng cấp Phase 2 Local
│   ├── train_upgrade_model.py                 # Script Transfer Learning với Freeze Backbone
│   └── verify_and_pack_phase2_dataset.py      # Kiểm tra toàn vẹn & tạo file cấu hình YAML 15K
│
├── notebooks/                                 # Các Notebook Jupyter phục vụ Google Colab
│   ├── RoadGuard_Phase2_Upgrade_Colab.ipynb
│   ├── RoadGuard_Pothole_5K_Colab.ipynb
│   ├── train_crack_yolo11_colab.ipynb
│   ├── train_pothole_colab_kaggle.ipynb
│   └── train_roadguard_15k_yolo11_colab.ipynb
│
├── data/ [EXCLUDED CONTENT - Danh sách thư mục]
│   ├── curated_export/                        # Các lô dataset YOLO đã đóng gói
│   ├── mvp_test_cases/                        # 7 bộ test case tiêu chuẩn MVP
│   ├── pothole_dataset_5k/                    # Bộ dữ liệu 5,000 ảnh ổ gà
│   ├── unified_road_dataset_15k/              # Bộ dữ liệu 15,000 ảnh hợp nhất
│   ├── pothole_dataset_5k.zip (221 MB)
│   └── unified_road_dataset_15k.zip (292 MB)
│
└── weights/ [EXCLUDED CONTENT - Danh sách checkpoints]
    └── trained/
        ├── roadguard_crack_yolo11n_v1.pt (5.22 MB)
        ├── roadguard_best_15k.pt (5.22 MB)
        └── roadguard_pothole_best_5k.pt (5.22 MB)
```

---

## 2. Chi Tiết Các File Mã Nguồn Thuộc `src/` & Root

### 2.1. Server & Entry Point
- **`run_ui.py`** ([`run_ui.py:1-58`](file:///f:/train%20AI%20đồ%20án/run_ui.py#L1-L58)):
  - **Mục đích:** Khởi chạy server Uvicorn ASGI tại cổng `8080`, đảm bảo UTF-8 cho Windows console và tự động mở trình duyệt web.
  - **Function chính:** `main()` ([`run_ui.py:20`](file:///f:/train%20AI%20đồ%20án/run_ui.py#L20)) — Cấu hình host `127.0.0.1`, port `8080`, nạp ứng dụng `src.api.ui_server:app`.

### 2.2. Module Local Inference (Stage 1 AI)
- **`src/inference/predictor.py`** ([`src/inference/predictor.py:15-138`](file:///f:/train%20AI%20đồ%20án/src/inference/predictor.py#L15-L138)):
  - **Mục đích:** Wrapper nạp mô hình YOLOv11 qua Ultralytics, thực hiện suy luận trên từng tile 640x640 hoặc frame toàn cảnh.
  - **Class chính:** `RoadDefectPredictor` ([`src/inference/predictor.py:15`](file:///f:/train%20AI%20đồ%20án/src/inference/predictor.py#L15))
    - `__init__(model_path, conf_threshold)` ([`src/inference/predictor.py:41`](file:///f:/train%20AI%20đồ%20án/src/inference/predictor.py#L41)): Nạp file trọng số `.pt` và thiết lập ngưỡng confidence.
    - `predict_tile(tile)` ([`src/inference/predictor.py:50`](file:///f:/train%20AI%20đồ%20án/src/inference/predictor.py#L50)): Chạy suy luận 1 tile 640x640 BGR, trả về danh sách BBox `[x1, y1, x2, y2, conf, cls_id]`.
    - `predict_full_frame(frame)` ([`src/inference/predictor.py:82`](file:///f:/train%20AI%20đồ%20án/src/inference/predictor.py#L82)): Kết hợp `TileSplitter` để chia nhỏ frame 2.7K/4K, dự đoán từng tile và gộp BBox khôi phục tọa độ gốc.

- **`src/inference/tiling_engine.py`** ([`src/inference/tiling_engine.py:12-190`](file:///f:/train%20AI%20đồ%20án/src/inference/tiling_engine.py#L12-L190)):
  - **Mục đích:** Cắt nhỏ khung hình độ phân giải cao thành các tile 640x640 có độ chồng lấp (stride overlap) và hợp nhất BBox bằng thuật toán NMS.
  - **Class chính:**
    - `TileSplitter(tile_size=640, overlap=0.2)` ([`src/inference/tiling_engine.py:12`](file:///f:/train%20AI%20đồ%20án/src/inference/tiling_engine.py#L12)): Cắt ảnh và khôi phục BBox.
    - `TargetBandClassifier` ([`src/inference/tiling_engine.py:113`](file:///f:/train%20AI%20đồ%20án/src/inference/tiling_engine.py#L113)): Xác định dải di chuyển của Flycam.

### 2.3. Module Curation & KTV AI (Stage 2 AI)
- **`src/curation/auto_tagger.py`** ([`src/curation/auto_tagger.py:21-221`](file:///f:/train%20AI%20đồ%20án/src/curation/auto_tagger.py#L21-L221)):
  - **Mục đích:** Bộ thẩm định chuyên sâu 2 Tầng. Thẩm định ảnh cận cảnh (Crop), phát hiện báo động giả (bóng râm/lóa sáng) qua trắc diện hình ảnh hoặc gọi KTV GPT-5.4 Vision.
  - **Class chính:** `AIAutoTagger` ([`src/curation/auto_tagger.py:21`](file:///f:/train%20AI%20đồ%20án/src/curation/auto_tagger.py#L21))
    - `analyze_crop(crop_path, base_class, confidence)` ([`src/curation/auto_tagger.py:53`](file:///f:/train%20AI%20đồ%20án/src/curation/auto_tagger.py#L53)): Phân tích ảnh crop, trả về `is_valid`, `fine_tag`, `severity`, `status`.

- **`src/curation/crack_analyzer.py`** ([`src/curation/crack_analyzer.py:66-223`](file:///f:/train%20AI%20đồ%20án/src/curation/crack_analyzer.py#L66-L223)):
  - **Mục đích:** Module toán học phân tích hình thái vết nứt (ngang, dọc, chân chim, mép đường), ước lượng bề rộng nứt mm (`hairline`, `medium`, `severe`) và góc nghiêng chủ đạo.
  - **Class chính:** `CrackAnalyzer` ([`src/curation/crack_analyzer.py:66`](file:///f:/train%20AI%20đồ%20án/src/curation/crack_analyzer.py#L66))
    - `analyze_crop_image(img, confidence)` ([`src/curation/crack_analyzer.py:70`](file:///f:/train%20AI%20đồ%20án/src/curation/crack_analyzer.py#L70)): Dùng ma trận Canny & Hough Lines phân tích đường nứt.

- **`src/curation/deduplicator.py`** ([`src/curation/deduplicator.py:22-217`](file:///f:/train%20AI%20đồ%20án/src/curation/deduplicator.py#L22-L217)):
  - **Mục đích:** Thuật toán khử trùng lặp khuyết tật trùng vết nứt qua nhiều frame video dựa trên khoảng cách tọa độ GPS Haversine, trùng lấp IoU và độ tương đồng hình ảnh SSIM.
  - **Class chính:** `DefectDeduplicator` ([`src/curation/deduplicator.py:22`](file:///f:/train%20AI%20đồ%20án/src/curation/deduplicator.py#L22))
    - `deduplicate(items)` ([`src/curation/deduplicator.py:134`](file:///f:/train%20AI%20đồ%20án/src/curation/deduplicator.py#L134)): Gom nhóm khuyết tật trùng lặp, đánh dấu `is_duplicate: True`.

- **`src/curation/dataset_exporter.py`** ([`src/curation/dataset_exporter.py:21-219`](file:///f:/train%20AI%20đồ%20án/src/curation/dataset_exporter.py#L21-L219)):
  - **Mục đích:** Đóng gói các khuyết tật đã thẩm định thành dataset YOLO chuẩn (`train/images`, `train/labels`, `val/images`, `val/labels`, `data.yaml`) và nén tệp `.zip`.
  - **Class chính:** `DatasetExporter` ([`src/curation/dataset_exporter.py:21`](file:///f:/train%20AI%20đồ%20án/src/curation/dataset_exporter.py#L21))
    - `export_yolo_dataset(curated_items, frames_lookup, export_name)` ([`src/curation/dataset_exporter.py:28`](file:///f:/train%20AI%20đồ%20án/src/curation/dataset_exporter.py#L28)): Chuẩn hóa tọa độ $xywh$ về $[0.0, 1.0]$, phân luồng 80/20 train/val.

### 2.4. Trích Mã Nguồn Critical từ `src/curation/kdv_inspector.py` (> 300 dòng)
File [`src/curation/kdv_inspector.py`](file:///f:/train%20AI%20đồ%20án/src/curation/kdv_inspector.py) dài **868 dòng**, chứa toàn bộ logic tương tác với GPT-5.4 Vision Tầng 2:

```python
# Trích nguyên văn đoạn nạp biến môi trường & tạo OpenAI Client (src/curation/kdv_inspector.py:71-100)
class KDVInspector:
    """Giám khảo AI Tầng 2 — Thẩm định khuyết tật đường qua Multimodal Vision (gpt-5.4)."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        env_config = _load_env_if_exists()
        self.api_key = api_key or env_config.get("KDV_API_KEY") or os.environ.get("KDV_API_KEY")
        self.base_url = base_url or env_config.get("KDV_BASE_URL") or os.environ.get("KDV_BASE_URL", "https://api.xah.io/v1")
        self.model_name = model or env_config.get("KDV_MODEL") or os.environ.get("KDV_MODEL", "gpt-5.4")

        self.client = None
        if self.api_key:
            self._init_client()

    def _init_client(self):
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        except Exception:
            self.client = None
```

```python
# Trích nguyên văn đoạn Dual-View Context Prompt & chế độ thẩm định toàn cảnh (src/curation/kdv_inspector.py:270-305)
    def inspect_with_context(
        self,
        overview_image: Any,
        defect_items: List[Dict[str, Any]],
        road_metadata: Optional[Dict[str, Any]] = None,
        batch_size: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Thẩm định khuyết tật với chế độ DUAL-VIEW CONTEXT:
        Đọc ảnh Khung hình Tổng thể (Overview Frame) bao quát tuyến đường kết hợp ảnh cắt cận cảnh phóng to.
        """
        if not self.is_available:
            return self._heuristic_fallback_batch(defect_items)

        # Tạo ảnh Mosaic ghép Overview và các BBox phóng to
        mosaic_b64, item_map = self._create_mosaic_grid(overview_image, defect_items)
        # Gửi request API multimodal tới gpt-5.4
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[...],
            temperature=0.2,
            max_tokens=2000
        )
```

### 2.5. Trích Mã Nguồn Critical từ `src/ingestion/raw_video_analyzer.py` (> 300 dòng)
File [`src/ingestion/raw_video_analyzer.py`](file:///f:/train%20AI%20đồ%20án/src/ingestion/raw_video_analyzer.py) dài **406 dòng**, là pipeline phân tích video thô:

```python
# Trích nguyên văn đoạn Quality Gate & Tính toán GPS thực địa (src/ingestion/raw_video_analyzer.py:64-90)
    def run_quality_gate(self, video_path: Path | str) -> Dict[str, Any]:
        """Kiểm tra chất lượng video trước khi đưa vào pipeline xử lý."""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return {"passed": False, "reason": "Không thể mở file video"}

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        passed = (width >= 1280 and height >= 720 and total_frames >= 10)
        return {
            "passed": passed,
            "resolution": f"{width}x{height}",
            "fps": fps,
            "total_frames": total_frames
        }
```
