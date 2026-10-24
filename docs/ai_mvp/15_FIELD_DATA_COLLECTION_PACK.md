# 15 — Field data collection pack

Tài liệu này là gói hướng dẫn thực địa cho chuyến bay bổ sung và chuẩn bị dữ liệu train. Nó dành cho người vận hành chưa cần biết sâu về AI.

## A. Mỗi survey cần nộp

```text
{SURVEY_ID}/
  raw/
    DJI_XXXX.MP4
    DJI_XXXX.SRT
  metadata.json
  flight_checklist.md
  field_measurements.csv
```

Không đổi tên MP4/SRT sau khi ghi; nếu phải đổi, giữ checksum và basename mapping trong manifest.

## B. Checklist trước khi bay

- [ ] Camera: DJI Mini 2 SE; video profile đã ghi lại.
- [ ] Độ phân giải/FPS đã kiểm tra trên app; không dùng bản preview.
- [ ] Gimbal `−90° ±2°`.
- [ ] Cao độ mục tiêu 10 m; cho phép 8–12 m.
- [ ] Tốc độ mục tiêu 3.5 m/s.
- [ ] Waypoint bám tuyến; không bay tay.
- [ ] Bật Video Subtitles/SRT.
- [ ] Pin, thẻ nhớ, vùng an toàn và dây điện đã kiểm tra.
- [ ] Mặt đường khô, ánh sáng không tạo bóng quá dài.
- [ ] Ghi mã tuyến, ngày giờ, người vận hành.

## C. Cách quay để có dữ liệu train

Mỗi tuyến nên có hai nhóm đoạn:

1. **Coverage pass:** bay liên tục toàn tuyến theo SOP.
2. **Evidence pass:** quay/chậm lại quanh các vị trí có nứt, ổ gà, bong tróc, mép vỡ, khe nối và nước đọng; giữ hư hỏng ở giữa vùng đường trong nhiều frame.

Không cần cố tạo hư hỏng giả. Hãy quay cả nền sạch, bóng cây, xe, người, lá/rác và khe nối bình thường vì đó là dữ liệu chống false positive.

## D. Phiếu đo thực địa

Mỗi hư hỏng được chọn làm ground truth nên có một dòng:

```csv
survey_id,route_id,station,lat,lon,class,observed_length_cm,observed_width_cm,depth_cm,field_severity,photo_ref,reviewer,notes
```

Quy tắc:

- Đo bằng thước/thiết bị ngoài hiện trường nếu có.
- `depth_cm` để trống nếu chưa đo; không suy ra từ bbox.
- Nếu không chắc là crack hay bong tróc, ghi `ambiguous` và note lý do.
- Gắn `photo_ref` tới ảnh/clip bằng chứng.

## E. Gói frame giao cho người gán nhãn

Từ mỗi video tạo ba loại dữ liệu:

- `overview/`: frame cách nhau 1–2 giây để đánh dấu tuyến và road mask.
- `bursts/`: 5–10 frame liên tiếp quanh candidate để đánh giá tracking.
- `hard_negatives/`: cây, bóng, xe, người, rác, khe nối sạch, lóa, mặt đường ướt.

Người gán không cần gán mọi frame trùng. Gán keyframe rõ nhất và liên kết burst bằng `track_group_id`.

## F. Quy tắc gán nhãn

### Road surface

Vẽ polygon toàn bộ phần mặt đường bê tông nhìn thấy. Không vẽ lên cỏ, nhà, xe hoặc sân ngoài đường. Nếu bị che quá nhiều, gắn `road_mask_uncertain`.

### Defect

- `pothole`: vùng lõm/hố lớn, ảnh hưởng rõ tới mặt tấm.
- `crack`: đường nứt nhìn thấy; không ép nhãn nếu chỉ là bóng/khe sạch.
- `bong_troc`: mất/tróc lớp bề mặt nông; không gộp vào pothole nếu chưa có lõm lớn.
- `edge_break`: vỡ mép tấm/lề.
- `joint_gap`: chỉ gán defect khi khe nối bị hư hỏng; khe nối đều, sạch là `clean_joint` negative.
- `standing_water`: nước đọng; luôn gắn `needs_field_check`.

### Exclusion/hard negative

Gắn tag cho cây/cỏ, bóng cây/dây điện, xe, người, rác/lá, lóa, vệt dầu, vệt bánh và khe nối bình thường. Không biến chúng thành class defect.

## G. Review nhãn

1. Annotator gán nhãn.
2. Reviewer kỹ thuật kiểm tra road mask và class.
3. Ca mơ hồ chuyển `ambiguous`, không tự đoán.
4. Export manifest gồm người gán, reviewer, thời gian, version taxonomy.

## H. Mục tiêu chuyến bay đầu tiên

Chuyến đầu không cần đủ mọi lớp. Mục tiêu là:

- 1–2 tuyến, 30–60 phút video gốc.
- Ít nhất 100 frame road mask.
- Tối thiểu 50 hard-negative frame cho mỗi nhóm cây/bóng/xe/người/khe nối.
- Tìm và đo 20–30 hư hỏng thật nếu tuyến có.
- Giữ một đoạn video nguyên vẹn làm holdout, không gán vào train.

Nếu chuyến đầu không có đủ crack thật, đó là kết quả dữ liệu cần báo cáo; không hạ threshold để tạo crack giả.
