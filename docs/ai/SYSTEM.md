# RoadGuard AI — tóm tắt hệ thống (kiểm tra 2026-10-22, HEAD `82ae0dc` + thay đổi chưa commit)

- Mục đích MVP: sàng lọc candidate hư hỏng đường bê tông từ video DJI; kỹ sư duyệt và đo FIELD. Quyết định nghiệp vụ: `docs/ai_mvp/01_SCOPE_AND_DECISIONS.md`.
- Luồng code hiện tại: `src/pipeline/pipeline.py` lấy frame/SRT, rồi 7 stage trong `src/pipeline/stages/`; parser `src/ingestion/srt_parser.py`; báo cáo `src/pipeline/stages/07_report.py`. Cấu hình: `configs/pipeline.yaml`.
- Nguồn khảo sát: `F:\video-flycam ngày 04-10`; 5 cặp `DJI_0059`–`DJI_0063` được kiểm kê tại `docs/ai_mvp/manifests/dji_20261004.json`. Video nguồn 1080p/29.97 fps, không phải cấu hình video mục tiêu 2.7K. Không sửa/xóa file gốc.
- Quy tắc telemetry sau DATA-02: GPS SRT là kinh độ, vĩ độ; `H`/`D` được giữ nguyên có provenance, không phải AGL. Thiếu AGL/pitch đáng tin thì không tính GSD/kích thước hoặc tọa độ khuyết tật mặt đất. `null` nghĩa là chưa có dữ liệu, không phải 0.
- Tích hợp: AI tạo candidate/bằng chứng; Backend/Frontend ngoài phạm vi việc này. `src/api/worker_service.py` vẫn có nhánh worker mock (chưa chứng minh E2E thật); không coi pass unit test là đạt MVP.
- Test: `python -m unittest discover -s tests -q`; test telemetry riêng: `python -m unittest tests.test_dji_telemetry_safety -q`.
- Gaps: flight log/AGL/pitch/orientation chưa xác minh, GPS SRT chỉ khoảng 4 chữ số thập phân; cần Gate D và field evaluation trước khi công bố vị trí/kích thước tin cậy. Xem `docs/ai_mvp/09_EVALUATION_GATES.md`.
- Dữ liệu crack (DATA-03): `data/merged` có YOLO box public/legacy nhưng chưa có mask crack DJI được review; split/nguồn nhãn chưa đủ để làm holdout domain. Kế hoạch chọn frame, nhãn và thí nghiệm ở `docs/ai_mvp/19_RG_AI_DATA_03_CRACK_DATA_PLAN.md` (chỉ thiết kế, chờ duyệt).
- Pilot DATA-04: 20 ảnh DJI có hash/provenance tại `data/pilots/crack_dji_20261022_batch01/`; 0 bbox/mask được gán, 0 approved. Nhiều ảnh xiên so với SOP nadir; xem `docs/ai_mvp/20_RG_AI_DATA_04_PILOT.md` trước khi mở rộng 120/40.
- DATA-05: giao diện gán box cục bộ `tools/annotate_dji_crack_pilot.py` cho đúng batch 20, lưu revision trong `data/` (Git ignore), có trạng thái draft/review và chặn duyệt 7 ảnh xiên vào nhánh nadir. Hướng dẫn tại `docs/ai_mvp/21_RG_AI_DATA_05_ANNOTATION_HANDOFF.md`; mask cần công cụ riêng, chưa có ground truth được duyệt.
