# 04 — Data và gán nhãn

## Dataset cần xây

Tạo dataset theo survey/route, không trộn ngẫu nhiên frame liền kề giữa train và test. Split theo **video hoặc chuyến bay**, tránh leakage cùng một đoạn đường xuất hiện ở hai tập.

### Nhãn bắt buộc

- polygon/mask `road_surface`;
- bbox hoặc polygon sáu lớp defect;
- exclusion/hard-negative: vegetation, person, vehicle, shadow, glare, debris, joint_gap_clean;
- quality tags: blur, low_light, overexposure, wet_surface, oblique_view;
- frame timestamp, survey_id, source video, telemetry status.

## Quy trình hard-negative mining

1. Chạy model hiện tại trên toàn bộ 4 video.
2. Thu mọi false positive cây/bóng/xe/người/khe nối.
3. Kỹ sư gán `hard_negative` hoặc sửa thành defect thật.
4. Đưa 70–80% vào train, giữ 20–30% theo video khác làm holdout.
5. Train lại, so sánh FP/km và recall crack trước khi thay model production.

## Sampling

Giữ frame cách nhau đủ để không sao chép gần như cùng một ảnh; trích thêm burst quanh candidate để gán track. Crop detector phải có context, không chỉ crop sát bbox.

## Chất lượng nhãn

Mỗi positive cần người gán và người review độc lập. Các ca không thể phân biệt crack/bong_troc từ ảnh phải gắn `ambiguous`, không ép nhãn. `joint_gap_clean` và bóng cây là negative bắt buộc.
