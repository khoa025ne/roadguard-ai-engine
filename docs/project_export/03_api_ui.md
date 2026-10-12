# 03 — Chi Tiết API Endpoints & Giao Diện Web UI

## 1. Danh Sách 20 REST API Endpoints (`src/api/ui_server.py`)

Tệp [`src/api/ui_server.py`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py) (1,144 dòng) chứa toàn bộ các endpoint xử lý giao diện và nghiệp vụ.

### 1.1. Endpoints Hệ Thống & Khởi Tạo

#### 1. `GET /` ([`ui_server.py:86`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L86))
- **Mục đích:** Phục vụ trang HTML chính `index.html`.
- **Response:** `HTMLResponse` chứa nội dung file [`src/api/web/index.html`](file:///f:/train%20AI%20đồ%20án/src/api/web/index.html).

#### 2. `GET /api/init-info` ([`ui_server.py:95`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L95))
- **Mục đích:** Trả về danh sách các mô hình AI có sẵn (sắp xếp theo `mtime` mới nhất lên đầu), các video mẫu và dataset preset có sẵn.
- **Trích đoạn xử lý chính:**
```python
# ui_server.py:98-110
    models = []
    for pt_file in WEIGHTS_DIR.glob("**/*.pt"):
        if pt_file.stat().st_size == 0:
            continue
        size_mb = round(pt_file.stat().st_size / (1024 * 1024), 2)
        models.append({
            "name": pt_file.name,
            "path": str(pt_file).replace("\\", "/"),
            "size_mb": size_mb,
            "mtime": pt_file.stat().st_mtime,
        })
    models.sort(key=lambda x: x["mtime"], reverse=True)
```
- **Response mẫu:**
```json
{
  "models": [
    {"name": "roadguard_pothole_best_5k.pt", "path": "F:/train AI đồ án/weights/trained/roadguard_pothole_best_5k.pt", "size_mb": 5.22},
    {"name": "roadguard_crack_yolo11n_v1.pt", "path": "F:/train AI đồ án/weights/trained/roadguard_crack_yolo11n_v1.pt", "size_mb": 5.22}
  ],
  "preset_videos": [...],
  "preset_datasets": [...],
  "latest_task_id": "task_1791271365_faa20d"
}
```

---

### 1.2. Endpoints Upload Dữ Liệu

#### 3. `POST /api/upload-video` ([`ui_server.py:187`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L187))
- **Mục đích:** Tải video từ máy tính (.mp4, .mov, .avi, .mkv) lưu vào `uploads/`.
- **Params:** `file: UploadFile`

#### 4. `POST /api/upload-dataset` ([`ui_server.py:206`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L206))
- **Mục đích:** Tải file nén dataset (.zip) từ máy tính.
- **Params:** `file: UploadFile`

#### 5. `POST /api/upload-folder` ([`ui_server.py:225`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L225))
- **Mục đích:** Tải nhiều file ảnh trực tiếp từ chọn thư mục Webkit Directory (`webkitdirectory`).
- **Params:** `files: List[UploadFile]`

#### 6. `GET /api/frames/{task_id}/{filename}` ([`ui_server.py:255`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L255))
- **Mục đích:** Trả về file ảnh frame đã vẽ Bounding Box theo `task_id`.

#### 7. `GET /api/crops/{task_id}/{filename}` ([`ui_server.py:265`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L265))
- **Mục đích:** Trả về file ảnh crop cận cảnh khuyết tật theo `task_id`.

---

### 1.3. Endpoints Phân Tích & Tiến Trình (Analysis Pipeline)

#### 8. `POST /api/start-analysis` ([`ui_server.py:474`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L474))
- **Mục đích:** Khởi chạy tiến trình phân tích Video Flycam bất đồng bộ.
- **Request Body (`AnalysisRequest`):** `video_path`, `model_path`, `conf_threshold`, `iou_threshold`, `tile_size`, `tile_overlap`, `auto_curate_ktv`.
- **Trích đoạn xử lý chính:**
```python
# ui_server.py:530-545
    task_id = f"task_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    task_dir = RESULTS_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    bg.add_task(
        run_video_analysis_task,
        task_id=task_id,
        video_path=req.video_path,
        model_path=req.model_path,
        conf_threshold=req.conf_threshold,
        iou_threshold=req.iou_threshold,
        tile_size=req.tile_size,
        auto_curate_ktv=req.auto_curate_ktv
    )
    return {"status": "SUCCESS", "task_id": task_id}
```

#### 9. `POST /api/start-dataset-analysis` ([`ui_server.py:662`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L662))
- **Mục đích:** Khởi chạy quét và phân tích trên tập ảnh Dataset (.zip hoặc Folder).
- **Request Body (`DatasetAnalysisRequest`):** `dataset_source`, `dataset_path`, `model_path`, `conf_threshold`, `max_images`.

#### 10. `GET /api/task-status/{task_id}` ([`ui_server.py:679`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L679))
- **Mục đích:** Trả về phần trăm tiến độ `%`, trạng thái `RUNNING`, `COMPLETED`, `FAILED` và thông điệp log.

#### 11. `GET /api/task-results/{task_id}` ([`ui_server.py:696`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L696))
- **Mục đích:** Trả về toàn bộ danh sách khuyết tật, khung hình và kết quả thẩm định đã nạp disk fallback từ `curated_results.json`.

#### 12. `GET /api/download/{task_id}/{filename}` ([`ui_server.py:741`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L741))
- **Mục đích:** Tải file báo cáo JSON/CSV/GeoJSON của task.

---

### 1.4. Endpoints Curation & KTV Thẩm Định (Stage 2 AI)

#### 13. `POST /api/curation/filter-and-tag` ([`ui_server.py:794`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L794))
- **Mục đích:** Gọi `AIAutoTagger` để phân loại chi tiết và khử trùng lặp toàn bộ mảng crops.

#### 14. `POST /api/curation/inspect-overview-context` ([`ui_server.py:840`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L840))
- **Mục đích:** Thẩm định KTV GPT-5.4 Vision chế độ DUAL-VIEW CONTEXT (Góc nhìn toàn cảnh + cận cảnh phóng to).
- **Trích đoạn xử lý chính:**
```python
# ui_server.py:885-920
    tagger = AIAutoTagger(provider="kdv_gpt54")
    curated_results = tagger.curate_with_overview_context(
        overview_image=overview_img,
        items=items_to_inspect,
        road_metadata={"task_id": req.task_id}
    )
```

#### 15. `POST /api/curation/assess-cracks` ([`ui_server.py:970`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L970))
- **Mục đích:** Gọi chuyên module `CrackAnalyzer` đo bề rộng nứt mm, góc nghiêng và khuyến nghị kỹ thuật.

#### 16. `POST /api/curation/update-item` ([`ui_server.py:1040`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L1040))
- **Mục đích:** Cập nhật nhãn/mức độ rủi ro do người dùng chỉnh sửa trên giao diện.

#### 17. `POST /api/curation/save-all` ([`ui_server.py:1068`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L1068))
- **Mục đích:** Lưu toàn bộ kết quả thẩm định xuống file `curated_results.json`.

#### 18. `GET /api/curation/results/{task_id}` ([`ui_server.py:1081`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L1081))
- **Mục đích:** Tải lại mảng `curated_results.json` của task.

#### 19. `POST /api/curation/export-dataset` ([`ui_server.py:1096`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L1096))
- **Mục đích:** Gọi `DatasetExporter` đóng gói danh sách khuyết tật thành Dataset YOLO và sinh link download.

#### 20. `GET /api/curation/download/{filename}` ([`ui_server.py:1137`](file:///f:/train%20AI%20đồ%20án/src/api/ui_server.py#L1137))
- **Mục đích:** Trả về file `.zip` dataset đã đóng gói cho trình duyệt tải về.

---

## 2. Logic JavaScript & Xử Lý Giao Diện (`src/api/web/index.html`)

Tệp [`src/api/web/index.html`](file:///f:/train%20AI%20đồ%20án/src/api/web/index.html) (2,024 dòng) điều khiển toàn bộ luồng SPA:

1. **Khởi Tạo Trang (`initPage()` - `index.html:804`):**
   - Gọi `GET /api/init-info`, nạp danh sách mô hình vào `#modelSelect`.
   - Chọn mặc định mô hình mới nhất tại vị trí chỉ số 0 (`if (idx === 0)` - `index.html:816`).
   - Cập nhật Badge tên mô hình góc trên `#modelBadge` (`index.html:825`).

2. **Chuyển Đổi Nguồn Dữ Liệu (`toggleInputMode()` - `index.html:270`):**
   - Chuyển đổi linh hoạt giữa Chế độ Video Flycam và Chế độ Dataset ZIP/Folder.

3. **Kích Hoạt Phân Tích (`startAnalysis()` - `index.html:920`):**
   - Thu thập thông số `modelSelect`, `confThreshold`, `iouThreshold`, `autoCurateKtv`.
   - Gửi yêu cầu `POST /api/start-analysis` hoặc `POST /api/start-dataset-analysis`.
   - Mở Interval 1 giây gọi `GET /api/task-status/{task_id}` để cập nhật Progress Bar.

4. **Hiển Thị Kết Quả (`renderResults()` - `index.html:1150`):**
   - Tab 1: Khung hình Video Player vẽ BBox khuyết tật.
   - Tab 2: Bộ sưu tập Crops Card kèm Badge xác thực KTV (`✅ [KTV: Tag]`, `💡 Reasoning`).
   - Tab 3: KDV Evaluation Dashboard hiển thị 4 Golden Metrics, Tag Chips bộ lọc và Bảng so sánh Matrix.

5. **Gửi Thẩm Định KTV Tầng 2 (`inspectOverviewContext()` - `index.html:1580`):**
   - Gửi request `POST /api/curation/inspect-overview-context` và cập nhật trực tiếp huy hiệu xác thực lên từng Crop Card.
