# 10 — Kế hoạch triển khai MVP

> Cập nhật dữ liệu 2026-10-22: P0 cần xét hợp nhất 7 basename video quan sát ở hai nơi, gồm 5 cặp SRT đã xác minh. Xem [audit DJI 04-10](18_DJI_SURVEY_20261004_AUDIT.md); không tự bỏ 0057/0064.

## P0 — Khóa baseline và dữ liệu thật

1. Kiểm kê 4 MP4, tìm/ghép SRT, ghi manifest và thông số drone/camera.
2. Trích frame theo sampling cố định; chạy quality report.
3. Chạy model hiện tại để tạo false-positive inbox.

Lệnh P0.1 hiện có:

```powershell
python tools/audit_survey_assets.py --root data/raw_videos --output outputs/survey_manifest_dji_mini2se.json
```

Lệnh không tự ghép SRT theo thứ tự; chỉ chấp nhận basename khớp và báo `missing_srt`/`ambiguous_srt` rõ ràng.

Khi SRT đã ghép được, manifest tự kiểm tra từng block bắt buộc có GPS, độ cao/barometer và gimbal pitch trong `[-92°, -88°]`, độ cao trong `[8 m, 12 m]`, timestamp đơn điệu. Không có trường nào được thay bằng default âm thầm.

## P1 — Road gate

1. Gán polygon road surface cho tập đại diện.
2. Fine-tune/đánh giá road segmentation.
3. Chặn candidate ngoài mask; thêm test leakage.

## P2 — Detector/domain adaptation

1. Gán nhãn sáu lớp MVP trên crop có context.
2. Bổ sung hard negatives và split theo survey.
3. Train model mới; benchmark per-class, FP/km và recall crack.

## P3 — Temporal và ID

1. Tích hợp tracker.
2. Viết merge policy và schema candidate.
3. Replay video, kiểm đếm thủ công, đo duplicate/missed rate.

## P4 — Review có điều kiện

1. Rule-based triage trước.
2. VLM batch cho vùng xám/hard negative.
3. Cache, provenance và fallback khi VLM lỗi.

## P5 — Field pilot

1. Chạy video thật end-to-end.
2. Kỹ sư review candidate và đo lại mẫu.
3. Chỉ phát hành model khi các gate 09 đạt; nếu chưa đạt, phát hành dưới nhãn pilot.

## Definition of Done

MVP đạt khi có model/domain holdout đạt ngưỡng đã phê duyệt, road gate chặn vật ngoài đường, tracking không đếm trùng, provenance đầy đủ và kỹ sư xác nhận kết quả trên video thật. Code chạy exit 0 một mình không đủ.
