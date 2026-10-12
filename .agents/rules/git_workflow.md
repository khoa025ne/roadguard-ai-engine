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

---

## 4. LUẬT SẮT — PUSH SAU MỖI TASK (Áp dụng mọi task từ nay về sau, không ngoại lệ)

1. **Sequential-Thinking MCP Mandate**: Mỗi khi dùng `sequential-thinking` MCP phân rã task, bước CUỐI CÙNG trong mọi kế hoạch PHẢI LUÔN là "Bước PUSH":
   - Viết báo cáo task $\rightarrow$ `git add` $\rightarrow$ `git commit` $\rightarrow$ `git push origin <branch>`.
   - Kế hoạch nào thiếu Bước PUSH = **chưa hoàn chỉnh, không được phép thực thi**.
2. **Verify Remote Commit**: Sau khi push, BẮT BUỘC verify bằng:
   ```bash
   git log origin/<branch> --oneline -1
   ```
   để xác nhận commit đã lên remote thành công.
   - Nếu push thất bại: thử lại 1 lần $\rightarrow$ nếu vẫn thất bại thì ghi rõ lý do vào báo cáo task rồi mới chuyển sang task tiếp theo. CẤM bỏ qua im lặng.
3. **Checkpoint bắt buộc**: CẤM kết thúc task khi chưa push (hoặc chưa ghi rõ lý do push thất bại trong báo cáo). Đây là checkpoint bắt buộc ngang hàng với viết báo cáo.
