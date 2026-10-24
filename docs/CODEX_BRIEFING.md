# CODEX BRIEFING — RoadGuard AI Engine (Drone MVP)

> File onboarding cho AI agent mới (Codex). Đọc file này trước khi làm bất cứ việc gì.
> Repo: `khoa025ne/roadguard-ai-engine` · Nhánh làm việc: `dev` (chỉ merge vào `main` khi đã xác nhận OK).

---

## 1. BỐI CẢNH

### 1.1 Dự án là gì
**RoadGuard AI Engine** — hệ thống thị giác máy tính phân tích khuyết tật mặt đường **bê tông nông thôn Việt Nam** từ **video drone (flycam)**.
Mục tiêu cuối: cho ra **báo cáo có GPS + mức độ nặng/nhẹ** để chủ doanh nghiệp (nhà thầu) lên kế hoạch sửa chữa trong thời gian bảo hành.

### 1.2 Mục tiêu MVP (đã chốt, không đổi)
- **Input:** video drone + telemetry / file `.SRT` có GPS.
- **Output:** báo cáo PDF gồm:
  - Bản đồ chấm defect theo mức độ (xanh/vàng/đỏ),
  - Bảng chi tiết từng vết: ID, loại, kích thước (cm), GPS, ảnh crop.
- **Nguyên tắc vàng:**
  - Model chỉ được "nhìn" **mặt đường bê tông**. Detection ngoài mặt đường (cỏ, cây, nhà, xe) = false positive phải loại.
  - AI chỉ **đề xuất**, con người quyết định. Mọi detection phải có **model version + provenance + frame timestamp**.
  - Bbox của AI **không phải** kích thước vật lý — kích thước thật do đo ngoài hiện trường hoặc tính qua GSD có cơ sở.

### 1.3 Kiến trúc pipeline (7 stages)
```
Video + telemetry
  → 01_segment  (tách mặt đường bê tông khỏi nền — YOLO seg)
  → 02_detect   (YOLO phát hiện khuyết tật trong vùng mask)
  → 03_filter   (NMS + ngưỡng confidence + mask-overlap filter ≥50%)
  → 04_dedup    (ByteTrack: 1 vết qua nhiều frame = 1 defect_id duy nhất)
  → 05_measure  (GSD → kích thước cm + mức độ nặng/nhẹ theo RULES)
  → 06_inspect  (KTV tầng 2 kiểm tra lại — xem §1.4)
  → 07_report   (xuất PDF + JSON/CSV/GeoJSON)
```
Code: `src/pipeline/stages/01_segment.py` … `07_report.py`. Entry: `pipeline.py`. Web UI: `run_ui.py` (:8080).

### 1.4 Hai tầng AI
- **Tầng 1 — YOLO local:** quét nhanh toàn frame (multiclass: pothole, crack, spalling).
- **Tầng 2 — "KTV AI"** (`src/curation/kdv_inspector.py`): kiểm tra lại từng detection, gán mức độ, xử lý ca khó.
  Gồm: rule-based (`mean_brightness`, `edge_ratio`) làm đường chính + vision LLM qua proxy (`gpt-5.4`) chỉ cho ca
  confidence thấp + heuristic fallback khi mất API key.
  ⚠️ Gọi VLM từng crop chậm (~10s/crop) và tốn chi phí — đang có nhiệm vụ tối ưu chi phí (xem §5).

### 1.5 Quy ước label (đã chốt — không tự đổi)
`class_map.json` duy nhất tại repo root: `{0: pothole, 1: crack, 2: bong_troc}`.
Mọi đường inference đọc từ file này. Cấm hardcode `0:pothole` / `0:crack` lẻ trong code.

---

## 2. MONG MUỐN CỦA OUTPUT — LUẬT LÀM VIỆC

