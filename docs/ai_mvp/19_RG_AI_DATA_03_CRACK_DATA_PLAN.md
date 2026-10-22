# RG-AI-DATA-03 — thiết kế dữ liệu crack detection + segmentation

Kiểm tra 2026-10-22, worktree `82ae0dc` + thay đổi chưa commit. Đây là **khảo sát/thiết kế**, chưa tạo tập train mới, tải public dataset, trích frame hàng loạt, gán nhãn hoặc train. Căn cứ: `01`, `03`, `09`, `10`, `18`, `docs/ai/tasks/RG-AI-DATA-02.md` và `manifests/dji_20261004.json`. Số lượng file/nhãn dưới đây là kiểm kê cấu trúc, **không phải kiểm định nhãn đúng**.

## 1. Dữ liệu và công cụ đang có

| Tài sản đã kiểm tra | Bằng chứng hiện có | Quyết định sử dụng |
|---|---|---|
| `data/merged` | 21.424 ảnh + 21.424 TXT YOLO; 21.587 instance `crack`, 10.111 `pothole`, 6.334 TXT rỗng; không có PNG/TIFF mask | Có box để thử baseline, **không** là holdout DJI hoặc mask ground truth. `tools/build_20k_dataset.py` sinh box crack bằng adaptive threshold/contour và có fallback box gần toàn patch; chưa có review thủ công cho phần này. TXT rỗng chưa chứng minh hard negative đúng nghĩa. |
| `data/unified_road_dataset_15k` | 15.000 ảnh; 5.000 crack box, 10.111 pothole box, 6.060 TXT rỗng; không có mask | Tập dẫn xuất public/legacy, dễ chồng lặp với `merged`; chỉ dùng sau audit nguồn và kiểm tra trùng cross-split. |
| `data/road_crack` | NTFS junction tới `results/web_runs/.../unzipped`; 6.315 JPG, YOLO TXT; `data.yaml` ghi Roboflow v1/CC BY 4.0 | Box crack có sẵn, nhưng chưa xác minh giấy phép/nguồn gốc từng ảnh và chất lượng nhãn từ trang gốc; không trộn vào DJI holdout. `data/road_crack_test_eval` chứa 265 ảnh/702 box, là subset cùng nguồn, **không phải test độc lập**. |
| `data/curated_export` | 463 ảnh/463 TXT; `roadguard_unified_finetune` có 450 ảnh và layout `images/train`, `labels/train`; tool audit hiện không đọc được layout này | Cần audit riêng; không coi tên `curated` là bằng chứng reviewer đã duyệt. `DatasetExporter` đang chia theo thứ tự frame, không theo survey; có fallback box 90% crop. Không dùng split đó để nghiệm thu. |
| `outputs/drone_benchmark_50_frames` | 50 JPG từ `0057/0059/0061/0064`, tên chứa video/frame/timestamp, **không có nhãn** | Dùng để xem nhanh/thiết kế rubric, không tự coi là positive crack hoặc ground truth. |
| `data/mvp_test_cases` | 30 ảnh thực tế chỉ trong `07_hard_negatives`; các thư mục crack hiện 0 ảnh; spec của hard-negative ghi 171 | Spec là mục tiêu/lịch sử, không phải tồn kho. Chưa xác minh 30 ảnh này là từ DJI hay đã được người duyệt. |
| Video DJI + SRT | 5 cặp `0059`–`0063` ở nguồn; thêm `0057/0064` chỉ MP4 theo audit; 1080p/29,97 fps; `0062` chỉ 6 giây, frame mẫu bị che | Nguồn domain chính, hiện **0 mask crack và 0 box crack đã review gắn provenance video** được xác minh. Không mặc định `0062` hữu dụng. Giữ mọi video. |

Quan sát **chỉ trên ba ảnh mẫu**: `crack_surf_00001.jpg` là patch cận cảnh 227×227 px, nền khác scale/cảnh DJI; `DJI_0059` t≈16s cho thấy bóng flycam, bóng cây và một đường tối cần kỹ sư phân biệt nứt/khe; `DJI_0061` t≈21s nhìn xiên có cây che nhiều. Không suy chất lượng toàn video từ ba ảnh. Công cụ hiện có gồm script trích 50 frame, YOLO label/export, auto-tagger/heuristic; **không tìm thấy quy trình pixel-mask crack được review trên DJI**. CVAT/Label Studio mới là lựa chọn đề xuất, không khẳng định đã cài.

## 2. Public datasets — nguồn, quyền dùng và domain gap

Chỉ khảo sát metadata nguồn; **chưa tải và chưa kiểm tra từng file**. “Public” không đồng nghĩa quyền tái phân phối/train thương mại. Trước nhập dữ liệu cần chụp phiên bản/URL, license của **dataset** (không nhầm license code), checksum, danh sách ảnh gốc và attribution.

