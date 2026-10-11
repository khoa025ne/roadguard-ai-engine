# 05 — Cấu Trúc Các Bộ Dữ Liệu & Tập Test Case MVP (Datasets & Test Cases)

## 1. Danh Sách Các Bộ Dữ Liệu Trong `data/`

### 1.1. Bộ Dữ Liệu `unified_road_dataset_15k`
- **Đường dẫn thư mục:** [`data/unified_road_dataset_15k/`](file:///f:/train%20AI%20đồ%20án/data/unified_road_dataset_15k)
- **Đường dẫn file nén:** [`data/unified_road_dataset_15k.zip`](file:///f:/train%20AI%20đồ%20án/data/unified_road_dataset_15k.zip) *(Dung lượng: 292 MB)*
- **Script tạo bộ dữ liệu:** `tools/build_20k_dataset.py` ([`tools/build_20k_dataset.py:1-281`](file:///f:/train%20AI%20đồ%20án/tools/build_20k_dataset.py#L1-L281))
- **Định dạng Annotation:** YOLO Bounding Box chuẩn hóa ($xywh \in [0.0, 1.0]$).
- **Phân bổ chi tiết (Kiểm tra thực tế qua `tools/verify_and_pack_phase2_dataset.py`):**
  - **Tập Train (12,193 ảnh):** 8,705 BBox Ổ gà (`pothole`), 4,000 BBox Vết nứt (`crack`), 4,848 ảnh Mẫu âm tính (File nhãn `.txt` 0 bytes).
  - **Tập Valid (2,056 ảnh):** 973 BBox Ổ gà, 750 BBox Vết nứt, 909 ảnh Mẫu âm tính.
  - **Tập Test (751 ảnh):** 433 BBox Ổ gà, 250 BBox Vết nứt, 303 ảnh Mẫu âm tính.
  - **TỔNG CỘNG:** **15,000 ảnh** (10,111 Ổ gà + 5,000 Vết nứt + 6,060 Ảnh âm tính chống bóng râm = 40.4%).

---

### 1.2. Bộ Dữ Liệu `pothole_dataset_5k`
- **Đường dẫn thư mục:** [`data/pothole_dataset_5k/`](file:///f:/train%20AI%20đồ%20án/data/pothole_dataset_5k)
- **Đường dẫn file nén:** [`data/pothole_dataset_5k.zip`](file:///f:/train%20AI%20đồ%20án/data/pothole_dataset_5k.zip) *(Dung lượng: 221 MB)*
- **Script tạo bộ dữ liệu:** `tools/build_5k_pothole_dataset.py` ([`tools/build_5k_pothole_dataset.py:1-178`](file:///f:/train%20AI%20đồ%20án/tools/build_5k_pothole_dataset.py#L1-L178))
- **Mục đích:** Tối ưu dung lượng siêu nhẹ (~221 MB) phục vụ huấn luyện nhanh (~12-15 phút / 30 epochs) trên Google Colab Free.
- **Phân bổ chi tiết:**
  - **3,940 ảnh Ổ gà thực tế** (`pothole` - ID 0) từ Roboflow Universe (`pothole-pq3lu`).
  - **1,060 ảnh Mẫu âm tính** (bóng râm cây cối, xe cộ, vệt lốp xe, mặt đường phẳng sạch) với file nhãn rỗng.
  - **TỔNG CỘNG:** **5,000 ảnh** (4,145 train, 597 valid, 258 test).

---

### 1.3. Tập Dữ Liệu Gốc `data/pothole/`
- **Đường dẫn:** [`data/pothole/`](file:///f:/train%20AI%20đồ%20án/data/pothole)
- **Nguồn gốc:** Roboflow Universe (`pothole-pq3lu` v1).
- **Quy mô:** 3,940 ảnh (3,345 train, 397 valid, 198 test).

---

## 2. Hệ Thống 7 Thư Mục Test Cases Chuẩn MVP (`data/mvp_test_cases/`)

Được trích xuất tự động qua script `tools/extract_testcases_and_export_dataset.py` ([`tools/extract_testcases_and_export_dataset.py:1-336`](file:///f:/train%20AI%20đồ%20án/tools/extract_testcases_and_export_dataset.py#L1-L336)):

```
data/mvp_test_cases/
├── 01_pothole_deep/             # 27 mẫu | CRITICAL | Ổ gà sâu nguy hiểm (> 5cm)
├── 02_pothole_shallow/          # 24 mẫu | MEDIUM   | Ổ gà nông bề mặt (< 3cm)
├── 03_crack_alligator/          # 50 mẫu | CRITICAL | Vết nứt chân chim / lưới mai rùa
├── 04_crack_longitudinal/       # 38 mẫu | HIGH     | Vết nứt dọc tuyến theo vệt bánh xe
├── 05_crack_transverse/         # 149 mẫu| MEDIUM   | Vết nứt ngang tuyến do co ngót nhiệt
├── 06_joint_gap_or_edge/        # 13 mẫu | MEDIUM   | Khe co giãn mối nối / nứt mép lề
└── 07_hard_negatives/           # 171 mẫu| NONE     | Mẫu âm tính (Bóng cây, bóng drone, nền sạch)
```

Mỗi thư mục Test Case bao gồm:
- `images/`: Ảnh toàn cảnh kèm Bounding Box trực quan hóa.
- `crops/`: Ảnh cắt cận cảnh khuyết tật đã lọc sạch.
- `test_case_spec.json`: Bảng đặc tả JSON tiêu chuẩn nghiệm thu (Mức độ rủi ro, Ngưỡng IoU, Confidence).
- `README.md`: Hướng dẫn kiểm thử thực địa.

---

## 3. Cấu Trúc File Annotation Chuẩn YOLO

Mỗi file nhãn `.txt` chứa 1 hoặc nhiều dòng theo định dạng chuẩn:
```
<class_id> <x_center> <y_center> <width> <height>
```
- `<class_id>`: `0` (pothole) hoặc `1` (crack).
- Tọa độ $x_{center}, y_{center}, w, h$: Chuẩn hóa thuộc dải $[0.0, 1.0]$.
- **Mẫu âm tính (Hard Negative):** File `.txt` có kích thước **0 bytes** (nội dung rỗng).
