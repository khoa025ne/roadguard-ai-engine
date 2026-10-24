# 09 — Evaluation gates

## Gate A — Data

- Split theo video/survey, không leakage.
- Có positive crack thật trên flycam và hard negatives từ chính video dự án.
- Có nhãn road mask cho holdout.

## Gate B — Model

- Báo per-class precision/recall/mAP trên holdout domain thật.
- Báo `FP/km`, `recall crack`, `road-mask leakage`, confusion với joint/shadow/vehicle.
- Không chấp nhận model chỉ có mAP dataset internet tốt.

## Gate C — Temporal/ID

- Sai số đếm defect so với kỹ sư trên video test dưới ngưỡng đã thống nhất.
- Một hư hỏng qua nhiều frame chỉ tạo một defect ID.
- Các ca không chắc chắn không bị auto-merge.

## Gate D — Provenance

100% candidate truy được video/frame/timestamp/model/config; thiếu SRT phải hiện rõ trạng thái thiếu telemetry.

## Gate E — Field acceptance

Chạy ít nhất một video thật đầy đủ, kỹ sư review toàn bộ candidate; đo kích thước/độ sâu ngoài hiện trường được lưu riêng và dùng để hiệu chỉnh, không dùng bbox làm ground truth vật lý.
