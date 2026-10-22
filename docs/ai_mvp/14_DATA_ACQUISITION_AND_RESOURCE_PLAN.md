# 14 — Kế hoạch tài nguyên và dữ liệu để train đúng scope

## Kết luận ngắn

Không cần bắt đầu bằng một dataset internet cực lớn. Với RoadGuard, dữ liệu quyết định chất lượng là video flycam đường bê tông xi măng Việt Nam và các hard negative xuất hiện đúng trong bối cảnh đó. Dataset công khai chỉ dùng để khởi tạo/pretrain, không dùng làm holdout nghiệm thu.

## 1. Việc phải xác minh trước khi gán nhãn

Metadata runtime của 4 file hiện trong workspace đang là `1920×1080`, trong khi camera profile được xác nhận là `2720×1530`. Có ba khả năng: file đã bị export/downscale, video được quay ở profile khác, hoặc metadata camera trong tài liệu không khớp file. Không được dùng GSD 2.7K cho các file 1080p trước khi xác minh.

Artifact cần lấy từ file gốc:

- MediaInfo/ffprobe: resolution, FPS, bitrate, codec, duration.
- SRT nguyên bản cùng basename.
- File gốc không qua Messenger/Zalo/YouTube hoặc re-encode.
- Screenshot/cấu hình camera và flight log nếu còn.

Quy trình thực địa chi tiết nằm trong [15_FIELD_DATA_COLLECTION_PACK.md](15_FIELD_DATA_COLLECTION_PACK.md).

## 2. Mục tiêu dữ liệu tối thiểu cho MVP

Đây là mục tiêu thực dụng cho detector/road gate, không phải số instance bắt buộc tuyệt đối:

| Hạng mục | Tối thiểu để chạy pilot | Mục tiêu trước nghiệm thu |
|---|---:|---:|
| Survey/tuyến độc lập | 4 | 8–12 |
| Frame có road mask | 800 | 2.000–3.000 |
| Polygon road surface | 500 | 1.500–2.500 |
| Pothole thật | 300 instance | 1.000+ instance |
| Crack nhìn thấy | 300 instance | 1.000–2.000 instance |
| Bong tróc/spalling | 150 instance | 500+ instance |
| Edge break | 150 instance | 500+ instance |
| Joint damage | 150 instance | 500+ instance |
| Standing water | 100 instance | 300+ instance |
| Hard negative | 1.000 frame | 5.000–10.000 frame |

Nếu một lớp chưa đạt mức tối thiểu, phải để lớp đó là `pilot/needs_more_data`, không ép train rồi tuyên bố đạt.

## 3. Dữ liệu cần thu từ mỗi chuyến bay

Mỗi tuyến nên có:

1. Video nguyên bản + SRT cùng basename.
2. Một lượt bay chuẩn theo SOP và một số đoạn có chủ đích chứa bóng cây, xe, người, khe nối, vũng nước, mép đường.
3. Frame overview cách nhau khoảng 1–2 giây để phủ tuyến.
4. Burst 5–10 frame quanh mỗi candidate để đánh giá tracking.
5. Ít nhất 20–50 hư hỏng được kỹ sư đo lại ngoài hiện trường để hiệu chỉnh severity/kích thước.
6. Ghi rõ đoạn không có hư hỏng; negative sạch có giá trị ngang positive trong bài toán giảm false positive.

## 4. Cách phân bổ frame

- Không lấy toàn bộ 30/60 fps để train; sẽ tạo hàng nghìn frame gần như giống nhau.
- Tách `survey-level split`: toàn bộ video/tuyến chỉ nằm ở train, val hoặc test.
- Train: 70% survey; validation: 15%; holdout test: 15% hoặc ít nhất 2 tuyến chưa từng train.
- Hard negative phải được tách theo tuyến; không để cùng một bóng cây xuất hiện ở train và test.
- Candidate mơ hồ giữ nguyên với nhãn `ambiguous`, không ép thành crack/pothole.

## 5. Schema nhãn bắt buộc

Mỗi frame/crop cần có:

