# 13 — Execution checklist và bằng chứng nghiệm thu

Tài liệu này biến kế hoạch MVP thành checklist có thể giao việc. Mỗi dòng chỉ được đánh dấu hoàn thành khi artifact hoặc lệnh kiểm tra tương ứng tồn tại.

## P0 — Intake và baseline

| ID | Việc | Artifact bắt buộc | Trạng thái hiện tại |
|---|---|---|---|
| P0.1 | Kiểm kê MP4/SRT | `survey_manifest.json`, SHA256 | Chưa đủ; workspace có 4 MP4, chưa thấy SRT |
| P0.2 | Xác minh camera/drone | `camera_profile.json` | Chưa xác minh |
| P0.3 | Chạy quality gate | `quality_report.json` + frame mẫu | Code có khung; chưa có fresh run |
| P0.4 | Baseline detector | `baseline_metrics.json` | Chưa có đánh giá AP/FP trên domain thật |
| P0.5 | False-positive inbox | `hard_negative_manifest.jsonl` | Chưa tạo từ toàn bộ survey |

## P1 — Road gate

| ID | Việc | Artifact bắt buộc | Gate |
|---|---|---|---|
| P1.1 | Gán mask đường | dataset mask + reviewer log | Có người gán/review độc lập |
| P1.2 | Đánh giá road model | `road_seg_metrics.json` | mIoU/Dice và leakage tách riêng |
| P1.3 | Áp mask vào detector | config + unit tests | Candidate ngoài mask không được confirmed |
| P1.4 | Kiểm tra mép/khe | hard-negative report | Không xóa nhầm defect thật ở mép |

## P2 — Detector và hard negatives

| ID | Việc | Artifact bắt buộc | Gate |
|---|---|---|---|
| P2.1 | Chốt taxonomy sáu lớp | `taxonomy_v1.json` | BA/nghiệp vụ duyệt |
| P2.2 | Gán nhãn domain thật | dataset manifest + label QA | Split theo video/survey |
| P2.3 | Train candidate model | model card + checkpoint hash | Có dataset/config/code ref |
| P2.4 | Đánh giá holdout | per-class metrics, confusion | Có FP/km và recall crack |

## P3 — Tracking và ID

| ID | Việc | Artifact bắt buộc | Gate |
|---|---|---|---|
| P3.1 | Replay tracker | track JSONL + video overlay | Có track persistence |
| P3.2 | Unique count audit | manual count sheet | Sai lệch so với người kiểm đếm trong ngưỡng đã chốt |
| P3.3 | Sinh defect ID | candidate schema + deterministic test | Chạy lại cùng input cho cùng ID |
| P3.4 | Merge giữa survey | match report | Ca mơ hồ thành `possible_match`, không tự gộp |

## P4 — VLM có điều kiện

| ID | Việc | Artifact bắt buộc | Gate |
|---|---|---|---|
| P4.1 | Tạo vùng confidence xám | routing metrics | VLM không nhận mọi crop |
| P4.2 | JSON schema validation | request/response fixtures | Parse lỗi chuyển review, không mất candidate |
| P4.3 | Cache và chi phí | `vlm_usage.jsonl` | Có hash, model, latency, cost estimate |
| P4.4 | Fallback | offline/provider-failure test | VLM không làm pipeline hỏng |

## P5 — Pilot

| ID | Việc | Artifact bắt buộc | Gate |
|---|---|---|---|
| P5.1 | Chạy 2 tuyến holdout | run manifest + metrics | Tuyến chưa dùng khi train |
| P5.2 | Kỹ sư review | decisions JSONL | Candidate có quyết định và lý do |
| P5.3 | Đo hiện trường mẫu | field measurement sheet | Tách `estimated` và `measured` |
| P5.4 | Phát hành pilot | release manifest + report | JSON/CSV/GeoJSON/PDF nhất quán |

## Quy tắc trạng thái

- `NOT_STARTED`: chưa có artifact.
- `IN_PROGRESS`: có artifact trung gian nhưng chưa qua gate.
- `PASS`: bằng chứng đạt đúng gate.
- `BLOCKED_INPUT`: thiếu dữ liệu/quyết định bên ngoài; không được giả định giá trị.
- `REWORK`: artifact có nhưng không đạt gate.

Mọi trạng thái phải ghi ngày, commit code, người thực hiện và đường dẫn artifact. “Pipeline chạy exit 0” chỉ là bằng chứng runtime tối thiểu, không tự đóng bất kỳ gate chất lượng nào.
