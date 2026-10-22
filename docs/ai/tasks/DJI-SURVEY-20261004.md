# Handoff — khảo sát DJI 04-10

- Mục tiêu: xác minh 5 cặp `DJI_0059`–`DJI_0063` tại `F:\video-flycam ngày 04-10`, đối chiếu 4 MP4 cũ; không bỏ file, không trích frame hàng loạt/train.
- Bằng chứng: `docs/ai_mvp/18_DJI_SURVEY_20261004_AUDIT.md`, `docs/ai_mvp/manifests/dji_20261004.json` (SHA-256, metadata, timebase, GPS/H, mẫu chất lượng).
- Kết quả: 5 cặp SRT đúng phụ đề nhúng; thêm `0060/0062/0063`, giữ `0057/0064`; tất cả MP4 1080p/29.97 fps; 6 stream video full decode OK. `0062` chỉ 6 s, ảnh mẫu bị che.
- Chặn: thiếu pitch/AGL; parser runtime đảo GPS, giả định H=10 m và pitch=-90°; chưa có nhãn/flight log. Không dùng dữ liệu này để xác nhận GSD/nadir hay train MVP.
- Trạng thái: audit/manifest hoàn tất; quyết định phân loại survey và sửa parser chuyển việc tiếp theo.
