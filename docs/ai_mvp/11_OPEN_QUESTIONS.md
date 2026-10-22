# 11 — Câu hỏi mở cần chốt

1. ~~Model/drone chính xác là gì; sensor, tiêu cự, resolution, FPS, codec?~~ **Đã chốt:** DJI Mini 2 SE, 6.17×4.55 mm, 4.26 mm, 2720×1530/30fps.
2. ~~4 MP4 hiện có file SRT tương ứng ở đâu; tên ghép theo quy tắc nào?~~ **Đã xác nhận ngoài workspace:** SRT cạnh MP4, cùng basename 100%; cần copy/mount vào workspace để kiểm tra runtime.
3. ~~Đường bay nadir hay xiên; bay tim đường hay lệch một bên; độ cao và tốc độ?~~ **Đã chốt SOP:** nadir −90°±2°, waypoint, H mục tiêu 10 m, V mục tiêu 3.5 m/s.
4. Ngưỡng FP/km và recall crack tối thiểu để kỹ sư chấp nhận là bao nhiêu?
5. Ai là người gán và người duyệt ground truth; cần bao nhiêu người review độc lập?
6. Có cho phép dùng detector/segmentation pretrained ngoài YOLO không?
7. Có được gửi crop lên provider VLM nào; dữ liệu nào không được rời máy?
8. Cache local tối đa bao nhiêu GB; Drive sync bằng công cụ nào?
9. Các lớp `edge_break`, `bong_troc`, `standing_water` có đủ ảnh thật để train chưa?
10. Severity nội bộ sẽ dùng mấy mức và tiêu chí kỹ sư nào để hiệu chỉnh?
11. Sai số GPS chấp nhận trong báo cáo sàng lọc là bao nhiêu mét?
12. Khi không có SRT hoặc GSD, báo cáo mong muốn hiển thị gì?
13. Một candidate cần người duyệt trước khi xuất sang Backend ở mức nào?
14. Chuyến bay SOP tiếp theo có thể quay bổ sung cảnh nứt rõ, bóng và khe nối không? **Đã được phép; còn chốt ngày và tuyến.**
