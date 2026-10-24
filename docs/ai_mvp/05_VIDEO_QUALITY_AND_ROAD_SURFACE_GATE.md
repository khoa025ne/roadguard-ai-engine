# 05 — Video quality và road-surface gate

## Quality gate tối thiểu

- Đọc được codec, resolution, FPS, duration.
- Có timestamp đơn điệu; SRT phải đồng bộ hoặc trạng thái `missing/mismatch`.
- Blur/exposure được đo theo frame; frame lỗi không đưa vào train/inference chính.
- Góc nhìn và độ cao phải được ghi trong manifest; không giả định camera nếu chưa xác minh.

## Road mask gate

Với mỗi detection, tính:

`road_overlap = area(bbox ∩ road_mask) / area(bbox)`

Candidate chỉ đi tiếp khi `road_overlap >= threshold` được calibrate trên validation thật. Nếu mask chạm cây/cỏ hoặc mask không liên tục, đánh dấu `mask_uncertain` và không auto-accept.

## Cải thiện road model

Fine-tune road segmentation bằng frame thật của dự án, có polygon mép đường và các ca cỏ/cây che mép. Benchmark phải báo mIoU, leakage vào vegetation và tỷ lệ loại đúng vùng ngoài đường; con số proxy không được gọi là ground-truth accuracy.

## SOP bay đề xuất

Bay gần nadir, tốc độ ổn định, tránh nắng xiên mạnh, ghi lại camera/độ cao/FPS/shutter và luôn giữ file SRT. Đây là điều kiện dữ liệu giúp model tốt hơn, không phải thay thế quality gate.

## Profile DJI Mini 2 SE đã chốt

Với `2720×1530`, sensor rộng `6.17 mm`, tiêu cự thực `4.26 mm`, công thức thực dụng là:

`GSD_mm_per_px = H_m × 1000 × 6.17 / (4.26 × 2720)`.

Kết quả xấp xỉ:

| Cao độ | GSD |
|---:|---:|
| 8 m | 4.26 mm/px |
| 10 m | 5.33 mm/px |
| 12 m | 6.39 mm/px |

Đây là giới hạn độ phân giải cho phép đo. Detector vẫn có thể phát hiện cấu trúc lớn hơn vài pixel, nhưng không được tuyên bố đo chính xác crack hairline ở dưới ngưỡng này. Nếu mục tiêu bắt buộc là `≤2 mm/px`, cần bay khoảng `3.75 m` với cùng camera hoặc dùng camera/sensor khác; quyết định này phải qua safety review, không tự suy ra từ pipeline.