| Nguồn chính thức | License được công bố | Góc chụp / mặt đường / cỡ ảnh | Nhãn, chuyển đổi | Đánh giá cho RoadGuard |
|---|---|---|---|---|
| [Crack500 — repo tác giả](https://github.com/fyangneil/pavement-crack-detection) | Repo nguồn không nêu giấy phép dataset rõ ràng: **chờ tác giả/xác minh quyền dùng** | Ảnh pavement gần mặt đất/điện thoại, tài liệu nghiên cứu thường ghi gốc khoảng 2.000×1.500 (chưa kiểm tra archive); nhiều bản dùng patch cắt từ ảnh gốc | Mask pixel theo benchmark; mask→box bằng connected components sau khi kiểm tra quy tắc tách nứt | Hữu ích học hình thái, domain gap lớn về góc/scale; patch cùng ảnh gốc phải ở cùng split. Không chọn làm nguồn chính trước khi rõ quyền dùng. |
| [DeepCrack — repo tác giả](https://github.com/yhlleo/DeepCrack) | Tác giả ghi **chỉ nghiên cứu/giáo dục phi thương mại** cho ảnh và annotation | Nhiều bề mặt/cảnh, có concrete và asphalt, gần mặt đất; kích thước từng file chưa đối chiếu | `train_img/train_lab`, `test_img/test_lab`, binary pixel maps; mask→box có thể làm | Khởi tạo/đối chứng học thuật; không dùng trong nhánh có mục đích thương mại nếu chưa được phép; tránh trộn split gốc. |
| [PaveCrack1300 — Mendeley Data v1](https://data.mendeley.com/datasets/8b27pdcxv7/1) | **CC BY 4.0**, cần attribution | DJI Mini 4 Pro, gần nadir sau chỉnh trực giao; pavement chưa xác nhận riêng tỷ lệ concrete/asphalt; 1.300 cặp 512×512 | Mask PNG nhị phân 255/0, polygon LabelMe gốc; mask→box khả thi | Ưu tiên thử segmentation/pretrain do góc UAV; **chỉ giữ patch có crack ≥4%**, thiếu negative/hairline, không thay thế hard negatives DJI. |
| [UAV-1388 — Figshare](https://figshare.com/articles/dataset/Pavement_cracks_from_UAV_imagery-1388/25103138) | **CC BY 4.0**, cần attribution | Ảnh UAV pavement, paper dùng DJI Mini 2; độ phân giải/file cụ thể chưa xác minh | Trang nguồn công bố 1.388 ảnh theo loại nứt và 100 no-crack; **chưa xác minh box/mask**. Chỉ coi là classification/candidate sampling cho tới khi xem file | Góc bay phù hợp hơn ảnh điện thoại; không tự biến nhãn loại nứt thành box/mask. Chú ý split theo ảnh gốc/chuyến bay. |
| [UAV-PDD2023 v4 — Zenodo](https://zenodo.org/records/8429208) | Trường Rights/License trên record hiện **không ghi loại giấy phép**: cần làm rõ trước khi train/redistribute | UAV cao 30 m, road pavement; 2.440 ảnh, paper sau mô tả 2.592×1.944 (cần xác minh trên file) | 11.158 object VOC box, sáu lớp gồm các nhóm nứt, repair, pothole; VOC→YOLO box; không có mask được công bố trên record | Nguồn detection UAV đáng khảo sát, nhưng cao/scale khác Mini 2 SE và license chưa rõ. |
| [PaveSeg — repo tác giả](https://github.com/FuturePave/PaveSeg-Dataset) | Repo ghi Apache-2.0, song **full dataset** được mô tả cần xin quyền dùng phi thương mại; xác minh quyền cho 100 ảnh preview riêng | Pavement 1.280×1.080; góc/camera chưa xác minh | Mask pixel nhiều lớp: crack, sealed crack, expansion joint...; chuyển grayscale ID→mask nhị phân hoặc hard-negative | Hữu ích học phân biệt crack với joint/sealed crack; chưa nhập vào gói thử vì quyền full set và domain còn cần làm rõ. |

Nguồn thứ cấp/paper **không được dùng thay điều khoản tác giả**. Không tải trực tiếp từ bản đóng gói lại vì có thể thay split, nhãn hoặc license. Không dùng bất kỳ public image nào làm holdout nghiệm thu RoadGuard.

## 3. Quy trình dữ liệu DJI đề xuất (chỉ kích hoạt sau phê duyệt)

1. **Định danh/provenance:** mỗi candidate giữ SHA-256 MP4, basename, `raw_frame_idx`, timestamp từ FPS thật, nguồn/phiên bản SRT, frame SHA-256, thuật toán sampling, trạng thái telemetry. Không dựa GPS/GSD để chọn hoặc dedup frame; `H` không phải AGL.
2. **Triage chất lượng ở độ phân giải gốc:** decode thành công, road concrete thấy rõ, crack tiềm năng không mất bởi blur/H.264, không đen/cháy sáng lớn tại vùng cần gán, không bị xe/cây che nặng. Blur/exposure score chỉ để xếp ưu tiên; người review quyết định `ACCEPT`, `AMBIGUOUS`, `REJECT` với reason (`blur`, `occluded`, `non_road`, `oblique`, `too_small_to_resolve`). Ảnh xiên được gắn tag và phân tầng riêng, không giả nadir. `0062` chỉ xem thủ công trước khi có quyết định dùng.
3. **Chống lặp:** trước tiên nhóm theo video + đoạn tuyến/time; lấy candidate thưa (đề xuất bước đầu 2–3 s) rồi so sánh pHash/SSIM trên vùng road, giữ frame sắc nhất cho cùng hư hỏng. Burst quanh candidate chỉ để xem temporal, không đưa frame kề nhau qua các split. Các đoạn đường lặp ở video khác cũng cùng một nhóm; GPS SRT 4 chữ số thập phân không đủ làm khóa duy nhất.
4. **Phân loại:** `positive_crack` chỉ khi đường phá vỡ mặt bê tông nhìn thấy, kỹ sư chấp nhận; `hard_negative` gồm khe nối sạch, bóng cây/dây, vạch sơn, vệt bẩn, mép cỏ, xe/người, vật che, vết vá; `clean` là road đọc được và được review không có nứt; `ambiguous` tách riêng, không ép thành positive/negative; `reject` là ảnh kém/chưa thấy road. Một frame có cả nứt và bóng vẫn là positive với nhãn crack trên vùng thật và tag bóng.
5. **Box detection:** một box cho một vùng/nhánh nứt liên tục ở scale ảnh có thể thấy; box ôm toàn vết nứt, chừa ít context nhưng không ăn cả patch. Nứt bị khe nối chia cắt: tách instance nếu không chứng minh liên tục. Khe sạch **không** gán crack; nếu có vỡ mép/nứt phát sinh cạnh khe, gán đúng phần hư hỏng. Bbox là vùng hình ảnh, không phải mm. Hard-negative frame có file YOLO rỗng **chỉ sau khi người gán đã kiểm tra toàn frame**.
6. **Pixel mask:** trên subset đủ phân giải, tô đúng pixel/đường nứt nhìn thấy; không tô bóng, khe sạch, sơn hoặc cả bbox. Lưu mask nhị phân PNG cùng kích thước ảnh gốc/crop với `ignore` riêng cho vùng mơ hồ/che khuất; giữ polygon/brush annotation gốc để sửa. Mask→box chỉ là **derived label**, lưu script/version và QA ít nhất 10% cặp để không cắt nhánh mảnh. Nếu crack mảnh dưới khả năng thấy ở 1080p, gắn `not_resolvable`, không vẽ theo suy đoán. Reviewer độc lập duyệt mọi positive của batch đầu.
7. **Road mask:** cần nhãn road-surface riêng trên subset để đo leakage; mask crack chỉ nằm trong vùng road hợp lệ. Không dùng model road segmentation hiện tại làm ground truth tự động.

### Split và kiểm tra leakage

- Khóa group theo `survey_id + route_segment + flight/session`, không chỉ basename. **Chưa chứng minh 0059–0063 là 5 survey độc lập**; có thể là các clip cùng chuyến/tuyến. Nếu cùng đường, toàn nhóm phải ở một split. `0057/0064` giữ trong registry, chưa tự loại vì thiếu sidecar.
- Đợt nhỏ đầu **chỉ là pilot annotation**, chưa gọi train/val/test. Sau khi có ≥3 survey/đoạn tuyến thực sự độc lập, đề xuất một nhóm cho train, một cho val và tối thiểu một **survey khác** khóa test; nếu ít hơn, dùng group cross-validation để thăm dò nhưng **chưa tuyên bố holdout đạt Gate A**. Public image/patch cùng nguồn gốc không được rơi vào nhiều split; kiểm tra SHA-256 + pHash/embedding review tại ranh giới split.
- Báo recall theo defect/track và theo frame, detection precision/recall tại IoU 0,3 và 0,5 (IoU nứt mảnh dễ nhạy với độ rộng box), confusion với joint/shadow/marking. Segmentation báo pixel recall, precision, Dice/IoU và recall theo đường nứt/instance; giữ protocol mask/ignore cố định. **FP/km** chỉ tính khi có chiều dài tuyến độc lập được đo/duyệt (waypoint/field map), không suy từ GPS SRT; trước đó dùng FP/video hoặc FP/phút và ghi rõ không tương đương FP/km.

## 4. Ma trận thí nghiệm sau khi dữ liệu được duyệt (không train ở DATA-03)

Giữ nguyên một holdout DJI độc lập, cùng preprocessing/metric/budget. Đánh giá **detection** và **segmentation** riêng, rồi đánh giá road gate + temporal trên video; không suy segmentation tốt từ mAP box hay ngược lại.

| Nhánh | Detection | Segmentation | Mục đích/giới hạn |
|---|---|---|---|
| Public-only | Box gốc có quyền dùng hoặc box dẫn xuất từ mask được QA | Mask public có quyền dùng | Baseline domain gap; không đủ để công bố MVP DJI. |
| DJI-only | Box crack/hard negative reviewer duyệt | Mask DJI reviewer duyệt | Đo giá trị dữ liệu đúng domain; có thể thiếu số lượng. |
| Public + DJI | Trộn theo tỷ trọng/source rõ ràng, tránh public áp đảo | Tương tự cho mask | Kiểm tra public giúp hay làm tăng FP trên joint/shadow DJI. |
| Pretrain public → fine-tune DJI | Cùng model/budget so với nhánh trên | Cùng protocol riêng | Ứng viên chính nếu quyền dùng rõ và pilot cho thấy cải thiện recall mà FP không tăng quá ngưỡng BA chốt. |

Không chọn ngưỡng PASS hoặc công thức FP/km khi BA chưa chốt mức chấp nhận và tuyến đo độc lập. Không tăng recall bằng cách hạ threshold rồi bỏ qua số FP.

## 5. Đợt nhỏ đầu xin phê duyệt

**Đề xuất, chưa thực hiện:** lập danh sách tối đa **120 frame candidate** từ `DJI_0059/0060/0061/0063`, ưu tiên các đoạn bê tông đọc được và tránh khung trùng; `0062` chỉ triage vài khung thủ công, không đặt quota. Mục tiêu phân bổ sau khi xem: tới 40 suspected crack, 40 hard negatives (khe/bóng/sơn/xe/cây), 20 clean, 20 ambiguous/quality. Nếu không tìm đủ crack, báo thiếu và đề xuất bay thêm, **không ép nhãn**. Gán box/quality/provenance cho 120 frame; chọn tối đa **40 frame** (khoảng 30 positive + 10 khó phân biệt) để gán crack mask và road mask tương ứng. Không dùng public data trong holdout pilot; chưa train.

**Ước lượng công sức, không phải cam kết:** giả định 1 annotator + 1 reviewer, triage/box 3–5 phút ×120 = 6–10 giờ; mask/road/ignore 10–25 phút ×40 = 7–17 giờ; review độc lập/đối soát 4–8 giờ; QA manifest/split ~2 giờ: **khoảng 19–37 giờ người**. Nếu nứt mảnh/bóng phức tạp hoặc ảnh xiên nhiều, thời gian tăng và quota mask giảm. Sau 20 frame đầu đo lại tốc độ, tỷ lệ bất đồng và tỷ lệ positive thật trước khi duyệt phần còn lại.

**Điểm người dùng/BA cần duyệt:** (a) nguồn frame ứng viên và ngân sách 120/40; (b) ai là kỹ sư quyết định crack vs joint; (c) có tuyến/chuyến bay độc lập mới cho holdout hay tất cả clip 04-10 cùng tuyến; (d) mục đích dùng public data chỉ nghiên cứu hay có khả năng thương mại để loại dataset hạn chế; (e) nguồn chiều dài tuyến chuẩn cho FP/km. Không cần chốt các điểm này để giữ nguyên video và báo cáo kiểm kê hiện tại.

## Bằng chứng và phần chưa xác minh

- Đã chạy kiểm kê chỉ đọc theo extension, đọc cấu trúc YOLO qua `tools.audit_dataset_readiness.audit_yolo_dataset` và kiểm tra một số script/ảnh mẫu; không đánh giá đầy đủ pixel quality hoặc đúng/sai từng nhãn.
- `merged`/15K/test_eval đếm nhãn cấu trúc PASS nhưng không có pixel mask; tool audit hiện index TXT theo basename toàn dataset nên chưa chứng minh không có basename collision giữa split. `curated_export` dùng layout khác nên báo thiếu nhãn giả; cần công cụ audit layout-aware ở gói thực thi.
- Public dataset metadata/license được xem 2026-10-22 từ trang tác giả/repository; độ phân giải, định dạng từng file và điều khoản quyền dùng cuối cùng cần xác minh khi nhập dữ liệu. Nguồn [paper UAV-1388](https://www.mdpi.com/2076-3417/14/3/1157) xác nhận DJI Mini 2 và detection nghiên cứu, nhưng trang Figshare chưa nêu cấu trúc box/mask của archive.
