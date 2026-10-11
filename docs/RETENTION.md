# Quy Chuẩn Lưu Trữ & Dọn Dẹp Định Kỳ (Task Retention Policy)
> Thiết lập cơ chế kiểm soát dung lượng cho thư mục `results/web_runs/` nhằm ngăn chặn phình to dung lượng ổ cứng.

---

## 1. Nguyên Tắc Giữ Lại (Retention Rules)

1. **Số lượng task giữ lại mặc định ($N$):**
   * Hệ thống luôn duy trì **$N$ task mới nhất** (mặc định $N = 5$).
   * Giúp người dùng trên Web UI có thể tra cứu và so sánh các lần phân tích gần đây nhất.

2. **⛔ Danh mục BẢO VỆ TUYỆT ĐỐI (Protected Tasks - CẤM ĐỤNG):**
   * **Task là đích đến của NTFS Junction / Symlink:**
     * Ví dụ: `task_ds_1790603381_f0cab9` là mục tiêu của liên kết [data/road_crack](file:///f:/train%20AI%20đồ%20án/data/road_crack). Xóa hoặc di chuyển task này sẽ làm hỏng dữ liệu dataset của dự án.
   * **Task được tham chiếu trong tài liệu kỹ thuật / hồ sơ nghiệm thu:**
     * Ví dụ: `task_1791271365_faa20d` được ghi nhận làm mẫu trong `docs/project_export/03_api_ui.md`.

3. **Chính sách Chuyển dời An toàn (`_trash_`):**
   * Không bao giờ thực hiện lệnh `rmdir /s /q` hoặc `rm -rf` trực tiếp.
   * Toàn bộ task dọn dẹp sẽ được di chuyển vào thư mục `_trash_YYYYMMDD/web_runs/`. Sau một thời gian kiểm định, người dùng có thể xóa hẳn `_trash_` khi chắc chắn an toàn.

---

## 2. Công Cụ Dọn Dẹp Tự Động (`tools/cleanup_tasks.py`)

Dự án cung cấp script công cụ [tools/cleanup_tasks.py](file:///f:/train%20AI%20đồ%20án/tools/cleanup_tasks.py) để tự động quét và dọn dẹp theo đúng quy chuẩn trên.

### Cách chạy:

```bash
# 1. Chạy thử nghiệm xem danh sách dọn dẹp mà KHÔNG di chuyển (Dry Run):
python tools/cleanup_tasks.py --dry-run

# 2. Dọn dẹp thực tế (Giữ mặc định 5 task mới nhất + các task bảo vệ):
python tools/cleanup_tasks.py

# 3. Tùy chỉnh giữ N task mới nhất (Ví dụ giữ 7 task):
python tools/cleanup_tasks.py --keep 7
```