1. **Bằng chứng:** mọi khẳng định kỹ thuật phải kèm `file:dòng` hoặc output lệnh. Không đoán mò.
2. **Xóa file:** chỉ xóa mục đã liệt kê trong audit được duyệt. Mục mới phát hiện → ghi "xem lại sau", không tự xóa.
3. **Không commit secret.** Không push file >500MB (trừ dataset đã duyệt).
4. **Nhánh:** làm việc và push lên nhánh `dev`. Chỉ merge vào `main` khi đã xác nhận OK.
5. **LUẬT SẮT:** xong task → `git add` → commit (message ghi rõ đã làm gì) → push lên `dev` →
   verify bằng `git log origin/dev --oneline -1`. Push fail → thử lại 1 lần → vẫn fail thì ghi rõ trong
   commit message rồi làm tiếp.
6. **Output test:** chỉ giữ metrics JSON + ảnh mẫu minh họa; xóa intermediates (frames, masks) sau khi xong.
   `outputs/` cho vào `.gitignore`. Chạy lặp thì dùng video ngắn (30–60s), full video chỉ khi nghiệm thu cuối.
7. **Kẹt:** không tự giải được → push code hiện tại lên `dev` → DỪNG, chờ người.
8. **Đồng bộ:** điều phối viên check git mỗi 15 phút và tự báo tiến độ khi có gì mới.

---

## 3. HIỆN TẠI ĐANG CÓ NHỮNG GÌ

### 3.1 Mission cũ: 10/10 task hoàn thành (2026-10-12, PROJECT_COMPLETE)
| Task | Kết quả |
|---|---|
| bootstrap-inbox-loop | Xong |
| field-test | Xong — pipeline chạy được trên video drone thật |
| integrate-multiclass | **SKIP lúc đó (chờ `best.pt`) → NAY ĐÃ CÓ FILE** (xem §3.2), cần chạy lại |
| ktv-wiring | Xong — stage `06_inspect` đã được pipeline gọi thật |
| pdf-report | Xong — `src/reporting/pdf_exporter.py` (weasyprint + reportlab fallback) |
| severity-rules | Xong — RULES theo FHWA trong `05_measure.py`, GSD đang là số tạm |
| ui-polish | Xong |
| ui-redesign | Xong — redesign toàn bộ UI theo design tokens, có `docs/UI_DESIGN.md` + `docs/UI_INTEGRATION.md` |
| ui-redesign-fix | Xong |
| Báo cáo tổng | `reports/agent_reports/PROJECT_COMPLETE.md` |

Pipeline chạy end-to-end exit 0, **24/24 tests pass**.

### 3.2 Models & weights
- **Road segmentation:** `yolo11m-road-seg.pt` (43MB) — benchmark 50 frame drone thật: detect 49/50.
- **Defect detection (multiclass):** `weights/trained/roadguard_multiclass_v1_best.pt` — **đã có** (xác nhận 2026-10-19).
  Baseline cũ: pothole AP@50 89.06%, crack 94.30%. Dataset merged: 21.424 ảnh / 31.698 bbox.
- Các checkpoint cũ: `roadguard_crack_yolo11n_v1.pt` (crack-only), `roadguard_best_15k.pt`, `roadguard_pothole_best_5k.pt`.

### 3.3 Modules chính trong `src/`
| Thư mục | Nội dung |
|---|---|
| `src/pipeline/stages/` | 7 stages `01_segment` → `07_report` |
| `src/inference/` | `predictor.py` (đọc `class_map.json` động), `tiling_engine.py` |
| `src/curation/` | `kdv_inspector.py` (KTV tầng 2), `deduplicator.py`, `auto_tagger.py`, `crack_analyzer.py` |
| `src/measurement/` | `metric_estimator.py` (GSD), `spatial_tracker.py` |
| `src/ingestion/` | `srt_parser.py` (GPS từ subtitle DJI) |
| `src/reporting/` | `pdf_exporter.py` |
| `src/api/` | `ui_server.py` (Web UI + `/api/*`) |
| `configs/` | `pipeline.yaml` và các file cấu hình dataset |

### 3.4 Tests hiện có (`tests/`)
`test_crack_and_dedup.py`, `test_curation.py`, `test_dataset_scanner.py`, `test_pipeline.py`,
`test_ui_curation_endpoints.py` — 24/24 pass.

