# 04 — Đặc Tả Mô Hình AI & Kịch Bản Huấn Luyện (Models & Training)

## 1. Danh Sách Các Model Checkpoints (`weights/trained/`)

Hệ thống lưu trữ các file trọng số xuất xưởng tại thư mục `weights/trained/`:

### 1.1. `roadguard_crack_yolo11n_v1.pt` (5.22 MB)
- **Kiến trúc mạng:** YOLOv11n (Nano - 2.59 triệu tham số).
- **Danh sách Class Map:**
  - `0: crack` (Vết nứt bề mặt đường bê tông xi măng / nhựa asphalt).
- **Nguồn gốc dữ liệu huấn luyện:** Tập dữ liệu Roboflow `road-crack-7jw6e` v1 (6,315 ảnh 640x640: 5,531 train, 519 val, 265 test).
- **Kết quả Benchmark độc lập (265 ảnh test / 702 instances):**
  - **Precision:** `80.37%`
  - **Recall:** `72.33%`
  - **mAP@50:** `78.60%`
  - **mAP@50-95:** `45.54%`
  - **Tốc độ suy luận CPU:** ~63.9 ms/ảnh (~15.6 FPS). GPU > 150 FPS.

### 1.2. `roadguard_best_15k.pt` (5.22 MB)
- **Kiến trúc mạng:** YOLOv11n (2.59M tham số).
- **Danh sách Class Map:**
  - `0: pothole` (Ổ gà, sụt lún mặt đường).
  - `1: crack` (Vết nứt bề mặt đường).
- **Nguồn gốc dữ liệu huấn luyện:** Bộ dữ liệu hợp nhất `unified_road_dataset_15k` (15,000 ảnh: 3,940 ổ gà, 5,000 vết nứt, 6,060 mẫu âm tính khử bóng râm).
- **Hiệu năng đạt được:**
  - **mAP@50 (Overall):** ~`82.40%`
  - **Precision:** ~`84.10%`
  - **Khả năng chống báo động giả bóng râm:** Rất tốt nhờ 40.4% mẫu âm tính nhãn rỗng.

### 1.3. `roadguard_pothole_best_5k.pt` (5.22 MB)
- **Kiến trúc mạng:** YOLOv11n.
- **Danh sách Class Map:**
  - `0: pothole` (Ổ gà / sụt tróc mặt đường).
- **Nguồn gốc dữ liệu huấn luyện:** Bộ dữ liệu `pothole_dataset_5k` (5,000 ảnh: 3,940 ổ gà thực tế + 1,060 mẫu âm tính bóng râm).
- **Mục đích thiết kế:** Mô hình siêu nhẹ chuyên dụng cho Ổ gà, tối ưu huấn luyện siêu tốc trên Google Colab Free (~12-15 phút / 30 epochs).

---

## 2. Đặc Tả Các Kịch Bản Huấn Luyện & Script (`tools/`)

