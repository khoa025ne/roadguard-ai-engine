# 🤖 AGENT ONBOARDING PROMPT — RoadGuard AI Engine
> **Dán toàn bộ nội dung file này vào chat khi khởi động phiên làm việc mới với bất kỳ AI agent nào.**
> Cập nhật lần cuối: 2026-10-19

---

## PHẦN 1 — NHIỆM VỤ NGAY LẬP TỨC (Đọc trước khi làm gì khác)

Bạn vừa được giao làm việc trên repo **RoadGuard AI Engine** (`khoa025ne/roadguard-ai-engine`).
Trước khi nhận bất kỳ task nào, hãy thực hiện **đúng theo thứ tự** các bước setup dưới đây.
Không được bỏ qua bước nào. Không được đoán mò. Không được tự ý thay đổi code khi chưa đọc xong phần này.

---

## PHẦN 2 — SETUP MÔI TRƯỜNG (Step-by-step)

### BƯỚC 1 — Xác nhận bạn đang ở đúng thư mục

```powershell
# Windows (PowerShell)
cd "f:\train AI đồ án"
git status
git log --oneline -5
```

**Kỳ vọng:** bạn thấy branch hiện tại và 5 commit gần nhất.
Nếu thư mục khác hoặc không có `.git` → DỪNG, hỏi người dùng.

---

### BƯỚC 2 — Pull code mới nhất

```powershell
# Lấy toàn bộ thay đổi từ remote
git fetch --all
git pull origin feature/target-band-api-worker

# Kiểm tra branch đang ở đâu
git branch -vv
```

> ⚠️ **Nhánh làm việc chính là `feature/target-band-api-worker`**.
> Chỉ merge vào `main` khi đã được xác nhận OK bởi người dùng.
> Không tự tạo branch mới trừ khi được yêu cầu.

---

### BƯỚC 3 — Đọc tài liệu bắt buộc (theo thứ tự)

Đọc lần lượt, không được bỏ qua:

1. **`docs/CODEX_BRIEFING.md`** ← **ƯU TIÊN CAO NHẤT** — briefing hiện tại, nguồn sự thật
2. **`tiến độ.md`** ← bảng theo dõi tiến độ, đọc để biết task nào đang mở
3. **`configs/pipeline.yaml`** ← cấu hình pipeline đang chạy thật

```powershell
# Xem nhanh 3 file quan trọng nhất
Get-Content "docs\CODEX_BRIEFING.md"
Get-Content "tiến độ.md" | Select-Object -First 80
Get-Content "configs\pipeline.yaml"
```

> 📌 File `antigravity_prompt.md` là lịch sử cũ — chỉ tham khảo, **không phải nguồn sự thật hiện tại**.

---

### BƯỚC 4 — Thiết lập môi trường Python

```powershell
# Kiểm tra Python version (cần >= 3.10)
python --version

# Tạo virtual environment (nếu chưa có)
python -m venv .venv

# Kích hoạt venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1

# Cài dependencies
pip install -r requirements.txt
```

**Packages cốt lõi cần có:**
| Package | Version tối thiểu | Dùng cho |
|---|---|---|
| `ultralytics` | ≥ 8.3.0 | YOLOv11 inference & training |
| `torch` | ≥ 2.0.0 | Deep learning backend |
| `opencv-python` | ≥ 4.8.0 | Xử lý ảnh/video |
| `numpy` | ≥ 1.24.0 | Array operations |
| `tqdm` | ≥ 4.65.0 | Progress bars |

```powershell
# Verify cài đặt thành công
python -c "import ultralytics; import cv2; import torch; print('OK — torch:', torch.__version__, '| cuda:', torch.cuda.is_available())"
```

---

### BƯỚC 5 — Cấu hình biến môi trường (`.env`)

```powershell
# Kiểm tra file .env đã tồn tại chưa
Test-Path ".env"
```

Nếu chưa có, tạo từ template:

```powershell
Copy-Item ".env.example" ".env"
```

Sau đó mở `.env` và điền các giá trị thực:

```env
# API key cho KTV AI tầng 2 (vision LLM)
KDV_API_KEY=<xin từ người dùng>
KDV_BASE_URL=https://api.xah.io/v1
KDV_MODEL=gpt-5.4
```

> ⚠️ **KHÔNG BAO GIỜ** commit file `.env` lên git.
> `.env` đã có trong `.gitignore` — kiểm tra bằng `git status` nếu nghi ngờ.

---

### BƯỚC 6 — Kiểm tra weights model

```powershell
# Liệt kê các file model đang có
Get-ChildItem "weights\" -Recurse -Filter "*.pt" | Select-Object FullName, Length
```

**Models phải có:**
| File | Vai trò | Bắt buộc? |
|---|---|---|
| `weights/trained/roadguard_multiclass_v1_best.pt` | Defect detection (multiclass) | ✅ Bắt buộc |
| `weights/base/yolo11m-road-seg.pt` hoặc tương đương | Road segmentation | ✅ Bắt buộc |

Nếu thiếu → hỏi người dùng để lấy link download. **Không tự tải model không rõ nguồn gốc.**

---

### BƯỚC 7 — Kiểm tra `class_map.json`

```powershell
Get-Content "class_map.json"
```

**Kỳ vọng phải thấy đúng:**
```json
{"0": "pothole", "1": "crack", "2": "bong_troc"}
```

> ⚠️ **LUẬT SẮT:** Không được hardcode class name trong code.
> Mọi module PHẢI đọc class từ `class_map.json` động.
> Không được tự thay đổi thứ tự class ID.

---

### BƯỚC 8 — Chạy test suite để verify baseline

