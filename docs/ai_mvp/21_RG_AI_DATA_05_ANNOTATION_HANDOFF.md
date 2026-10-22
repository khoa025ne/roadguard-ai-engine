# RG-AI-DATA-05 — mở batch 20 ảnh và gán nhãn thử

Kiểm tra 2026-10-22 trên batch DATA-04. Không trích thêm ảnh, không tạo ground truth, không sửa MP4/SRT. Bảng bàn giao an toàn cho GitHub ở `manifests/crack_dji_pilot_batch01_handoff.csv` chỉ có basename/frame/time danh nghĩa/hash ảnh/triage; **không chứa ảnh, GPS, SRT hoặc đường dẫn máy cá nhân**. Manifest đầy đủ và ảnh (~19,9 MB JPEG + ~0,8 MB contact sheet) chỉ ở `data/pilots/crack_dji_20261022_batch01/` trên máy; `data/` bị Git ignore. Nếu cần đồng bộ riêng tư, đề xuất `Google Drive/RoadGuard/private/annotation_pilots/crack_dji_20261022_batch01/` với quyền chỉ annotator + kỹ sư, giữ manifest/hash, không tạo link công khai; **chưa upload**.

## Góc xiên và quyết định cần người dùng

SOP bay trong `15_FIELD_DATA_COLLECTION_PACK.md` yêu cầu gimbal −90° ±2°. 7 ảnh ở `visual_triage.csv` có phối cảnh xiên rõ khi xem contact sheet, nên gắn `provisional_reject` khỏi **nhánh dữ liệu nadir**: `0059` frame 2400/3200, `0060` 600/6200, `0061` 900, `0063` 350/3400. Đây là đánh giá hình ảnh, **không phải đo pitch**; SRT chưa có pitch tin cậy. Ảnh vẫn giữ nguyên để nghiên cứu domain xiên sau này, không biến thành negative hay xóa. `0061` frame 11200 nằm nhóm uncertain vì vừa xiên/vừa có xe, chưa áp quyết định cuối.

Quyết định sản phẩm cần BA/chủ dự án chốt nếu muốn dùng ảnh xiên: giữ nadir-only như SOP (khuyến nghị cho MVP) và bay bù đoạn thiếu; hoặc mở **một tập/model/metric riêng cho góc xiên**, với chuẩn thu thập/evaluation mới. Không trộn 7 ảnh vào training/evaluation nadir chỉ vì thiếu dữ liệu.

## Mở giao diện và thao tác (Windows, không cần cài thêm thư viện)

1. Mở PowerShell trong `F:\train AI đồ án`.
2. Chạy `python tools/annotate_dji_crack_pilot.py --pilot data/pilots/crack_dji_20261022_batch01`.
3. Mở URL in ra, mặc định `http://127.0.0.1:8765/`, trên **chính máy này**. Không chuyển tiếp cổng lên Internet; nhấn Ctrl+C ở PowerShell để dừng.
4. Cột trái có 3 nhóm 6/7/7. Chọn ảnh, phóng to, kéo chuột bao sát **vết nứt chắc chắn**. Nút “Bỏ box cuối”/“Xóa box nháp” sửa trước khi lưu. Khe sạch, bóng, sơn, dây điện, xe không vẽ crack.
5. Chọn quyết định chất lượng và trạng thái `draft`, `pending_review`, `uncertain`, `reject` hoặc `approved`. Điền tên người gán, ghi chú và phút thực tế. Ca uncertain/reject bắt buộc nêu lý do. Nhấn “Lưu phiên bản mới”; mỗi lần tạo JSON revision mới ở `annotations/revisions/`, không sửa ảnh/manifest hay revision cũ.
6. **Chỉ kỹ sư được chỉ định** dùng `approved`: chọn chất lượng `accept`, điền tên reviewer và tick xác nhận. Nếu 0 box, phải kiểm toàn ảnh rồi tick “không có crack”; không mặc định 0 box là clean. Giao diện chặn approval của 7 ảnh xiên khỏi nhánh nadir. Tên/checkbox là nhật ký thao tác, không xác thực danh tính kỹ sư; người quản lý phải kiểm quyền ngoài công cụ.
7. Ví dụ thử **không tạo ground truth**: mở ảnh `DJI_0059...f000360...`, quan sát đường tối, nếu chưa phân biệt crack-vs-khe thì chọn `uncertain`, ghi “đường tối cần kỹ sư xác nhận” và tên, lưu. Kỹ sư mở lại, xem video/ngữ cảnh, mới kết luận và duyệt hoặc giữ uncertain. Không dùng hình minh họa như nhãn chuẩn.

Giao diện hỗ trợ **box crack và trạng thái**, chưa vẽ mask. Mask crack/road cần polygon/brush ở LabelMe hoặc CVAT sau khi người dùng chọn công cụ; hai gói này **chưa được cài trong environment hiện tại**. Khi xuất mask, giữ cùng basename, kích thước 1920×1080, phiên bản nhãn, reviewer và hash ảnh; không tự điền `approved`. Không upload dữ liệu bay lên dịch vụ annotation công khai.

## Bàn giao người thực hiện

- Chủ dự án/BA: chỉ định annotator, kỹ sư duyệt crack-vs-khe/nadir, xác nhận công cụ mask và lựa chọn có cần nghiên cứu nhánh xiên riêng không.
- Annotator: bắt đầu từ 6 ảnh `provisional_keep`, sau đó rà 7 `uncertain`; ghi phút thực tế/ảnh và vùng mơ hồ. Không gán nhãn âm tính theo suy đoán.
- Kỹ sư: xem ảnh full resolution + ngữ cảnh video, giải quyết crack-vs-khe và 7 ảnh xiên, duyệt có tên. Sau 20 ảnh tổng kết lỗi/time trước khi mở batch mới.
- Người quản lý dữ liệu: giữ batch local hoặc Drive riêng tư, kiểm SHA-256 sau copy; không push JPEG/MP4/SRT/GPS hay revision nhãn lên repo công khai khi chưa có phê duyệt chia sẻ.

Trạng thái tại lúc bàn giao: 20 ảnh, 6/7/7 triage, **0 bbox/mask/approved**, annotation time chưa đo. Tool không tự sinh nhãn. Timestamp trong bảng là `frame_index/FPS` danh nghĩa, không xác thực SRT/PTS. Survey independence chưa được chứng minh nên chưa chia train/val/test.
