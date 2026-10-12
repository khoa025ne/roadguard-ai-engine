# 06 — Cấu Hình Hệ Thống, Hằng Số Ngưỡng & Biến Môi Trường (Config & Thresholds)

## 1. Biến Môi Trường Bắt Buộc (Environment Variables)

Hệ thống nạp các biến môi trường từ tệp `.env` (tham chiếu mẫu [`.env.example:1-6`](file:///f:/train%20AI%20đồ%20án/.env.example#L1-L6) và mã nguồn [`src/curation/kdv_inspector.py:71-85`](file:///f:/train%20AI%20đồ%20án/src/curation/kdv_inspector.py#L71-L85)):

| Tên Biến Môi Trường | Mô Tả Chức Năng | Giá Trị Mẫu / Default | Bắt Buộc? |
| :--- | :--- | :--- | :---: |
| `KDV_API_KEY` | API Key xác thực kết nối đến KTV GPT-5.4 Vision Tầng 2 | `sk-proj-...` | Cần khi bật KTV Tầng 2 |
| `KDV_BASE_URL` | Endpoint URL cổng API Gateway | `https://api.xah.io/v1` | Không (có default) |
| `KDV_MODEL` | Tên mô hình Multimodal Vision xử lý bối cảnh | `gpt-5.4` | Không (có default) |

> ⚠️ **Quy tắc bảo mật:** Không lưu API Key trực tiếp vào git. Tạo file `.env` cá nhân tại thư mục gốc dự án.

---

## 2. Hằng Số Ngưỡng Toán Học & Xử Lý Ảnh (Threshold Constants)

### 2.1. Ngưỡng Inference & NMS (Stage 1 YOLO Scanner)
- **`CONF_THRESHOLD = 0.25`** ([`src/inference/predictor.py:41`](file:///f:/train%20AI%20đồ%20án/src/inference/predictor.py#L41)): Ngưỡng tin cậy tối thiểu để nhận diện khuyết tật.
- **`IOU_THRESHOLD = 0.45`** ([`src/inference/tiling_engine.py:60`](file:///f:/train%20AI%20đồ%20án/src/inference/tiling_engine.py#L60)): Ngưỡng giao nhau NMS (Non-Maximum Suppression) khi gộp BBox tile 640x640.
- **`TILE_SIZE = 640`** & **`OVERLAP = 0.20`** ([`src/inference/tiling_engine.py:12`](file:///f:/train%20AI%20đồ%20án/src/inference/tiling_engine.py#L12)): Kích thước tile cắt ảnh và tỷ lệ giao biên 20%.

### 2.2. Ngưỡng Sàng Lọc Báo Động Giả (Stage 2 AI Auto-Tagger)
Tham chiếu mã nguồn: [`src/curation/auto_tagger.py:93-130`](file:///f:/train%20AI%20đồ%20án/src/curation/auto_tagger.py#L93-L130)

- **Ngưỡng nhận diện Bóng Râm / Nền Sạch (False Alarm Shadow):**
  - `edge_ratio < 0.018` và `std_brightness < 12.0` $\rightarrow$ Đánh dấu `status: FALSE_ALARM`, `tag_category: hard_negative` ([`src/curation/auto_tagger.py:93`](file:///f:/train%20AI%20đồ%20án/src/curation/auto_tagger.py#L93)).
- **Ngưỡng nhận diện Lóa Sáng (Overexposure):**
  - `mean_brightness > 230` $\rightarrow$ Đánh dấu `status: FALSE_ALARM` ([`src/curation/auto_tagger.py:96`](file:///f:/train%20AI%20đồ%20án/src/curation/auto_tagger.py#L96)).
- **Phân loại Ổ gà sâu nguy hiểm (`pothole_deep`):**
  - `core_mean < 70` và `edge_ratio > 0.06` $\rightarrow$ Gán `severity: CRITICAL` ([`src/curation/auto_tagger.py:119`](file:///f:/train%20AI%20đồ%20án/src/curation/auto_tagger.py#L119)).
- **Phân loại Ổ gà đọng nước (`pothole_water_filled`):**
  - `core_mean < 85` và `std_brightness > 35` $\rightarrow$ Gán `severity: CRITICAL` ([`src/curation/auto_tagger.py:124`](file:///f:/train%20AI%20đồ%20án/src/curation/auto_tagger.py#L124)).

### 2.3. Ngưỡng Đánh Giá Hình Thái Vết Nứt (`CrackAnalyzer`)
Tham chiếu mã nguồn: [`src/curation/crack_analyzer.py:12-20`](file:///f:/train%20AI%20đồ%20án/src/curation/crack_analyzer.py#L12-L20)

- **Vết nứt tóc / nhỏ (Hairline crack):** Bề rộng $< 3\text{ mm}$.
- **Vết nứt trung bình (Medium crack):** Bề rộng $3\text{ mm} - 6\text{ mm}$.
- **Vết nứt nghiêm trọng (Severe crack):** Bề rộng $> 6\text{ mm}$.

---

## 3. Các File Cấu Hình Dataset (.YAML)

### 3.1. `data/unified_road_dataset_15k/data_phase2.yaml`
Tham chiếu: [`data/unified_road_dataset_15k/data_phase2.yaml:1-21`](file:///f:/train%20AI%20đồ%20án/data/unified_road_dataset_15k/data_phase2.yaml#L1-L21)
```yaml
path: F:/train AI đồ án/data/unified_road_dataset_15k
train: train/images
val:   valid/images
test:  test/images

nc: 2
names:
  0: pothole
  1: crack
```

### 3.2. `data/pothole_dataset_5k/data.yaml`
Tham chiếu: [`data/pothole_dataset_5k/data.yaml:1-11`](file:///f:/train%20AI%20đồ%20án/data/pothole_dataset_5k/data.yaml#L1-L11)
```yaml
path: ./pothole_dataset_5k
train: train/images
val:   valid/images
test:  test/images

nc: 1
names: ['pothole']
```
