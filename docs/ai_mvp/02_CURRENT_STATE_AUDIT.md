# 02 — Audit trạng thái hiện tại

> Cập nhật 2026-10-22: nguồn `F:\video-flycam ngày 04-10` đã xác minh có 5 cặp MP4/SRT `DJI_0059`–`DJI_0063`, cộng `DJI_0064.MP4` chưa có SRT rời. Xem [audit mới và manifest](18_DJI_SURVEY_20261004_AUDIT.md). Các phát biểu “chưa mount được nguồn” bên dưới là trạng thái lịch sử, không còn là kết luận mới nhất.

## Bằng chứng đã quan sát

- Có pipeline 7 stage tại `src/pipeline/stages/01_segment.py` đến `07_report.py`.
- Có road segmentation checkpoint `weights/pretrained/yolo11m-road-seg.pt` (~43.12 MB).
- Có detector checkpoints: `roadguard_best_15k.pt`, `roadguard_multiclass_v1_best.pt`, crack-only và pothole-only.
- Có 4 video MP4 trong `data/raw_videos/`, tổng khoảng 4.19 GB.
- Có các module ingestion, tiling, curation, tracking, measurement và reporting.
- Handoff BA xác định AI chỉ tạo candidate; Backend/PM/Crew giữ quyết định nghiệp vụ.
- Regression suite hiện chạy được bằng `python -m unittest discover -s tests -q`: **24 tests, 24 OK, 18.957 giây** (`CURRENT_VERIFIED`). Đây là bằng chứng cho contract/scaffold, không phải bằng chứng model đạt chất lượng field.
- Người dùng đã xác nhận camera/flight profile và cặp SRT theo basename; trong môi trường chạy hiện tại chỉ xác minh được 4 MP4 tại `data/raw_videos/`, còn `F:\video-flycam` chưa tồn tại/mount được (`USER_CONFIRMED_EXTERNAL`, runtime copy chưa hoàn tất).
- Tính lại GSD DJI Mini 2 SE ở 10 m cho 2720 px ngang cho kết quả khoảng **5.33 mm/px**; SOP cũ ghi `≤2.0 mm/px` là mâu thuẫn cần sửa trước khi chốt gate đo nứt.
- Tool P0 `tools/audit_survey_assets.py` đã chạy trên workspace và tạo manifest 4 asset; cả 4 có trạng thái `missing_srt` trong runtime hiện tại, đúng với nguyên tắc không giả định telemetry.
- Tool đã có validator SRT theo SOP: GPS, altitude/barometer, gimbal pitch và timestamp; các block thiếu trường sẽ fail rõ ràng thay vì dùng giá trị mặc định.

## Chưa được chứng minh

- Chất lượng model trên video flycam thật theo FP/km và recall crack.
- SRT tương ứng với 4 MP4 trong workspace.
- GSD với đúng camera/drone thật.
- E2E gọi real checkpoint qua worker/provider.
- Đánh giá AP/precision/recall trên holdout video thật; test suite hiện chưa bao phủ chất lượng detection theo km.
- Config mặc định vẫn trỏ `weights/trained/roadguard_best_15k.pt` (2 lớp), chưa trỏ model đa lớp mới.
- `src/api/worker_service.py` còn nhánh `MockAIAdapter`; chưa phải bằng chứng worker production chạy real YOLO.
- Model `bong_troc` có dữ liệu huấn luyện đủ; tài liệu cũ ghi lớp nhưng dataset trước đây thiếu mẫu đáng tin cậy.

## Chẩn đoán lỗi hiện tại

Model đang bị ép giải bài toán “mọi vật thể tương phản trong frame là defect”. Nguyên nhân chính là domain gap, thiếu road mask bắt buộc, hard negatives chưa đủ từ video thật, sampling/tiling chưa tối ưu và chưa có kiểm tra temporal. Hạ/nghiêng confidence chỉ đổi tỷ lệ lỗi, không giải quyết nguyên nhân.

## Kết luận tiến độ

**Pipeline scaffold: gần hoàn thiện. Model MVP: chưa đạt. Data/E2E nghiệm thu: chưa xác minh.** Không được ghi “MVP hoàn tất” trước khi đóng các evaluation gate trong tài liệu 09.