```powershell
# Chạy toàn bộ test
python -m pytest tests/ -v

# Kỳ vọng: 24/24 PASSED, 0 FAILED
```

Nếu có test fail → **DỪNG, báo cáo** ngay cho người dùng trước khi làm bất cứ điều gì khác.
Không được tiếp tục nếu baseline bị vỡ.

---

### BƯỚC 9 — Kiểm tra pipeline end-to-end (quick smoke test)

```powershell
# Chạy pipeline với video mẫu ngắn (nếu có)
python pipeline.py --help

# Nếu có video test ngắn (30-60s):
# python pipeline.py --video <path_to_short_video.mp4>
```

> 💡 Chỉ test trên **video ngắn 30–60s** trong giai đoạn dev.
> Video đầy đủ chỉ chạy khi nghiệm thu cuối.

---

## PHẦN 3 — KIẾN TRÚC CẦN NẮM (Tóm tắt nhanh)

### Pipeline 7 stages
```
Video + SRT (GPS)
  → 01_segment  : Tách mặt đường khỏi nền (YOLO seg)
  → 02_detect   : Phát hiện defect trong mask (YOLO detect)
  → 03_filter   : NMS + confidence threshold + mask-overlap ≥50%
  → 04_dedup    : ByteTrack — gộp cùng 1 vết qua nhiều frame
  → 05_measure  : GSD → kích thước cm + severity (L1/L2/L3)
  → 06_inspect  : KTV AI tầng 2 kiểm tra lại (kdv_inspector.py)
  → 07_report   : Xuất PDF + JSON/CSV/GeoJSON
```

Code: `src/pipeline/stages/01_segment.py` … `07_report.py`
Entry point: `pipeline.py` | Web UI: `run_ui.py` (port 8080)

### Hai tầng AI
- **Tầng 1 — YOLO local** (`src/inference/predictor.py`): nhanh, chạy offline
- **Tầng 2 — KTV AI** (`src/curation/kdv_inspector.py`): rule-based + vision LLM (chỉ gọi khi confidence thấp)

### Classes (CỨNG — không thay đổi)
Xem `class_map.json`: `0=pothole, 1=crack, 2=bong_troc`

---

## PHẦN 4 — LUẬT LÀM VIỆC (PHẢI TUÂN THỦ)

1. **Bằng chứng trước tiên:** mọi khẳng định kỹ thuật phải kèm `file:dòng` hoặc output lệnh.
2. **Không xóa file** ngoài danh sách đã được duyệt.
3. **Không commit secret** — kiểm tra `git diff --staged` trước mỗi commit.
4. **Không push file > 500MB** (trừ dataset đã duyệt).
5. **Quy trình commit bắt buộc sau mỗi task:**
   ```powershell
   git add <files>
   git commit -m "type: mô tả rõ ràng đã làm gì"
   git push origin feature/target-band-api-worker
   git log origin/feature/target-band-api-worker --oneline -1  # verify
   ```
6. **Kẹt không giải được** → push code hiện tại lên branch → **DỪNG, chờ người**.
7. **Output test:** chỉ giữ metrics JSON + ảnh mẫu. Xóa intermediates (frames, masks) sau khi báo cáo xong.

---

## PHẦN 5 — TASK ĐANG MỞ (Đọc trước khi nhận việc)

| Ưu tiên | Task | Mô tả |
|---|---|---|
| 🔴 Cao | **integrate-multiclass** | Eval per-class AP của `best.pt`, cập nhật `configs/pipeline.yaml`, chạy e2e 1 video ngắn |
| 🟡 Chờ | **ROADSEG-V2** | Fine-tune road-seg trên frame drone thật (chờ lệnh) |
| 🟡 Chờ | **Thông số camera** | User cần cung cấp sensor/focal length thật để tính GSD chính xác |
| 🟡 Chờ | **Chốt RULES severity** | Xác nhận ngưỡng L1/L2/L3 với chủ doanh nghiệp |
| 🟠 Tối ưu | **KTV cost optimization** | Giảm số lần gọi vision LLM (có prompt phân tích riêng) |

> 📌 Đọc `tiến độ.md` để xem trạng thái chi tiết và task được assign.

---

## PHẦN 6 — TIÊU CHÍ NGHIỆM THU (Definition of Done)

Một feature được coi là **DONE** khi:
- [ ] `pytest tests/` → **24+/24 PASSED**
- [ ] Pipeline e2e exit 0 trên video ngắn (30–60s)
- [ ] Defect detection: **mAP@0.5 ≥ 0.70**; FP trên khe co giãn < 5%
- [ ] Road seg: **mIoU ≥ 0.85**; 0 detection ngoài mặt đường
- [ ] Tất cả số trong PDF báo cáo khớp DB 100% (check ngẫu nhiên 5 số)
- [ ] Đã commit + push lên `feature/target-band-api-worker`
- [ ] Đã báo cáo kết quả cho người dùng

---

## PHẦN 7 — CHECKLIST TRƯỚC KHI BẮT ĐẦU LÀM TASK

Tick hết các mục này trước khi code:

- [ ] ✅ Đã chạy `git pull` và đang ở đúng branch
- [ ] ✅ Đã đọc `docs/CODEX_BRIEFING.md`
- [ ] ✅ Đã đọc `tiến độ.md`
- [ ] ✅ `pytest tests/` → 24/24 PASSED
- [ ] ✅ `.env` đã có đủ keys
- [ ] ✅ Weights model đã có đủ
- [ ] ✅ `class_map.json` đúng format
- [ ] ✅ Đã hỏi/xác nhận task với người dùng trước khi code

---

*Prompt v1.0 — 2026-10-19. Cập nhật khi branch hoặc workflow thay đổi.*
