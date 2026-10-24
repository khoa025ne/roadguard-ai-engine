# 01 — Scope và quyết định

## Đã chốt

| Chủ đề | Quyết định |
|---|---|
| Người dùng | Kỹ sư hiện trường |
| Mục đích | Sàng lọc sửa chữa và nghiệm thu bảo hành |
| Mặt đường | Bê tông xi măng; asphalt ngoài MVP |
| Lớp bắt buộc | `pothole`, `crack`, `bong_troc`, `edge_break`, `joint_gap`, `standing_water` |
| Phân loại crack | Không bắt buộc trong MVP; kỹ sư nhận biết từ crop |
| Độ sâu/kích thước | AI chỉ ước tính; đo FIELD là giá trị nghiệm thu |
| Quyền quyết định | AI không auto-accept; tạo candidate để review |
| VLM | Dùng có điều kiện, ưu tiên chi phí thấp |
| Hệ thống ngoài AI | Không triển khai BE/FE trong phạm vi này |
| Lưu trữ | Google Drive cá nhân Google One 5 TB + local cache |

## Hồ sơ thiết bị và bay đã xác nhận

- Drone/camera: **DJI Mini 2 SE**, cảm biến 1/2.3" CMOS, sensor `6.17 × 4.55 mm`.
- Video chuẩn: `2720 × 1530`, `30 fps`; tiêu cự thực `4.26 mm` (tương đương 24 mm).
- Góc bay: nadir `-90° ±2°`; waypoint, cao độ mục tiêu `10 m`, tốc độ mục tiêu `3.5 m/s`.
- File gốc: `DJI_0057`, `DJI_0059`, `DJI_0061`, `DJI_0064`; quy tắc ghép MP4/SRT là cùng basename 100%.
- Cập nhật 2026-10-22: thư mục nguồn thực tế là `F:\video-flycam ngày 04-10`. Đã xác minh 5 cặp MP4/SRT `DJI_0059`–`DJI_0063`; `DJI_0064` có MP4 nhưng thiếu SRT rời; `DJI_0057` chỉ có MP4 trong workspace. Xem [audit DJI mới](18_DJI_SURVEY_20261004_AUDIT.md). `data/raw_videos/` hiện vẫn chỉ chứa 4 MP4 và không có SRT.

## Hiệu chỉnh GSD bắt buộc

Với thông số trên, tại `H=10 m`:

`GSD_mm_per_px = H_m × 1000 × sensor_width_mm / (focal_length_mm × image_width_px) ≈ 5.33 mm/px`.

Vì vậy tuyên bố GSD `≤2.0 mm/px` trong một số SOP cũ là **không phù hợp với cấu hình 2.7K này**. Không dùng ngưỡng đó để nghiệm thu; nứt nhỏ hơn khoảng 2–3 pixel GSD phải gắn `NOT_MEASURABLE` hoặc cần bay thấp hơn/đổi camera.

## Nguyên tắc kỹ thuật

1. Không dùng confidence đơn lẻ để chữa lỗi domain.
2. Candidate ngoài vùng mặt đường hợp lệ bị loại trước khi tạo kết quả.
3. Bbox không được gọi là số đo vật lý.
4. Mỗi kết quả phải truy nguyên tới video, frame, timestamp, model và config.
5. Không có SRT/GSD tin cậy thì ghi rõ `telemetry_missing`, không bịa GPS/kích thước.

## Taxonomy MVP

- `pothole`: hố/lõm phá vỡ mặt tấm, ưu tiên cao.
- `crack`: đường nứt nhìn thấy trên bề mặt.
- `bong_troc`: mất lớp bề mặt, mẻ/tróc nông; phân biệt với pothole bằng hình thái và độ lõm chỉ ở mức gợi ý.
- `edge_break`: vỡ mép tấm/lề.
- `joint_gap`: khe nối/co giãn; mặc định là hard negative nếu không có dấu hiệu hư hỏng kèm theo.
- `standing_water`: nước đọng; cần gắn cờ kiểm tra vì phản xạ dễ gây false positive.

Các vật thể `tree`, `vegetation`, `vehicle`, `person`, `shadow`, `glare`, `debris` là **exclusion/hard-negative**, không phải defect.