### 3.5 Việc còn mở (chưa làm)
1. **integrate-multiclass (chạy lại):** eval per-class AP của `best.pt` trên test split, so với baseline
   (pothole 89.06% / crack 94.30%); regression >3% thì báo cáo, không tự rollback. Cập nhật model path
   trong `configs/pipeline.yaml` (stage `02_detect`), chạy e2e 1 video ngắn.
2. **ROADSEG-V2:** fine-tune road-seg trên frame drone thật (task đã soạn, chờ lệnh).
3. **Thông số camera drone thật** (sensor, tiêu cự, rộng ảnh) — do user cung cấp, hiện GSD đang là số tạm
   (mọi giá trị tạm đánh dấu `# TẠM — chờ thông số camera thật`).
4. **Chốt bảng RULES** (ngưỡng nặng/nhẹ) với chủ doanh nghiệp — hiện là số mẫu theo FHWA.
5. **Tối ưu chi phí KTV** — có prompt phân tích riêng (hỏi điều phối viên để lấy).

---

## 4. TEST — DANH SÁCH & CÁCH GIẢI QUYẾT

### 4.1 Test kỹ thuật (code)
| Test | Chạy thế nào | Đạt khi nào |
|---|---|---|
| Unit/integration (`tests/`) | `pytest tests/` | 24/24 pass, không vỡ pipeline cũ |
| E2E pipeline | `python pipeline.py` (hoặc entry tương đương) trên video mẫu | exit 0, đủ 7 stages chạy (kiểm tra log `06_inspect` không skip) |
| Field test | Full pipeline trên **1 video drone đầy đủ** (không cắt) | Báo cáo: tổng thời gian, FPS, số detection, % detection bị mask loại, phân bố severity, **3 case tốt nhất + 3 case tệ nhất** kèm frame minh họa |
| Eval gate | Chạy trên 7 thư mục `mvp_test_cases`, chú ý `hard_negatives` và `joint_gap_or_edge` | FP trên khe co giãn < 5% số detection |

### 4.2 Tiêu chí nghiệm thu (Definition of Done — đã chốt)
- Defect detection: **mAP@0.5 ≥ 0.7** trên tập val; FP trên khe co giãn < 5%.
- Road segmentation: **mIoU ≥ 0.85**; **0 detection nằm hẳn ngoài mặt đường**.
- Dedup liên frame: sai lệch đếm **< 10%** trên video test 60s (đếm tay đối chiếu).
- Định vị: plot điểm defect lên bản đồ — điểm nằm trên/gần tuyến đường.
- Báo cáo: **mọi con số trong PDF khớp DB 100%** (kiểm tra ngẫu nhiên 5 số).
- Demo: chạy được trên **video drone thật**, không số minh họa.

### 4.3 Quản lý output test (vì test sinh output rất nặng)
1. Chỉ giữ: metrics JSON + ảnh mẫu minh họa. Xóa intermediates (frames, masks) ngay sau khi báo cáo xong.
2. `outputs/` cho vào `.gitignore` — cấm push output nặng lên GitHub.
3. Lúc dev/test lặp: chạy trên đoạn video ngắn (30–60s). Full video chỉ khi nghiệm thu cuối.
4. Ảnh cho mục đích test: lưu JPG quality 70–80, đủ nhìn là được.

---

## 5. BỘ DOCS THỐNG NHẤT (đang gộp dần vào `docs/`)
- `docs/PIPELINE.md` — kiến trúc pipeline 7 stages.
- `docs/UI_DESIGN.md` + `docs/UI_INTEGRATION.md` — thiết kế UI và điểm tích hợp.
- `docs/ke_hoach_thuc_thi_AI.md` — kế hoạch thực thi AI (Epic/Task).
- `docs/specs/` — spec chi tiết từng module.
- `tiến độ.md` (root) — bảng theo dõi tiến độ & quy tắc (đọc khi bắt đầu phiên làm việc).
- `antigravity_prompt.md` (root) — prompt của agent đời trước (tham khảo lịch sử, không dùng nữa).
- File này (`CODEX_BRIEFING.md`) — briefing hiện tại, là nguồn đúng nhất.

---

*Briefing v1.0 — 2026-10-19. Cập nhật khi scope hoặc luật thay đổi.*
