# RG-AI-DATA-04 — handoff 2026-10-22

- Mục tiêu: pilot DJI crack tối đa 120 ảnh box/quality, 40 ảnh mask crack+road; batch đầu 20, không train/public data/production changes.
- Đã làm: hash nguồn với audit; trích 20 ảnh (5 mỗi `0059/0060/0061/0063`) vào `data/pilots/crack_dji_20261022_batch01`; manifest + review queue + contact sheet + visual triage. Tool không ghi đè và tests ở `tools/prepare_dji_crack_pilot.py`, `tests/test_prepare_dji_crack_pilot.py`.
- Trạng thái: 20 ảnh chờ duyệt; 0 box, 0 mask, 0 approved, thời gian annotation chưa đo. Triage sơ bộ 6 keep/7 uncertain/7 reject do góc xiên; chưa xác nhận bất kỳ crack/negative GT nào.
- Nguồn/quy tắc/QA: `docs/ai_mvp/20_RG_AI_DATA_04_PILOT.md`, DATA-03 plan, DJI audit/manifest, scope và Gate 09. `0062` không được chọn do chất lượng chưa rõ, không bị loại khỏi nguồn.
- Cần BA/người dùng: chỉ định annotator + kỹ sư duyệt và công cụ; giải quyết ảnh xiên so với SOP, đo thời gian 20 ảnh, xác định survey/route độc lập trước split. Khi hoàn tất review mới lấy batch tiếp trong giới hạn.
- Verification: `python -m unittest tests.test_prepare_dji_crack_pilot -q` 3/3 PASS; `python -m unittest discover -s tests -q` 50/50 PASS; kiểm tra độc lập 20 hash ảnh, manifest/review queue/visual triage khớp tên và 0 annotation file PASS. Không có training/evaluation Gate được tuyên bố PASS.
