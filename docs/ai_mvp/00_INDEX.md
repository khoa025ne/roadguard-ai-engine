# RoadGuard AI — AI MVP Canonical Documentation

**Ngày cập nhật:** 2026-10-22
**Phạm vi:** AI/data/inference; không thay thế Backend, Frontend hay nghiệp vụ FIELD.

## Mục tiêu

RoadGuard AI hỗ trợ kỹ sư hiện trường sàng lọc hư hỏng đường bê tông xi măng và nghiệm thu bảo hành từ video flycam. AI tạo **candidate có bằng chứng và provenance**; kỹ sư/Backend mới quyết định Defect cuối cùng, đo thực địa và xử lý sửa chữa.

## Thứ tự đọc

1. [Scope và quyết định đã chốt](01_SCOPE_AND_DECISIONS.md)
2. [Audit trạng thái hiện tại](02_CURRENT_STATE_AUDIT.md)
3. [Kiến trúc mục tiêu](03_TARGET_AI_ARCHITECTURE.md)
4. [Kế hoạch dữ liệu và gán nhãn](04_DATA_AND_LABELING_PLAYBOOK.md)
5. [Quality gate và road-surface gate](05_VIDEO_QUALITY_AND_ROAD_SURFACE_GATE.md)
6. [Tracking, merge và defect ID](06_DETECTION_TRACKING_AND_DEFECT_ID.md)
7. [Chính sách VLM](07_VLM_REVIEW_POLICY.md)
8. [Kho Google Drive và manifest](08_GOOGLE_DRIVE_STORAGE_AND_MANIFEST.md)
9. [Evaluation gates](09_EVALUATION_GATES.md)
10. [Kế hoạch triển khai MVP](10_MVP_IMPLEMENTATION_PLAN.md)
11. [Câu hỏi mở](11_OPEN_QUESTIONS.md)
12. [Handoff với BA/Backend](12_BA_HANDOFF_ALIGNMENT.md)
13. [Execution checklist và bằng chứng nghiệm thu](13_EXECUTION_CHECKLIST.md)
14. [Kế hoạch tài nguyên và dữ liệu train](14_DATA_ACQUISITION_AND_RESOURCE_PLAN.md)
15. [Field data collection pack](15_FIELD_DATA_COLLECTION_PACK.md)
16. [Dataset readiness report](16_DATASET_READINESS_REPORT.md)
17. [RG-AI-P0-01 — Kiểm kê AI workspace và baseline](17_RG_AI_P0_01_WORKSPACE_AUDIT.md)
18. [Khảo sát DJI 04-10 — file gốc và telemetry](18_DJI_SURVEY_20261004_AUDIT.md)
19. [RG-AI-DATA-03 — kế hoạch dữ liệu crack detection + segmentation](19_RG_AI_DATA_03_CRACK_DATA_PLAN.md)
20. [RG-AI-DATA-04 — batch pilot 20 ảnh DJI và hướng dẫn gán nhãn](20_RG_AI_DATA_04_PILOT.md)
21. [RG-AI-DATA-05 — mở batch 20 ảnh và gán nhãn thử](21_RG_AI_DATA_05_ANNOTATION_HANDOFF.md)

Mẫu manifest: [templates/survey_manifest.example.json](templates/survey_manifest.example.json)

## Quy ước bằng chứng

- `CURRENT_VERIFIED`: quan sát được trong worktree hoặc lệnh kiểm tra đã chạy.
- `HISTORICAL`: ghi trong log/tài liệu cũ, chưa chạy lại trong phiên này.
- `PROPOSED`: thiết kế mục tiêu, chưa phải tính năng đã có.
- `NOT_VERIFIED`: chưa có bằng chứng đủ mạnh.

`docs/project_export/` được giữ nguyên làm tài liệu lịch sử; không dùng làm nguồn sự thật mới.
