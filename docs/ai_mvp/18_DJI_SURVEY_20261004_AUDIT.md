# Cập nhật khảo sát DJI ngày 04-10 — kiểm chứng file gốc

Lưu ý chia sẻ: `manifests/dji_20261004.json` chứa GPS và đường dẫn nguồn, giữ **cục bộ**; không push manifest này lên GitHub công khai. Bảng bàn giao DATA-05 đã lược bỏ GPS và đường dẫn máy.

Kiểm tra 2026-10-22, revision nền `82ae0dc`. Nguồn: `F:\video-flycam ngày 04-10`; đối chiếu `data/raw_videos/`. Manifest cục bộ `manifests/dji_20261004.json` có SHA-256 từng MP4/SRT, metadata và phép kiểm timestamp, được tạo bằng `tools/audit_dji_survey.py`; không phát hành trên GitHub vì có GPS. Bản runtime nằm ở `outputs/survey_manifest_20261004.json`. Không đổi, chuyển, xóa video/SRT nào.

## Kết quả ghép cặp và telemetry

| Video nguồn | MP4/SRT cùng basename | Thời lượng | SRT cues / GPS hợp lệ | `H` ghi trong SRT | Gimbal pitch |
|---|---|---:|---:|---:|---:|
| `DJI_0059` | Có | 120.053 s | 120 / 120 | 0–3.4 m | không có |
| `DJI_0060` | Có | 301.067 s | 301 / 301 | 0–3.0 m | không có |
| `DJI_0061` | Có | 427.000 s | 427 / 427 | 2.0–4.3 m | không có |
| `DJI_0062` | Có | 6.000 s | 6 / 6 | 0 m | không có |
| `DJI_0063` | Có | 126.000 s | 126 / 126 | 0.8–14.7 m | không có |
| `DJI_0064` | **Không có SRT rời** | 330.000 s | chưa xác minh sidecar | — | — |

Với cả 5 cặp, nội dung (sau chuẩn hóa khoảng trắng) và timestamp từng cue SRT rời **trùng với track subtitle nhúng trong MP4**. Cue bắt đầu 0 ms, tăng đơn điệu, không chồng lấp/không có khoảng trống; cuối SRT lệch cuối video 0–67 ms. Đây là đồng bộ **timebase/cặp file**, không phải xác nhận GPS chính xác ngoài hiện trường. GPS hiện diện và nằm trong phạm vi tọa độ hợp lệ ở mọi cue, nhưng chỉ ghi khoảng 4 chữ số thập phân; toàn video lần lượt chỉ có 7, 19, 48, 1, 15 cặp tọa độ khác nhau. Không dùng trực tiếp để suy FP/km hay định vị khuyết tật độ chính xác cao.

`H` chỉ là **độ cao ghi trong subtitle** (có thể tương đối với điểm cất cánh), không được chứng minh là khoảng cách camera–mặt đường/AGL. Dãy `H` phần lớn thấp hơn SOP 10 m và thay đổi mạnh ở `0063`; không được tự suy là chuyến bay vi phạm SOP hay tính GSD từ `H` khi chưa có flight log và quan hệ với nền địa hình. Cả 5 SRT không chứa gimbal pitch, nên `−90° ±2°` **chưa xác minh**.

## Video và chất lượng quan sát được

- Cả 6 MP4 trong thư mục nguồn là H.264 **1920×1080, 29.97003 fps**, không phải 2720×1530/30 fps ghi trong profile dự án. Cả 6 giải mã toàn bộ stream video bằng FFmpeg với `-xerror`: exit 0. Ba khung tại 10/50/90% mỗi video đều đọc được; số đo luma/độ nét proxy trong manifest. Chúng chỉ chứng minh khả năng đọc và mức phơi sáng/độ tương phản cục bộ, **không chứng minh toàn clip sắc nét hoặc đủ điều kiện gán nhãn**.
- Sáu ảnh đơn lẻ ở `outputs/survey_quality_samples_20261004/` là bằng chứng xem nhanh, không phải trích frame hàng loạt. `0059` giữa clip có xe đỗ và bóng/vệt trên mặt bê tông; `0060/0061/0063` có đường bê tông, cây/cỏ/bóng và khe/nứt cần chuyên gia xác nhận; `0064` có đường và mép cỏ. Khung giữa `0062` bị vật gần camera che gần hết, clip chỉ 6 s: giữ file nhưng **chưa tính là survey hữu dụng cho huấn luyện/holdout**. Góc camera không thể chốt chỉ bằng các ảnh mẫu.
- Không có nhãn ground truth hoặc kiểm tra field cho các clip này. Chưa có quality gate độc lập theo từng đoạn để quyết định frame nào vào dataset.

