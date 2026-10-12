# KIẾN TRÚC INBOX RUNNER LOOP (TỰ ĐỘNG HÓA NHẬN NHIỆM VỤ)

**Tác giả**: Antigravity Agent & Muse (Pé)  
**Mục tiêu**: Tự động hóa hoàn toàn quy trình nhận nhiệm vụ từ xa. Người điều phối (Muse) chỉ cần tạo file task và push lên thư mục `inbox/` của repository; máy trạm Windows sẽ tự động kích hoạt Antigravity Agent (`agy`) chạy ngầm định kỳ 30 phút/lần mà không cần thao tác dán lệnh thủ công.

---

## 1. Sơ Đồ Kiến Trúc Hoạt Động (Architecture Flow)

```
[Muse / Điều phối viên]
         │ (Tạo file inbox/NEXT_PROMPT.md hoặc task_*.md)
         ▼
[GitHub Repository] (nhánh feature/target-band-api-worker hoặc main)
         │
         │ (Windows Task Scheduler định kỳ 30 phút / 1 lần)
         ▼
[install_windows.ps1] -> [runner.py]
         │
         ├── Bước 1: `git pull` để nhận prompt mới nhất từ remote.
         │
         ├── Bước 2: Quét thư mục `inbox/`:
         │           ├── Không có file mới -> In log "inbox empty" -> KẾT THÚC.
         │           └── Có file task (*.md không bắt đầu bằng _) -> Đọc nội dung task.
         │
         ├── Bước 3: Gọi Antigravity CLI (`agy`) thực thi task tự hành.
         │
         ├── Bước 4: Đổi tên file task đã xử lý thành `inbox/_done_<timestamp>.md`.
         │
         └── Bước 5: Báo cáo kết quả và đồng bộ `git push` về GitHub theo LUẬT SẮT.
```

---

## 2. Danh Mục Các Thành Phần (Components)

1. **`runner.py`**:
   - Trình điều khiển trung tâm (Python 3.10+).
   - Thực hiện kiểm tra đồng bộ git, quét hàng đợi `inbox/`, kích hoạt `agy` và lưu trữ lịch sử tác vụ.
2. **`install_windows.ps1`**:
   - Kịch bản PowerShell tự động đăng ký tác vụ trong Windows Task Scheduler (`RoadGuard_InboxRunner`).
   - Cấu hình tần suất chạy: 30 phút một lần, tự động chạy khi người dùng đăng nhập.
3. **`uninstall_windows.ps1`**:
   - Kịch bản gỡ bỏ tác vụ khỏi Windows Task Scheduler khi bảo trì.
4. **Thư mục hàng đợi `inbox/`**:
   - `inbox/NEXT_PROMPT.md`: Tệp chứa chỉ thị mới cần thực hiện ngay lập tức.
   - `inbox/_done_*.md`: Các chỉ thị đã hoàn thành (tiền tố `_` để runner bỏ qua).

---

## 3. Quy Chuẩn Đặt Tên & Xử Lý Tác Vụ Trong `inbox/`

- **Tệp ưu tiên cao nhất**: `inbox/NEXT_PROMPT.md`.
- **Tệp theo chuỗi nhiệm vụ**: `inbox/task_01_feature.md`, `inbox/task_02_eval.md`.
- **Tệp bỏ qua**: Mọi tệp bắt đầu bằng dấu gạch dưới `_` (ví dụ `_done_20261012_1400.md`, `_template.md`).

---

## 4. Hướng Dẫn Vận Hành & Kiểm Tra

### 4.1. Kiểm thử thủ công (Dry-run):
```powershell
python tools\inbox_runner\runner.py
```
*Kết quả kỳ vọng khi không có task mới*:
```
[inbox_runner] 2026-10-12 14:05:00 — git pull up-to-date.
[inbox_runner] 2026-10-12 14:05:01 — inbox empty.
```

### 4.2. Cài đặt tự động định kỳ 30 phút:
```powershell
powershell -ExecutionPolicy Bypass -File "tools\inbox_runner\install_windows.ps1" -RepoPath "F:\train AI đồ án"
```
