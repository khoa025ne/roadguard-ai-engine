# 📋 CrackScan VN — Master Project Document
> **File này là nguồn sự thật duy nhất (Single Source of Truth) của toàn bộ dự án.**
> **⚠️ BẮT BUỘC:** Mọi AI Agent / Developer trước và sau mỗi session phải đọc và cập nhật [tiến độ.md](file:///f:/train%20AI%20đồ%20án/tiến%20độ.md) và bám sát kế hoạch chi tiết tại [ke_hoach_thuc_thi_AI.md](file:///f:/train%20AI%20đồ%20án/ke_hoach_thuc_thi_AI.md).

---

## 🔖 Metadata Dự Án

| Trường | Giá Trị |
|---|---|
| **Tên dự án** | RoadGuard / CrackScan VN |
| **Mô tả** | AI phát hiện & phân tích khuyết tật cầu đường nông thôn bằng Flycam |
| **Phiên bản** | v1.0.0 (Đồng bộ RoadGuard Specs) |
| **Ngày tạo** | 2026-09-15 |
| **Cập nhật lần cuối** | 2026-09-22 |
| **Developer** | Solo AI/ML Developer & AI Pair Agent |
| **Tài liệu nghiệp vụ** | `c:\Users\ADMIN\Downloads\diagram\` |
| **Kế hoạch AI chi tiết**| [ke_hoach_thuc_thi_AI.md](file:///f:/train%20AI%20đồ%20án/ke_hoach_thuc_thi_AI.md) |
| **Bảng theo dõi tiến độ**| [tiến độ.md](file:///f:/train%20AI%20đồ%20án/tiến%20độ.md) |
| **Timeline** | < 1 tháng (demo khẩn) |
| **Khu vực** | Cầu & đường bê-tông nông thôn, miền Nam Việt Nam |

---

## 🎯 Mục Tiêu Cốt Lõi

### Primary Goal
> Xây dựng hệ thống AI tự động phát hiện, phân loại và đo lường vết nứt trên cầu đường nông thôn từ video Flycam, xuất kết quả dưới dạng báo cáo kèm toạ độ GPS.

### Success Criteria (Demo)
- [ ] Detect ít nhất **4/8 loại** hư hỏng với confidence > 0.50
- [ ] mAP50 > **0.55** trên validation set crack
- [ ] Xử lý 1 video 5 phút trong < **5 phút**
- [ ] Xuất JSON report kèm GPS coordinates
- [ ] Demo chạy được end-to-end từ video → kết quả

### Success Criteria (Production)
- [ ] mAP50 > **0.75** trên 8 class
- [ ] Width estimation error ± 2mm tại độ cao 10m
- [ ] GPS accuracy ± 5m (giới hạn DJI Mini 2 SE)
- [ ] PDF report tự động
- [ ] Dashboard web với Leaflet.js map

---

## 🏗️ Kiến Trúc Hệ Thống (Hiện Tại)

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT                                                       │
│  [Video .MP4 từ DJI Mini 2 SE] + [File .SRT GPS]           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: VIDEO PROCESSING  [hadle_vid.py]                  │
│  ├── Frame sampling: mỗi 15 frame → 2fps từ 30fps          │
│  ├── Blur detection: Laplacian variance < 100 → skip       │
│  ├── GPS sync: frame_id ↔ SRT timestamp                    │
│  └── Tile split: 2720×1530 → tiles 640×640 (overlap 20%)  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2: GPS PROCESSING  [srt_gps_parser.py]               │
│  ├── Parse DJI SRT format: lat/lon/rel_alt mỗi 33ms        │
│  ├── Tính GSD realtime: f(altitude, sensor, focal)         │
│  └── Export: JSON + GeoJSON                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3: AI INFERENCE  [trainAI_watch_img.py]              │
│  ├── Model: YOLOv11n (fine-tuned từ COCO weights)          │
│  ├── Tile inference + NMS merge                             │
│  ├── GSD-based measurement: width/length mm                 │
│  └── Severity classification: L1/L2/L3                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 4: OUTPUT  [TODO]                                    │
│  ├── JSON report: {crack_id, class, severity, gps, size}   │
│  ├── GeoJSON: cho Leaflet.js map                           │
│  └── PDF report: WeasyPrint (TODO)                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Hardware & Environment

| Thành phần | Chi tiết | Trạng thái |
|---|---|---|
| **Flycam** | DJI Mini 2 SE | ✅ Xác nhận |
| **Sensor** | 1/2.3" CMOS, 12MP | ✅ |
| **Video** | 2.7K (2720×1530) @ 30fps | ✅ |
| **Focal Length** | 24mm equiv (actual ~4.26mm) | ✅ |
| **GPS** | File `.SRT` sidecar (tách rời) | ✅ Có sẵn |
| **GPU (train)** | Kaggle T4 (free 30h/tuần) | ⏳ Cần setup |
| **Runtime** | Python 3.12.10 | ✅ |
| **OS** | Windows | ✅ |
| **Deploy** | Railway Hobby ($5/tháng) | ⏳ Chưa setup |

### GSD Reference Table (DJI Mini 2 SE)
| Độ cao | GSD (mm/px) | Crack nhỏ nhất detect | Khuyến nghị |
|---|---|---|---|
| 5m | 0.71 | ~2mm | ✅ Tốt nhất |
| 10m | 1.43 | ~5mm | ✅ Đủ dùng |
| 15m | 2.14 | ~7mm | ⚠️ Giới hạn |
| 20m | 2.86 | ~9mm | ⚠️ Chỉ crack lớn |
| 30m | 4.29 | ~13mm | ❌ Không phù hợp |

> **⚠️ RÀNG BUỘC BAY:** Người điều khiển PHẢI bay ở 5–15m để detect vết nứt. Bay > 20m chỉ thấy ổ gà.

---

## 📦 Trạng Thái Model AI

### `best.pt` — Thực Trạng Đã Xác Nhận
```
Architecture : YOLOv11n  (yolo11n.yaml)
Trained on   : COCO dataset (80 class — người, xe, động vật...)
Epochs       : 600 (Ultralytics official training)
mAP50 COCO   : 55.14%
mAP50-95     : 39.39%
File size    : 5.35 MB
Date         : 2024-09-25

⚠️ CHƯA CÓ bất kỳ class nào về vết nứt / ổ gà!
✅ SẼ DÙNG LÀM: Pretrained weights cho fine-tune (transfer learning)
```

### Target Model (Sau Fine-tune)
```
Architecture : YOLOv11n-seg (thêm segmentation head)
Classes      : 8 class (crack + pothole)
Training     : fine-tune từ best.pt
Dataset      : ~800-1200 ảnh tổng hợp
Target mAP50 : > 0.65
```

### 8 Classes Mục Tiêu
| ID | Class | Tiếng Việt | Mức Độ Ưu Tiên |
|---|---|---|---|
| 0 | `pothole` | Ổ gà | 🔴 Cao |
| 1 | `longitudinal` | Nứt dọc | 🟡 Trung bình |
| 2 | `transverse` | Nứt ngang | 🟡 Trung bình |
| 3 | `alligator` | Nứt chân chim | 🔴 Cao |
| 4 | `edge_crack` | Nứt mép đường | 🟠 |
| 5 | `block_crack` | Nứt ô | 🟡 |
| 6 | `spalling` | Bong tróc bê-tông | 🔴 Cao |
| 7 | `raveling` | Tróc hạt mặt đường | 🟢 Thấp |

---

## 📁 Cấu Trúc File Dự Án

```
f:\train AI đồ án\
│
├── 📄 antigravity_prompt.md      ← FILE NÀY — Master document (luôn cập nhật)
├── 🤖 best.pt                    ← YOLOv11n COCO pretrained (base weights)
│
├── 🐍 srt_gps_parser.py          ← Parse DJI .SRT → GPS JSON + GSD calc
├── 🐍 hadle_vid.py               ← Video → frames + blur filter + tile split
├── 🐍 trainAI_watch_img.py       ← Inference viewer + GSD measurement
├── 🐍 train_crack_model.py       ← Fine-tune YOLOv11n với crack dataset
│
├── 📄 requirements.txt           ← Python dependencies
│
├── 📂 crack_dataset/             ← [CHƯA TẠO] Dataset sau khi label
│   ├── images/train/
│   ├── images/val/
│   ├── labels/train/
│   └── labels/val/
├── 📄 crack_dataset.yaml         ← [CHƯA TẠO] Dataset config YOLO
│
├── 📂 frames/                    ← [CHƯA TẠO] Output của hadle_vid.py
├── 📂 results/                   ← [CHƯA TẠO] Output inference
└── 📂 runs/crack_detection/      ← [CHƯA TẠO] Training output (YOLO default)
```

---

## 📊 Tiến Độ Thực Hiện

### ✅ Đã Hoàn Thành (Session 01 — 2026-09-15)

- [x] **Phân tích yêu cầu** — Elicit requirements qua Q&A 3 vòng
- [x] **Xác định phạm vi** — Crack & pothole trên cầu/đường nông thôn miền Nam VN
- [x] **Hardware profiling** — DJI Mini 2 SE specs, GSD table đầy đủ
- [x] **Model audit** — Phát hiện `best.pt` là COCO 80-class, không phải pothole model
- [x] **Thiết kế kiến trúc** — 4-layer pipeline (Video → GPS → AI → Output)
- [x] **Cài đặt môi trường** — Python 3.12, ultralytics 8.4.152, torch 2.14.0, opencv 5.0.0
- [x] **`srt_gps_parser.py`** — DJI SRT parser, GSD realtime, JSON/GeoJSON export
- [x] **`hadle_vid.py`** — Frame extractor, blur filter, tile splitter, GPS sync
- [x] **`trainAI_watch_img.py`** — Inference viewer, GSD measurement, severity classify
- [x] **`train_crack_model.py`** — Fine-tune script với hyperparameters tối ưu aerial
- [x] **`requirements.txt`** — Dependencies đầy đủ

### ⏳ Đang Làm / Bước Tiếp Theo

- [x] **[NGAY]** Xử lý dataset Pothole từ `archive.zip` (3,940 ảnh: 3345 train, 397 valid, 198 test)
- [x] Tạo `pothole_dataset.yaml` & `train_pothole_model.py` phục vụ xuất model riêng
- [x] Tạo `train_pothole_colab_kaggle.ipynb` sẵn sàng train GPU T4 miễn phí
- [ ] Huấn luyện xuất file `pothole_best.pt`
- [ ] Thu thập bổ sung các class nứt khác (CRACK500, RDD2022) nếu mở rộng 8 class
- [ ] Integration test: video → JSON report đầy đủ
- [ ] **[TUẦN 4]** Demo UI (Streamlit/Gradio) + deploy Railway

### ❌ Chưa Làm

- [ ] ByteTrack integration (dedup detections across frames)
- [ ] PDF report generator (WeasyPrint)
- [ ] Leaflet.js map dashboard
- [ ] FastAPI backend endpoints
- [ ] End-to-end pipeline runner script
- [ ] GPS stitching / orthophoto
- [ ] Severity scoring system (rule-based)

---

## ⚠️ Ràng Buộc Kỹ Thuật (Constraints)

> **Những ràng buộc này là BẤT BIẾN — không được bỏ qua khi thiết kế bất kỳ module nào.**

### C01 — GSD & Độ Cao Bay (CRITICAL)
```
MỖI module xử lý ảnh PHẢI nhận altitude_m làm input.
GSD = (altitude_m × 1000 × 6.17mm) / (4.26mm × 2720px)
Bay > 20m → CẢNH BÁO người dùng về giới hạn detection.
```

### C02 — Input Format (FIXED)
```
Video    : MP4, H.264, 2720×1530, 30fps (DJI Mini 2 SE standard)
GPS      : File .SRT sidecar, cùng tên với video, format DJI standard
Model    : YOLO format (.pt), ultralytics >= 8.3.0
```

### C03 — Class Schema (FIXED — không thay đổi thứ tự ID)
```
Khi fine-tune, PHẢI giữ nguyên class ID 0-7 như bảng trên.
Thêm class mới → append ID 8, 9... KHÔNG được reorder.
Lý do: các module downstream hardcode class ID → severity mapping.
```

### C04 — Frame Sampling (ADJUSTABLE)
```
Default: mỗi 15 frame (= 2fps từ video 30fps)
Min: 5 frame (= 6fps) — chỉ khi cần độ phủ cao
Max: 30 frame (= 1fps) — khi video rất dài
Blur threshold default: 100 (Laplacian variance)
```

### C05 — Tile Strategy (FIXED)
```
Tile size : 640×640 px (YOLO standard)
Overlap   : 20% (128px) — bắt buộc để tránh miss detection ở rìa tile
NMS IoU   : 0.45 (merge duplicate boxes từ overlap region)
```

### C06 — Output Schema (FIXED — API contract)
```json
{
  "job_id": "string",
  "video_path": "string",
  "processed_at": "ISO8601",
  "drone": "DJI Mini 2 SE",
  "gsd_avg_mm_per_px": "float",
  "cracks": [
    {
      "track_id": "int",
      "class_id": "int (0-7)",
      "class_name": "string",
      "severity": "L1|L2|L3",
      "confidence": "float",
      "gps": {"lat": "float", "lon": "float"},
      "altitude_m": "float",
      "gsd_mm_per_px": "float",
      "width_mm": "float",
      "length_mm": "float",
      "best_frame": "string (filename)"
    }
  ],
  "summary": {
    "total_cracks": "int",
    "by_class": {},
    "by_severity": {"L1": "int", "L2": "int", "L3": "int"},
    "damage_area_pct": "float"
  }
}
```

### C07 — Severity Rules (BUSINESS LOGIC — có thể điều chỉnh)
```
L1 (Nhẹ)          : width < 2mm  OR class = raveling
L2 (Trung bình)   : 2mm ≤ width < 5mm  OR class ∈ {longitudinal, transverse, block_crack}
L3 (Nghiêm trọng) : width ≥ 5mm  OR class ∈ {pothole, alligator, spalling}
```

### C08 — Infrastructure (COST CONSTRAINT)
```
Training  : Kaggle Notebook GPU T4 (FREE — 30h/tuần)
Inference : Hugging Face Spaces hoặc local GPU
Backend   : Railway Hobby ($5/tháng) — CHỈ API gateway, KHÔNG inference
Storage   : Cloudinary free (25GB) + Supabase PostgreSQL free (500MB)
```

### C09 — Dataset Quality Gate
```
Trước khi training, dataset PHẢI đạt:
  - Tối thiểu 80 ảnh/class (640 ảnh total minimum)
  - Train/Val split: 80/20
  - Annotation: polygon (không phải bbox đơn thuần) cho 6 class crack
  - Bbox chấp nhận được cho pothole và spalling
  - Không được có ảnh trùng giữa train và val set
```

### C10 — GPS Accuracy Disclaimer
```
DJI Mini 2 SE GPS accuracy: ±1.5m (GNSS, không RTK)
Mọi output GPS PHẢI kèm theo field: "gps_accuracy_m": 1.5
Không được claim độ chính xác cao hơn thực tế trong demo/report.
```

---

## 🔄 Changelog

### Session 01 — 2026-09-15
**Người thực hiện:** Antigravity AI  
**Thời gian:** ~15:25 → 15:38 ICT

**Đã làm:**
- Elicit toàn bộ yêu cầu qua 3 vòng Q&A chi tiết
- Phát hiện: `best.pt` là YOLOv11n COCO (80 class), chưa train về crack
- Xác nhận hardware: DJI Mini 2 SE, SRT GPS file có sẵn
- Tính toán và ghi lại GSD table cho tất cả độ cao
- Cài đặt môi trường: ultralytics 8.4.152, torch 2.14.0, opencv 5.0.0
- Tạo 4 scripts Python core: parser, video, inference, training
- Thiết kế output JSON schema (C06)
- Xác định 10 ràng buộc kỹ thuật (C01–C10)

**Phát hiện quan trọng:**
- ⚠️ Bay > 20m: vết nứt nhỏ < 9mm sẽ không detect được
- ⚠️ FFmpeg chưa cài trên máy — scripts dùng OpenCV thay thế
- ⚠️ Cần label lại toàn bộ dataset với polygon annotation

**Quyết định kỹ thuật:**
- Giữ YOLOv11n (không nâng lên medium/large) vì demo < 1 tháng
- Dùng detection head trước (không seg) để nhanh có kết quả baseline
- Training trên Kaggle GPU (free) thay vì local

**Bước tiếp theo session sau:**
1. Cung cấp ảnh test từ Flycam để kiểm tra pipeline
2. Bắt đầu thu thập/label dataset trên Roboflow
3. Setup Kaggle Notebook cho training

---

## 🔐 Quy Tắc Cập Nhật File Này

> **AI PHẢI tuân theo các quy tắc sau khi làm việc trên dự án này:**

### Khi nào PHẢI cập nhật
| Sự kiện | Phần cần cập nhật |
|---|---|
| Thêm file/script mới | `📁 Cấu Trúc File`, `✅ Đã Hoàn Thành` |
| Thay đổi class schema | `C03`, bảng `8 Classes Mục Tiêu` |
| Thay đổi output JSON | `C06` |
| Thay đổi business logic | `C07` (Severity Rules) |
| Train model mới | `📦 Trạng Thái Model AI`, `Changelog` |
| Thay đổi kiến trúc | `🏗️ Kiến Trúc Hệ Thống` |
| Kết thúc mỗi session | `Changelog`, `⏳ Đang Làm`, phiên bản |
| Phát hiện bug/issue quan trọng | Thêm vào `Changelog` |

### Format Changelog Entry
```markdown
### Session XX — YYYY-MM-DD
**Người thực hiện:** [tên]
**Thời gian:** HH:MM → HH:MM ICT

**Đã làm:**
- [bullet points]

**Phát hiện quan trọng:**
- [discoveries, gotchas]

**Quyết định kỹ thuật:**
- [design decisions với lý do]

**Bước tiếp theo session sau:**
1. [numbered list]
```

### Quy tắc phiên bản
```
v0.X.Y
  X = Major milestone (0=Setup, 1=Training, 2=Pipeline, 3=Deploy)
  Y = Số session trong milestone đó

Hiện tại: v0.2.0 (Setup milestone, session 2)
```

---

*📌 File này được tạo và quản lý bởi Antigravity AI. Cập nhật lần cuối: 2026-09-15T15:38 ICT.*
