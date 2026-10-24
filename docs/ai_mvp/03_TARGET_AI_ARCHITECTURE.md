# 03 — Kiến trúc AI mục tiêu

```text
Video + SRT
  -> ingest/checksum
  -> video quality gate
  -> frame sampling + blur/exposure gate
  -> road-surface segmentation
  -> exclusion mask (vegetation/person/vehicle/shadow/glare)
  -> defect detector trên vùng hợp lệ
  -> temporal tracker
  -> candidate filter + hard-negative rules
  -> stable defect ID + best evidence frame
  -> GSD/telemetry estimate (nếu đủ dữ liệu)
  -> conditional VLM review (optional)
  -> JSON/GeoJSON/CSV/report artifact
```

## Các tầng

1. **Quality gate:** loại video không đọc được, quá mờ, quá tối/sáng, thiếu metadata.
2. **Road gate:** chỉ cho inference trong mask mặt đường bê tông; mask không đủ tin cậy thì candidate chuyển `needs_review`.
3. **Exclusion gate:** dùng detector/segmentation pretrained hoặc rule màu/hình học để loại cây, người, xe, bóng và vật ngoài đường.
4. **Defect detector:** fine-tune trên crop/patch mặt đường thật, taxonomy MVP sáu lớp.
5. **Temporal layer:** track nhiều frame, yêu cầu persistence tối thiểu trước khi tạo candidate.
6. **Review layer:** rule trước, VLM sau, người duyệt cuối.

## Quy tắc an toàn

- Không có mask đường hợp lệ: không phát hành candidate “confirmed”.
- Không có telemetry: không phát hành kích thước/GPS như số đo chính xác.
- Candidate ngoài đường hoặc chỉ xuất hiện một frame: mặc định `rejected`/`needs_review`.
- VLM không được thay đổi provenance hoặc tự tạo Defect nghiệp vụ.
