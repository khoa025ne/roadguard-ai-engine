# Bố Cục Thư Mục Dự Án RoadGuard AI Engine (Folder Layout)
> Phiên bản chuẩn hóa sau đợt tái cấu trúc Kiến Trúc A (Linear Pipeline v2.0).

---

## 1. Sơ đồ cấu trúc tổng thể

```
roadguard-ai-engine/
├── configs/                        # Cấu hình hệ thống & tham số pipeline
│   ├── pipeline.yaml               # Cấu hình tập trung 7 stages của Pipeline Tuyến Tính
│   ├── crack_8classes.yaml         # Config dataset huấn luyện 8 lớp nứt
│   └── road_crack_dataset.yaml     # Config dataset nhận diện vết nứt Roboflow
├── data/                           # Dữ liệu khảo sát & Dataset huấn luyện (Bảo vệ)
│   ├── raw_videos/                 # Video flycam gốc duy nhất (DJI_0057, 0059, 0061, 0064)
│   ├── road_crack/                 # Junction trỏ vào dataset vết nứt
│   ├── unified_road_dataset_15k/   # Dataset hợp nhất 15k ảnh
│   ├── pothole_dataset_5k/         # Dataset ổ gà 5k ảnh
│   └── curated_export/             # Dataset do module AI Curation xuất xưởng
├── docs/                           # Tài liệu kỹ thuật, đặc tả kiến trúc & quy trình
│   ├── PIPELINE.md                 # Đặc tả chi tiết 7 Stages của Kiến Trúc A
│   ├── FOLDER_LAYOUT.md            # Bản đồ bố cục thư mục chuẩn
│   ├── RETENTION.md                # Quy chuẩn lưu trữ & dọn dẹp task định kỳ
│   └── specs/                      # Đặc tả hợp đồng dữ liệu & User Stories
├── notebooks/                      # Google Colab & Jupyter Notebooks huấn luyện
├── outputs/                        # Thư mục chứa kết quả xuất xưởng (Ignored by Git)
│   ├── reports/                    # Báo cáo inspection_report.json & GeoJSON
│   ├── predicts/                   # Ảnh dự đoán & Bounding Box
│   └── runs/                       # Log & checkpoint thử nghiệm nội bộ
├── results/                        # Dữ liệu chạy giao diện Web UI (Web Bench)
│   ├── web_runs/                   # Kết quả phân tích các task trên Web UI
│   └── web_uploads/                # File tải lên tạm thời từ trình duyệt
├── src/                            # Mã nguồn ứng dụng RoadGuard AI Engine
│   ├── api/                        # Dịch vụ Web UI Server & Async Worker API
│   │   ├── ui_server.py            # FastAPI Web Test Bench
│   │   ├── worker_service.py       # Worker tích hợp Backend ASP.NET Core
│   │   └── web/index.html          # Giao diện kiểm thử trực quan
│   ├── contracts/                  # Schema bất biến & Idempotency
│   │   ├── aidetection_schema.py   # Chuẩn dữ liệu bảng AIDetection
│   │   ├── idempotency.py          # Khóa chống trùng lặp SHA256
│   │   └── mock_ai_adapter.py      # Adapter giả lập cho Backend nghiệm thu sớm
│   ├── curation/                   # Hệ thống tinh tuyển dữ liệu AI-Assisted Curation
│   │   ├── auto_tagger.py          # Bộ phân loại & gắn tag tự động
│   │   ├── crack_analyzer.py       # Phân tích hình thái nứt chuyên sâu
│   │   ├── deduplicator.py         # Khử trùng lặp đa khung hình & tiling
│   │   ├── kdv_inspector.py        # KTV AI Multimodal thẩm định khuyết tật
│   │   └── dataset_exporter.py     # Đóng gói dataset chuẩn YOLO theo class_map.json
│   ├── inference/                  # Động cơ nhận diện mô hình AI
│   │   ├── predictor.py            # Bộ suy luận YOLOv11 & tự nạp class_map.json
│   │   └── tiling_engine.py        # Cắt mảnh 640x640 có gối đầu & Cross-Tile NMS
│   ├── ingestion/                  # Tiếp nhận & tiền xử lý video viễn thám
│   │   ├── srt_parser.py           # Bóc tách phụ đề DJI SRT & tính GSD
│   │   ├── video_extractor.py      # Trích xuất khung hình chuẩn
│   │   └── dataset_scanner.py      # Quét dataset phục vụ Web UI
│   ├── measurement/                # Đo đạc kích thước thực tế & không gian
│   │   ├── metric_estimator.py     # Ước lượng chiều dài, chiều rộng, Severity
│   │   └── spatial_tracker.py      # Theo dõi không gian
│   ├── pipeline/                   # Kiến Trúc A: Linear Pipeline
│   │   ├── pipeline.py             # Điều phối tuần tự & hàm API run_video_analysis_task
│   │   └── stages/                 # 7 giai đoạn tuyến tính (1 file = 1 stage)
│   │       ├── 01_segment.py       # Tách nền & tạo mask mặt đường
│   │       ├── 02_detect.py        # YOLO object detection
│   │       ├── 03_filter.py        # Lọc theo mask, diện tích & target band
│   │       ├── 04_dedup.py         # Khử trùng lặp đa khung hình & tiling
│   │       ├── 05_measure.py       # Đo đạc 2D, GSD, Severity & WGS84
│   │       ├── 06_inspect.py       # Thẩm định KTV & lọc báo động giả
│   │       └── 07_report.py        # Xuất báo cáo JSON, GeoJSON, crops
│   └── utils/                      # Tiện ích bổ trợ (I/O UTF-8, Georeferencing)
│       ├── io.py                   # safe_imwrite, safe_imread
│       └── geo.py                  # calculate_defect_ground_coords WGS84
├── tests/                          # Bộ kiểm thử tự động UnitTest
├── tools/                          # Các script công cụ bổ trợ
│   ├── cleanup_tasks.py            # Công cụ dọn dẹp task định kỳ theo RETENTION
│   ├── remap_merge.py              # Hợp nhất dataset chuẩn hóa taxonomy
│   └── ...                         # Scripts đóng gói notebook & benchmark
├── weights/                        # Trọng số mô hình AI
│   └── trained/                    # 3 bản weights tốt nhất được bảo vệ
│       ├── roadguard_best_15k.pt
│       ├── roadguard_crack_yolo11n_v1.pt
│       └── roadguard_pothole_best_5k.pt
├── class_map.json                  # Taxonomy ánh xạ Class ID tập trung
├── pipeline.py                     # Master CLI Runner kết nối Kiến Trúc A
├── run_ui.py                       # Điểm khởi chạy Web UI Test Bench
└── .gitignore                      # Chặn rác và dữ liệu lớn
```
