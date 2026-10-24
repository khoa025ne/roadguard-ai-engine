# RG-AI-DATA-03 — handoff (2026-10-22)

- Mục tiêu: khảo sát crack data local/public, thiết kế chọn frame, nhãn box/mask, split và thí nghiệm; chỉ thiết kế, không tải/trích hàng loạt/gán nhãn/train/sửa pipeline.
- Căn cứ và báo cáo: `docs/ai_mvp/19_RG_AI_DATA_03_CRACK_DATA_PLAN.md`; tài liệu nền `01/03/09/10/18`, manifest DJI và `RG-AI-DATA-02.md`.
- Hiện trạng: `merged` 21.424 ảnh/21.587 crack boxes, không mask; 50 frame DJI chưa nhãn; 5 SRT nguồn có GPS/H nhưng thiếu pitch/AGL. Nhãn public/legacy không thay holdout DJI. `0062` chưa được chọn train.
- Đề xuất chờ duyệt: tối đa 120 frame candidate/40 mask từ 0059/0060/0061/0063, reviewer kỹ sư, khoảng 19–37 giờ người; đo pilot 20 frame đầu để điều chỉnh. Chưa có survey holdout độc lập được xác nhận.
- Chưa xác minh: quyền dùng Crack500/UAV-PDD2023, nguồn từng ảnh Roboflow/merged, độ đúng box tự sinh, pixel mask DJI, chiều dài tuyến độc lập cho FP/km, tính độc lập của các clip 04-10.
- Verification: chỉ lệnh kiểm kê/read-only và đối chiếu nguồn chính thức; `git diff --check` cho tài liệu. Không chạy test model vì không đổi code/train.