## Đối chiếu 4 video trong tài liệu cũ

| Basename | `data/raw_videos/` (danh sách cũ) | Thư mục nguồn 04-10 | Kết luận |
|---|---|---|---|
| `DJI_0057` | MP4 | không thấy | Giữ bản workspace; có subtitle nhúng, chưa có SRT rời |
| `DJI_0059` | MP4 | MP4 + SRT | MP4 hai nơi SHA-256 trùng |
| `DJI_0060` | không | MP4 + SRT | Mới phát hiện; giữ |
| `DJI_0061` | MP4 | MP4 + SRT | MP4 hai nơi SHA-256 trùng |
| `DJI_0062` | không | MP4 + SRT | Mới phát hiện; giữ, clip ngắn/che khuất |
| `DJI_0063` | không | MP4 + SRT | Mới phát hiện; giữ |
| `DJI_0064` | MP4 | MP4, thiếu SRT rời | MP4 hai nơi SHA-256 trùng; có subtitle nhúng |

Tổng cộng **7 basename MP4 khác nhau** trên hai nơi; 5 cặp sidecar hợp lệ ở thư mục nguồn. Không tự loại bỏ `0057`/`0064`, không tự tạo sidecar từ subtitle nhúng. Quy định dự án về cặp MP4/SRT cùng basename hiện được 5 file `0059`–`0063` đáp ứng tại nguồn; chưa đáp ứng ở `data/raw_videos/` vì nơi đó vẫn chỉ có 4 MP4 và không có SRT.

## Blocker tích hợp và quyết định tiếp theo

`src/ingestion/srt_parser.py` **không đọc đúng định dạng SRT vừa xác minh**: cue `GPS (kinh độ, vĩ độ, …)` được gán ngược nên vĩ độ thành giá trị ngoài ±90°; parser không nhận `H` nên rơi về 10 m và không có pitch thì tự gán −90°. Kiểm tra trực tiếp `DJI_0059.SRT`: 120 cue được parse nhưng vĩ độ đầu không hợp lệ, `rel_alt_m=10.0`, `gimbal_pitch=-90.0` đều do fallback. `tools/audit_survey_assets.py` cũng dùng validator yêu cầu `ALT/BAROMETER` và pitch, không phù hợp đúng định dạng `H` hiện có. **Không đưa GPS/GSD/nadir từ pipeline hiện tại vào kết quả tin cậy**. Chưa sửa code này trong công việc kiểm kê dữ liệu.

**Cập nhật 2026-10-22 / RG-AI-DATA-02:** đoạn trên là phát hiện tại thời điểm audit, trước khi sửa. Parser và các điểm xuất số đo đã được sửa; xem `docs/ai/tasks/RG-AI-DATA-02.md`. Năm SRT thật nay parse 980 cue GPS/H/D, không tự tạo pitch, AGL hoặc GSD. Chưa có bằng chứng hiện trường để công bố tọa độ khuyết tật hoặc kích thước vật lý.

Gói tiếp theo nên: (1) lấy flight log/screenshot camera để xác minh độ phân giải, độ cao AGL và gimbal; (2) thống nhất ý nghĩa `H` và tọa độ GPS với DJI/đội bay; (3) sửa parser + test bằng 5 SRT thật, chặn default giả; (4) quyết định có xuất SRT rời cho `0057`/`0064` từ track nhúng hay lấy bản gốc từ thẻ nhớ; (5) review đoạn video để phân loại train/holdout/hard-negative. Chưa trích frame hàng loạt, chưa train, chưa khẳng định đạt SOP hoặc gate dữ liệu.
