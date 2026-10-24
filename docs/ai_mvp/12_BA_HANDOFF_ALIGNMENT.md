# 12 — Handoff với BA/Backend

## AI cung cấp

AI cung cấp candidate detection, evidence frame/crop, timestamp, telemetry status, model/config provenance, road overlap, track/defect ID đề xuất, estimate có cờ chất lượng và review suggestion.

## AI không cung cấp

AI không tự tạo Defect nghiệp vụ, không quyết định KEEP_NEW/LINK_EXISTING/REJECT, không duyệt sửa chữa, không thay thế FIELD measurement và không coi GIS road segment là pixel road mask.

## Contract principles

- Backend giữ source file identity, job/attempt, manifest hash, model/config pins và callback admission.
- Candidate phải idempotent và replay được.
- Late/replayed result phải bị fencing theo attempt.
- Missing/corrupt video hoặc SRT phải là trạng thái lỗi rõ ràng, không hoàn thành giả.
- E2E provider/deployment chưa được tuyên bố đạt cho tới khi chạy bằng artifact thật.

## Trạng thái hiện tại

Đây là tài liệu handoff/định hướng AI. Các hợp đồng tích hợp cụ thể cần BA/Backend xác nhận trước khi code adapter production.
