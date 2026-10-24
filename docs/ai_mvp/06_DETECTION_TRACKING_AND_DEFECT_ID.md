# 06 — Detection, tracking và defect ID

## Ba loại ID

- `survey_id = SHA256(video_sha256 + srt_sha256 + flight_metadata)`.
- `track_id`: ID tạm trong một video, do ByteTrack/OC-SORT hoặc tracker tương đương.
- `defect_id`: ID ổn định sau khi merge và review; không dùng số thứ tự frame.

## Merge trong một survey

Gộp các observation khi cùng class tương thích, track liên tục, khoảng cách tâm/bbox phù hợp, appearance tương đồng và GPS cục bộ không mâu thuẫn. Giữ observation có chất lượng cao nhất làm `best_evidence_frame`; không cộng số lượng frame thành số defect.

## Merge giữa nhiều survey

Ưu tiên road section + lý trình tương đối + độ lệch tim + mốc tấm bê tông. GPS dân sự chỉ là tín hiệu hỗ trợ. Nếu không đủ neo, tạo `possible_match` để người duyệt, không tự gộp.

## Schema candidate tối thiểu

```json
{
  "defect_id": "survey-route-station-seq",
  "track_id": "t-001",
  "class": "crack",
  "status": "candidate|needs_review|rejected|accepted_by_human",
  "first_seen_ts": 12.4,
  "best_evidence_frame": "frames/000372.jpg",
  "bbox": [x1, y1, x2, y2],
  "road_overlap": 0.93,
  "gps": {"lat": null, "lon": null, "quality": "missing"},
  "size_estimate": {"value": null, "unit": "cm", "quality": "unverified"},
  "model_version": "...",
  "config_hash": "...",
  "provenance": {"video_sha256": "...", "frame_ts": 12.4}
}
```
