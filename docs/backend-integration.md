# Tích hợp backend RoadGuard

Khởi động Detection Studio theo README. Các route dưới đây dùng tiền tố `/api/mvp-video` trên loopback. API trả JSON, ngoại trừ UI và route tải file. Backend gọi từ máy chủ RoadGuard hoặc thông qua lớp dịch vụ đã xác thực và phân quyền. Worker legacy `src.api.worker_service` là interface khác cho manifest; job Studio dùng API dưới đây.

| Bước | Request | Kết quả |
| --- | --- | --- |
| Cấu hình | `GET /config`, `GET /models` | Model ID, task, classes, version, trạng thái khả dụng và mặc định |
| Tải lên | `POST /upload`, multipart `file`, `prepare_only`, `sample_fps`, `crack_model`, `pothole_model`, `road_mask_enabled`, `segment_model` | `{job_id}`. `Idempotency-Key` dùng lại khi file và cấu hình giống nhau |
| Khởi chạy | `POST /{job_id}/start` | Job ở READY chuyển sang QUEUED |
| Theo dõi | `GET /{job_id}`, `GET /{job_id}/logs?after=0`, `GET /jobs` | Trạng thái, tiến độ, sự kiện, kết quả và lỗi |
| Hủy | `POST /{job_id}/cancel` | Ghi nhận yêu cầu hủy |
| Tải kết quả | `GET /{job_id}/files/analysis.json` | `models`, `frames`, `detections`, `road_mask`, `summary`, `limitations` |
| Review Queue | `GET /{job_id}/review-queue/` | Giao diện duyệt trên đúng phiên chạy |
| Revision | `GET /{job_id}/review-queue/api/state`, `POST /{job_id}/review-queue/api/review` | Snapshot hiện tại hoặc revision mới có audit |
| Báo cáo | `POST /{job_id}/report/local`, hoặc `POST /{job_id}/review-queue/api/report/{draft,ready,approve}` | Báo cáo thống kê AI hoặc phiên bản báo cáo do người dùng duyệt |
| CKEY | `GET /ckey/models`, `GET /{job_id}/ckey/preview`, `POST /{job_id}/ckey/{vision,report}` | Cấu hình, dự toán, kết quả AI lưu theo run |

```bash
BASE=http://127.0.0.1:8080/api/mvp-video
curl -fsS "$BASE/config"
curl -fsS -H 'Idempotency-Key: example-run-1'   -F 'file=@sample.mp4' -F 'prepare_only=true' -F 'sample_fps=2'   -F 'road_mask_enabled=true' "$BASE/upload"
# Gán JOB_ID từ phản hồi upload.
curl -fsS -X POST "$BASE/$JOB_ID/start"
curl -fsS "$BASE/$JOB_ID"
curl -fsS "$BASE/$JOB_ID/files/analysis.json"
```

Luồng trạng thái là `UPLOADING → READY → QUEUED → RUNNING → COMPLETED`. Job có thể kết thúc ở FAILED, CANCELLED hoặc INTERRUPTED. Backend kiểm tra HTTP status và đọc `detail` hoặc `error` với `code`, `message`, `stage` khi có. Lỗi thường gặp gồm 403 ngoài loopback, 404 job/file không tồn tại, 409 xung đột revision hoặc idempotency, 422 dữ liệu/model không hợp lệ, 429 hàng đợi đầy, và 507 thiếu dung lượng. Với lỗi mạng, đọc lại trạng thái trước khi gửi lại.

Detection có `frame`, `timestamp_s`, `class_name`, `bbox` theo pixel, `confidence` và provenance model. Khi bật Road Mask, frame có trạng thái dự đoán/thiếu mask cùng tên file nếu có, và detection có `road_overlap`/cảnh báo. Studio gửi `detection_mode=FT95`, `Vision` hoặc `FT95 + Vision`. Với client cũ, chọn FT95 bằng cùng ID cho `crack_model` và `pothole_model`; cặp legacy dùng hai ID riêng. Segmentation dùng ID có task SEGMENT.

Khi gửi review, lấy `state.revision` làm `base_revision`, cung cấp `reviewer`, `confirm:true` và danh sách quyết định `items`, `coverage` hoặc `resolutions`. Duyệt box không xác nhận phạm vi. Report draft gắn với revision review. Bước ready và approve chỉ nhận revision report hiện hành, và approve yêu cầu `accept_limits:true`. Báo cáo approved lưu riêng theo phiên bản.

CKEY Vision nhận `{"confirm_paid":true,"mode":"FT95 + Vision"}` sau khi người dùng đồng ý gửi dữ liệu. Vision chỉ nhận frame của job đã hoàn tất ở luồng hiện tại. Report CKEY cần xác minh riêng và chỉ xuất draft. AI proposal được lưu tách khỏi GT. Backup dữ liệu dưới `results/mvp_video28/` theo chính sách của backend, gồm kết quả AI, revision review, báo cáo và lịch sử sự kiện.

Với AI Report, đọc `GET /{job_id}/ckey/report/preview` để nhận nội dung gửi và `input_revision`. Gửi `POST /{job_id}/ckey/report` cùng `confirm_paid: true` và token revision vừa nhận. Một lượt dùng một request văn bản. Đọc lại trạng thái qua `GET /{job_id}/ckey/report` hoặc tải bản nháp gần nhất với `?download=true`. Contract báo cáo hiện chưa được xác minh trực tiếp.