### 2.1. Script Transfer Learning Nâng Cấp Phase 2 (`tools/train_upgrade_model.py`)
Tham chiếu mã nguồn: [`tools/train_upgrade_model.py:1-92`](file:///f:/train%20AI%20đồ%20án/tools/train_upgrade_model.py#L1-L92)

- **Mục tiêu:** Chuyển đổi mô hình 1-class `roadguard_crack_yolo11n_v1.pt` sang mô hình 2-class (`pothole`, `crack`) mà không bị mất tri thức nhận diện vết nứt cũ (Catastrophic Forgetting).
- **Bảng Siêu Tham Số (Hyperparameters):**
  - **Weights khởi đầu:** `weights/trained/roadguard_crack_yolo11n_v1.pt` ([`tools/train_upgrade_model.py:23`](file:///f:/train%20AI%20đồ%20án/tools/train_upgrade_model.py#L23))
  - **Dataset config:** `data/unified_road_dataset_15k/data.yaml` ([`tools/train_upgrade_model.py:28`](file:///f:/train%20AI%20đồ%20án/tools/train_upgrade_model.py#L28))
  - **Epochs:** `30`
  - **Batch size:** `16` (VRAM ~4.5 GB)
  - **Image Size:** `640`
  - **`freeze`:** `10` (Đóng băng 10 layer Backbone bảo vệ các bộ lọc đặc trưng vết nứt - [`tools/train_upgrade_model.py:77`](file:///f:/train%20AI%20đồ%20án/tools/train_upgrade_model.py#L77))
  - **`lr0` (Initial Learning Rate):** `0.001` (Thấp hơn 10x so với train từ đầu)
  - **`lrf` (Final Learning Rate Factor):** `0.01` (Cosine annealing decay)
  - **`warmup_epochs`:** `2`

### 2.2. Script Huấn Luyện Local Phase 2 (`tools/train_phase2_local.py`)
Tham chiếu mã nguồn: [`tools/train_phase2_local.py:1-118`](file:///f:/train%20AI%20đồ%20án/tools/train_phase2_local.py#L1-L118)

- **Mục tiêu:** Chạy huấn luyện hoàn chỉnh Phase 2 trên máy Local có GPU CUDA.
- **Trích nguyên văn đoạn gọi hàm `model.train()`:**
```python
# tools/train_phase2_local.py:72-97
    results = model.train(
        data=args.data,
        epochs=args.epochs,        # Default: 35
        imgsz=args.imgsz,          # Default: 640
        batch=args.batch,          # Default: 16
        device=device,
        freeze=args.freeze,        # Default: 10
        lr0=0.001,
        lrf=0.01,
        warmup_epochs=3,
        box=7.5,                   # Weight cho Bounding Box Loss
        cls=0.5,                   # Weight cho Classification Loss
        dfl=1.5,                   # Weight cho Distribution Focal Loss
        mosaic=0.5,
        close_mosaic=5,            # Tắt mosaic 5 epoch cuối
        project=str(WORKSPACE_ROOT / "runs/phase2_train"),
        name="roadguard_yolo11n_v2",
        exist_ok=True,
        save=True,
        val=True,
        plots=True
    )
```

### 2.3. Các Jupyter Notebook Generator (`tools/generate_*_notebook.py`)
- **`generate_phase2_colab_notebook.py`** ([`tools/generate_phase2_colab_notebook.py:1-307`](file:///f:/train%20AI%20đồ%20án/tools/generate_phase2_colab_notebook.py#L1-L307)): Sinh notebook [`notebooks/RoadGuard_Phase2_Upgrade_Colab.ipynb`](file:///f:/train%20AI%20đồ%20án/notebooks/RoadGuard_Phase2_Upgrade_Colab.ipynb) phục vụ Colab GPU T4.
- **`generate_pothole_5k_notebook.py`** ([`tools/generate_pothole_5k_notebook.py:1-241`](file:///f:/train%20AI%20đồ%20án/tools/generate_pothole_5k_notebook.py#L1-L241)): Sinh notebook [`notebooks/RoadGuard_Pothole_5K_Colab.ipynb`](file:///f:/train%20AI%20đồ%20án/notebooks/RoadGuard_Pothole_5K_Colab.ipynb).

---

## 3. Ma Trận Đổi Tên Lớp & Mapping Class IDs

| YOLO Class ID | Tên Lớp Gốc | Tên Tiếng Việt Trực Quan | Thuộc Tính Gắn Tag KTV (Stage 2) |
| :---: | :--- | :--- | :--- |
| **0** | `pothole` | Ổ gà, sụt lún mặt đường | `pothole_deep` (>5cm), `pothole_shallow` (<3cm), `pothole_water_filled` |
| **1** | `crack` | Vết nứt bề mặt đường | `crack_longitudinal`, `crack_transverse`, `crack_alligator`, `crack_edge`, `joint_gap` |
| **-1** | `background` | Mẫu âm tính (Nền sạch / Bóng râm) | `false_alarm_shadow`, `false_alarm_glare`, `false_alarm_debris` |
