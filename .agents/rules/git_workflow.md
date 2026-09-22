# 🌿 QUY TẮC QUẢN TRỊ GIT & NHÁNH (GIT WORKFLOW RULES)

## 1. NGUYÊN TẮC QUẢN LÝ NHÁNH (BRANCHING STRATEGY)
Hệ thống sử dụng cấu trúc 3 cấp độ. Cấm tạo nhánh có tên "backup" (Git và Remote Cloud đã đảm nhiệm việc này).

*   **`main` (hoặc `master`):** BẤT KHẢ XÂM PHẠM. Nhánh chứa sản phẩm chạy ổn định. Tuyệt đối không code hoặc commit trực tiếp lên nhánh này.
*   **`dev` (Develop):** Môi trường làm việc gốc. Nơi tích hợp code từ các tính năng lẻ để test tổng thể trước khi gộp lên `main`.
*   **`feature/*` hoặc `fix/*` (Nhánh Task):** Nơi thực hiện code thực tế. Xong việc phải gộp (merge) trả lại `dev`.
    *   *Quy tắc đặt tên:* `feature/<tên-tính-năng-ngắn-gọn-cách-bằng-gạch-ngang>` (VD: `feature/opencv-video-crop`).
    *   *Quy tắc sửa lỗi:* `fix/<tên-lỗi-ngắn-gọn>` (VD: `fix/srt-timestamp-drift`).

---

## 2. QUY CHUẨN COMMIT (CONVENTIONAL COMMITS FORMAT)
Mọi lệnh commit do AI sinh ra BẮT BUỘC theo định dạng: `<type>: <Mô tả ngắn gọn bằng tiếng Việt>`. Không dùng các câu chung chung như "update code".

*   `feat`: Thêm tính năng/logic mới (VD: `feat: tích hợp OpenCV cắt frame video`).
*   `fix`: Sửa lỗi bug (VD: `fix: sửa lỗi crash khi video không có frame`).
*   `refactor`: Tối ưu code, không đổi logic (VD: `refactor: tách hàm đo lường tọa độ sang file riêng`).
*   `docs`: Cập nhật tài liệu (VD: `docs: cập nhật README cho API AI`).
*   `chore`: Cấu hình, update thư viện vặt.

---

## 3. LUỒNG LÀM VIỆC TỰ ĐỘNG (AUTONOMOUS EXECUTION FLOW)

### KỊCH BẢN 1: Bắt đầu một tính năng mới
Tự động chạy chuỗi lệnh tạo nhánh mới từ `dev`:
```bash
git checkout dev
git pull origin dev
git checkout -b feature/<tên-tính-năng>
```

### KỊCH BẢN 2: Bắt đầu một bản sửa lỗi (Bugfix)
```bash
git checkout dev
git pull origin dev
git checkout -b fix/<tên-lỗi>
```

### KỊCH BẢN 3: Hoàn thành tính năng và gộp về `dev`
```bash
git checkout dev
git pull origin dev
git merge feature/<tên-tính-năng>
git push origin dev
git branch -d feature/<tên-tính-năng>
```