- `road_surface` polygon/mask.
- Defect bbox hoặc polygon: `pothole`, `crack`, `bong_troc`, `edge_break`, `joint_gap`, `standing_water`.
- Exclusion/hard-negative: `vegetation`, `person`, `vehicle`, `tree_shadow`, `glare`, `debris`, `clean_joint`.
- Quality: `blur`, `underexposed`, `overexposed`, `wet`, `oblique`, `occluded`.
- `survey_id`, video basename, frame timestamp, SRT status, annotator, reviewer.

Khuyến nghị dùng CVAT hoặc Label Studio để polygon/mask và review; dataset nhỏ có thể dùng Roboflow, nhưng phải export kèm manifest và không để nền tảng tự đổi class/split mà không ghi log.

## 6. Nguồn dữ liệu và cách dùng

### A. Nguồn ưu tiên 1 — video của dự án

Đây là nguồn quyết định nghiệm thu. Từ 4 video hiện có, cần trích false positives của model cũ làm hard-negative bank ngay cả khi chưa đủ positive crack.

### B. Nguồn ưu tiên 2 — chuyến bay bổ sung

Tổ chức 4–8 survey mới theo SOP, ưu tiên các tuyến có tấm bê tông, khe nối, mép vỡ và nứt thật. Một chuyến chỉ quay nền sạch vẫn rất có giá trị để giảm FP.

### C. Nguồn công khai

Có thể dùng các bộ road-damage/pothole/crack công khai như RDD2022, Pothole-600, CrackForest/CFD, GAPs384 và bộ crack bê tông như SDNET2018 để pretrain hoặc bổ sung hình thái. Tuy nhiên chúng thường khác vật liệu, góc quay, camera, ánh sáng và quốc gia; không được trộn trực tiếp vào test nghiệm thu RoadGuard.

Quy tắc: public data giúp model biết “hình dạng defect”; drone data Việt Nam quyết định model có biết “defect trên đúng mặt đường này” hay không.

## 7. Tài nguyên phần cứng và phần mềm

- Local SSD: cần chừa tối thiểu 2–3 lần dung lượng video của một run để giữ frame/cache tạm.
- GPU: 8 GB VRAM đủ fine-tune YOLO nhỏ ở 640; 12–16 GB thuận lợi hơn cho segmentation/tiling.
- Google Drive 5 TB: raw immutable, dataset version, checkpoint, metrics và release; không chạy job trực tiếp trên thư mục Drive đang sync.
- Dùng SHA256 + manifest cho video, SRT, dataset, model và run.
- Annotation: 1 annotator + 1 reviewer; các lớp khó cần kỹ sư hiện trường quyết định.

## 8. Chiến lược train đề xuất

### Phase A — Road gate

Fine-tune road segmentation bằng frame thật, đánh giá IoU/Dice và leakage vào cây/cỏ/lề đường.

### Phase B — Detector baseline

Train `pothole` và `crack` trước trên vùng mặt đường đã lọc; thêm hard negatives từ 4 video. Chỉ khi baseline không còn nhầm nặng mới mở rộng `bong_troc`, `edge_break`, `joint_gap`, `standing_water`.

### Phase C — Fine-grained defect

Các lớp mới chỉ được bật khi có đủ instance và reviewer agreement. `joint_gap` sạch nên là negative/exclusion; chỉ gắn defect khi có vỡ/tróc/hư hỏng kèm theo.

### Phase D — Temporal/active learning

Chạy model trên video chưa gán nhãn, ưu tiên review false positive và confidence thấp, bổ sung vào vòng train tiếp theo.

## 9. Quy tắc quyết định “đủ dữ liệu chưa?”

Chưa đủ nếu:

- crack thật trên drone quá ít hoặc chỉ có ảnh internet;
- test random frame thay vì test theo survey;
- không có hard negative cây/bóng/xe/người từ chính tuyến khảo sát;
- lớp có ít hơn 2 survey độc lập;
- không biết file đang là 2.7K gốc hay 1080p proxy;
- không có người review nhãn.

Đủ cho pilot khi có ít nhất 4 survey, road mask được review, mỗi lớp bắt buộc có positive thật hoặc được đánh dấu chưa hỗ trợ, và toàn bộ candidate trên một video holdout được kỹ sư xem qua.
