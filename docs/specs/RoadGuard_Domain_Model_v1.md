# RoadGuard — Domain Model v1

> Thiết kế đích đồng bộ ngày 22/09/2026 theo [Incident/Segment](RoadGuard_Incident_Segment_Design_v1.md) và [AI/Segment/Edge](RoadGuard_AI_Segment_Edge_Design_v1.md). Các aggregate, trường và quy tắc mở rộng dưới đây là hợp đồng thiết kế, không xác nhận đã có entity, migration, worker hoặc API trong runtime. Phạm vi bàn giao BE vẫn tách Android/Web, hệ AI bên ngoài và thu thập thực địa; adapter mock phải được phân biệt với AI thật. Nghiệm thu BE không tuyên bố độ chính xác AI hoặc kết quả thực nghiệm từ dữ liệu giả. Xem [ADR 003](../adr/003-backend-delivery-and-ai-boundary.md).

Dựa trên [Data Dictionary](RoadGuard_Data_Dictionary_v1.md) và [ERD](RoadGuard_ERD_v1.md). Mục tiêu: xác định ranh giới giao dịch nhất quán (aggregate),
quy tắc bất biến (invariant), và các quy tắc **liên-aggregate** cần domain service thực thi thay vì FK.

Ký hiệu: **[R]** = Aggregate Root. Entity con liệt kê thụt vào dưới root, không có ID truy cập độc lập từ bên ngoài aggregate.

## Quyết định thiết kế đã chốt theo yêu cầu người dùng

Sáu điểm dưới đây là quyết định thiết kế đã chốt. Khi có khác biệt với các "Điểm mở" cũ trong tài liệu này, các quyết định này được ưu tiên:

1. Giữ riêng `PasswordResetLog` và `AccountStatusChangeLog`.
2. `Warranty` luôn là entity/aggregate riêng, hỗ trợ nhiều giai đoạn bảo hành trong một dự án; không nhúng thành field đơn trong `HandoverDocument`.
3. `QualityCheck` được hỗ trợ ở cấp `SurveyFile` và `SurveyDataVersion`, đồng thời phân biệt Drone App kiểm tra sơ bộ với Backend/System Worker kiểm tra chính thức; PM chỉ xem kết quả và quyết định bay bổ sung.
4. `SupplementarySurveyRequest` không thuộc aggregate `Survey`; là aggregate độc lập.
5. Phát hiện AI được PM giữ lại tạo `Defect OPEN` (Preliminary Defect); PM xác minh từ bằng chứng drone hoặc thực địa đủ căn cứ. Giao Repair Crew đo bổ sung khi cần số đo vật lý hoặc bằng chứng chưa đủ, không bắt buộc đo mọi lỗi. Chỉ `Defect VERIFIED` mới được đưa vào đợt sửa; ground truth nghiên cứu vẫn bắt buộc cho mẫu nghiên cứu.
6. Khi lập đợt sửa, PM nhập phương án sửa tổng quát và chi phí dự kiến; không quản lý bước/giai đoạn thi công, vật liệu, khối lượng hoặc định mức chi tiết.

Mã truy vết: `UD-01` (audit log riêng), `UD-02` (Warranty), `UD-03` (QualityCheck hai cấp), `UD-04` (SupplementarySurveyRequest độc lập). Thiết kế 22/09 cập nhật `UD-05` thành PM xác minh dựa trên bằng chứng và `UD-06` thành phương án tổng quát + chi phí; các bằng chứng lịch sử dùng nghĩa cũ không bị viết lại.

## Yêu cầu nghiên cứu bắt buộc từ đề cương

Đề cương `RoadGuard_Contractor_Warranty_Inspection_phuonglhk.md` là nguồn yêu cầu bổ sung cho **Research Validation Track**, không phải User Story sản phẩm MVP. Track này bắt buộc phải có ground truth thực địa cho một mẫu depression/slab faulting và đối chiếu với số đo từ drone/surface model để tính sai số và measurement uncertainty.

- Có thể ghi nhận ngoài app bằng Excel/giấy trong đợt thực địa.
- Trước khi phân tích, dữ liệu phải được chuẩn hóa thành các aggregate nghiên cứu có `sample_id`, liên kết survey/road section version, người đo, dụng cụ, thời điểm, vị trí, giá trị, đơn vị và bằng chứng.
- Không dùng Research Validation Track để tự động kết luận trách nhiệm bảo hành. Workflow TN01–TN06, TN12/AI13 là phần bắt buộc của sản phẩm hiện tại và dùng chung cấu trúc số đo với Research Validation nhưng có mục đích, phân quyền và state machine riêng.

---

## 1. Auth & Access

### `User` [R]
- Không có entity con transactional.
- **Invariant:**
  - `User.role_code` là role toàn hệ thống authoritative và thuộc {Supervisor, PM, DroneOperator, RepairCrew, Reporter}; người dùng không được tự đổi vai trò (US-01 mục 3).
  - `ReporterType` ∈ {`Citizen`, `InvestorRepresentative`} chỉ phân loại người gửi, không cấp quyền quản trị/phê duyệt hoặc xem toàn dự án. Reporter đăng nhập, chỉ xem phản ánh của mình và nội dung được công bố; không nhận danh tính người gửi khác hoặc chi phí nội bộ.
  - `status = Suspended` → không đăng nhập được, không đặt lại mật khẩu được (US-01 mục 6).
  - Đặt lại mật khẩu → bắt buộc đổi mật khẩu ở lần đăng nhập kế tiếp (US-01 mục 6).
- **Domain Events:** `UserSuspended` (kích hoạt tạo danh sách bàn giao việc — quy tắc 17), `UserPasswordReset` (kích hoạt thu hồi toàn bộ Session), `UserRoleChanged` (ghi audit và thu hồi toàn bộ Session/RefreshToken trong cùng transaction trước khi role mới có hiệu lực).

### `Session` [R]
- Tham chiếu `user_id`.
- Ghi nhận `issued_at`; có thể lưu `device_metadata_json` nullable theo schema ứng dụng đã version hóa. Metadata là write-once, không chứa secret/token, không trả qua API nghiệp vụ/public, không ghi log và không được dùng thay cho kiểm tra session, role hoặc `ProjectMember` phía server.
- **Invariant:** phải bị thu hồi khi logout, hết hạn, hoặc khi `User.PasswordReset`/`Suspended`/`UserRoleChanged` xảy ra (US-01, US-17) — **cross-aggregate: Session phải lắng nghe event từ User**. Mỗi request phải đối chiếu JWT role claim với `User.role_code`; mismatch phải fail closed và thu hồi token family.

### `Notification` [R]
- Tham chiếu `recipient_user_id` + `source_entity_type/id` (đọc, không phải nghiệp vụ nên polymorphic ref chấp nhận được ở đây, khác với `Evidence`).
- **Invariant:** hỗ trợ sự kiện khảo sát, xử lý, duyệt, trả sửa, từ chối/hủy, phân công lại, sắp hết hạn bảo hành và thông báo tiến độ phản ánh đã được PM công bố. Notification không thay thế `ReportStatusEvent`; thông báo Reporter chỉ chứa dữ liệu công khai trong phạm vi của họ.

### `PasswordResetLog` [R]
- Ghi nhận riêng từng lần đặt lại mật khẩu, tham chiếu `target_user_id` và `performed_by_user_id`.
- Là audit record độc lập theo yêu cầu thiết kế; không gộp vào `AuditLog`.
- **Fields audit bắt buộc:** `target_user_id`, `performed_by_user_id`, `occurred_at`, `reason`, `result`, `source`, `correlation_id`.
- **Security invariant:** không bao giờ lưu mật khẩu, token hoặc dữ liệu bí mật; chỉ lưu người thực hiện, thời điểm và kết quả.

### `AccountStatusChangeLog` [R]
- Ghi nhận riêng các lần ngừng/mở tài khoản và việc bàn giao việc liên quan, tham chiếu `target_user_id` và `changed_by_user_id`.
- Là audit record độc lập theo yêu cầu thiết kế; `AuditLog` chung không thay thế entity này.
- **Fields audit bắt buộc:** `target_user_id`, `changed_by_user_id`, `occurred_at`, `from_status`, `to_status`, `reason`, `source`, `correlation_id`.
- Nếu phát sinh bàn giao việc, lưu thêm `handover_reference` tới danh sách bàn giao; không xóa hoặc ghi đè bản ghi cũ.

---

## 2. Project

### `Project` [R]
- Entity con: `ProjectMember` (list), `HandoverDocument`.
- **Invariant:**
  - `project_code` duy nhất (US-03 mục 1).
  - Đúng 1 `ProjectMember` với `role = PM` đang active tại một thời điểm (US-03 mục 5, quy tắc 2 Use Case).
  - Với PM/DroneOperator/RepairCrew, `ProjectMember.role_code` phải bằng `User.role_code` hiện tại. Membership phải `ACTIVE`, nằm trong `valid_from`/`valid_to`, thuộc đúng project của resource và thỏa policy thao tác; thay đổi membership có hiệu lực ngay ở request kế tiếp. Reporter dùng quyền sở hữu `IncidentReport`, không cần và không được suy ra quyền tác nghiệp từ membership dự án.
  - `status = Closed` → chặn tác nghiệp thông thường, giữ nguyên lịch sử (US-03 mục 7).
- **Domain Events:** `ProjectMemberReassigned` (kích hoạt `Notification`).

### `Warranty` [R]
- Aggregate riêng, bắt buộc có `project_id` và có thể có `road_section_id` khi bảo hành gắn với một đoạn đường cụ thể.
- **Fields nghiệp vụ:** `handover_date`, `warranty_start_date`, `warranty_end_date`, `retained_value`, `scope`, `source_document_id`.
- Một `Project` có thể có nhiều `Warranty` cho các giai đoạn/thời hạn/phạm vi khác nhau.
- Không được biểu diễn bằng một field đơn trong `HandoverDocument`; `HandoverDocument` chỉ quản lý hồ sơ bàn giao.

### `RoadSection` [R]
- Entity con: `RoadSectionVersion` (list, đúng 1 bản `is_current = true`; không dùng current-version FK vòng).
- **Invariant tạo/chuyển version:** tạo RoadSection rồi tạo Version 1 `is_current = true`; khi đổi hình học, tạo version bất biến mới và đổi marker trong cùng transaction. SQL filtered unique index chặn nhiều current version; application không hoàn tất command nếu chưa có current version.
- **SRID:** `Project.engineering_utm_srid` nullable không có default, chỉ nhận 32648/32649; không tạo RoadSectionVersion khi project chưa cấu hình SRID.
- **Invariant:** sửa hình học → tạo `RoadSectionVersion` mới, giữ bản cũ; **dữ liệu cũ (Survey, Defect) không tự gắn sang hình học mới** (US-03 mục 3).
- **⚠️ Hệ quả thiết kế quan trọng:** vì invariant trên, mọi entity lưu vị trí trên đoạn đường (`Survey`, `Defect`) phải tham chiếu `road_section_version_id` cụ thể tại thời điểm tạo — **không** chỉ tham chiếu `road_section_id`. Nếu chỉ dùng `road_section_id`, sửa hình học sẽ vô tình "kéo" dữ liệu cũ sang hình học mới, vi phạm đúng quy tắc mà US-03 mục 3 cấm.
- Supervisor nhập tuyến đã bàn giao; đầu/cuối chỉ đủ cho tuyến thẳng. Tuyến cong cần polyline được PM xác nhận từ vẽ/import/hồ sơ; GPS drone chỉ là nguồn tham khảo. Tính chiều dài theo polyline và hệ tọa độ mét, giữ chiều tăng lý trình.

### `RoadSegmentSet` [R]
- Entity con: `RoadSegment` (list); `SegmentSetId` là định danh của `RoadSegmentSet`, không phải một aggregate khác.
- Tham chiếu một `road_section_version_id`; PM sửa nháp, chọn chiều dài mục tiêu dương (100 m, 1.000 m hoặc giá trị khác), chia/gộp/chỉnh ranh giới rồi công bố.
- Mỗi segment lưu mã/thứ tự, khoảng `start_offset_m`/`end_offset_m`, chiều dài và hình học con. Bộ công bố phủ đủ tuyến, không hở/chồng khoảng, các segment kề nhau chung ranh giới; dùng `[đầu, cuối)` và segment cuối chứa điểm cuối tuyến.
- Công bố làm bất biến bộ và segment. Chia lại hoặc đổi hình học tạo bộ mới; nhiệm vụ, video, Defect và job cũ giữ nguyên bộ/phiên bản đã tham chiếu. `RoadSegmentMapping` lưu quan hệ trước/sau và căn cứ ánh xạ; không gán phát hiện sang segment nhỏ hơn nếu chưa đủ căn cứ vị trí.

### `IncidentReport` [R]
- Entity con: `ReportPhoto`, `ReportStatusEvent` (append-only), `ReportStatusEventPhoto` (ảnh được công bố cùng event). Giữ người gửi, nội dung gốc và `incident_case_id` bắt buộc: gửi thành công tạo hồ sơ New; project có thể chưa xác định để chờ định tuyến. Nhiều phản ánh có thể cùng một hồ sơ; gộp trùng liên kết hồ sơ chính và giữ lịch sử nguồn.
- Mỗi ảnh có GPS/vị trí hư hỏng riêng, nguồn tọa độ (`CaptureGps`, `Exif`, `Manual`, `Unknown`), thời điểm và độ chính xác nếu có; giữ vị trí gốc cùng lịch sử PM hiệu chỉnh. Không lấy GPS lúc upload cho ảnh cũ thiếu GPS; không ép ảnh xa nhau vào một segment.
- `ReportStatusEvent` là timeline công khai riêng với mã `SUBMITTED`, `RECEIVING` khi PM bắt đầu xử lý, `ACCEPTED` khi PM nhận, `VERIFYING`, `DEFECT_FOUND` hoặc `NO_DEFECT` (bắt buộc lý do PM), `AWAITING_REPAIR`, `REPAIRING`, `RETESTING`, `REPAIRED`, `DUPLICATE`, `OUT_OF_SCOPE`. Assigned tự động không tạo RECEIVING/ACCEPTED.
- Chỉ PM kết luận/công bố. `REPAIRED` cần hồ sơ đạt `Verified`, các lỗi liên quan đã đạt và ảnh sau sửa đúng phạm vi được server-confirm rồi PM chọn công bố; Crew nộp `Fixed` chưa đủ. Trùng/ngoài phạm vi có nhãn và lý do riêng, không là `NO_DEFECT`; phản ánh trùng theo dõi hồ sơ chính nhưng không thấy người gửi khác.

### `IncidentCase` [R]
- Entity con: `IncidentCaseHistory` (append-only, lưu actor/thời điểm/lý do, thay đổi người phụ trách), `IncidentCaseDefect` (liên kết Defect); liên kết phản ánh, tuyến/segment và các nhiệm vụ qua định danh. Hồ sơ chưa định tuyến có project/road version/segment nullable; phải xác định phạm vi trước giao tác nghiệp, không tự gán sai tuyến.
- Vòng đời riêng: `New -> Assigned -> Open -> Fixed -> Retest -> Verified -> Closed`. Assigned là giao PM; Open là PM tiếp nhận/kiểm chứng/chờ duyệt/tổ chức sửa, không đồng nghĩa đã giao sửa.
- `Open -> Fixed` cần đúng Crew được giao từ phiên bản sửa đã duyệt, toàn bộ hạng mục bắt buộc nộp đủ kết quả/bằng chứng. PM tổ chức Retest; chỉ PM xác nhận tất cả hạng mục đạt mới Verified; Supervisor xác nhận Closed đối với hồ sơ đã sửa.
- `Retest -> Open` khi không đạt, giữ các lần sửa/kiểm tra và kết quả đạt từng hạng mục. Đổi phạm vi, phương án hoặc chi phí cần duyệt version mới trước khi giao phần phát sinh. Từ chối kinh phí không tự kết luận không lỗi hoặc đóng hồ sơ.
- PM có thể đóng không sửa với `ClosureReason = NoDefect | Duplicate | OutOfScope`, lý do/bằng chứng; Duplicate bắt buộc hồ sơ chính và được đóng từ New/Assigned/Open, NoDefect/OutOfScope từ Open. Không bỏ qua Retest/Verified để đóng với lý do đã sửa. Tái phát tạo hồ sơ mới liên kết hồ sơ đóng.
- `Defect VERIFIED` là xác nhận hư hỏng **trước sửa**; `IncidentCase Verified` là nghiệm thu **sau sửa**. Không dùng chung enum hoặc đổi nghĩa dữ liệu cũ.

---

## 3. Survey

### `SurveyPlan` [R]
- Entity con: `SurveyPlanPostponement` (list, append).
- **Invariant:** hoãn kế hoạch không hủy yêu cầu khảo sát đã tạo — nghĩa là **`SurveyPlan` và `SurveyRequest` là 2 aggregate độc lập**, chỉ liên kết lỏng qua `project_id` (US-04 mục 3, US-05 mục 6).
- PM vẫn lập khảo sát gốc/định kỳ chủ động mà không có `IncidentReport`/`IncidentCase`; nguồn phản ánh là tùy chọn, không thay thế lịch bảo hành.

### `SurveyRequest` [R]
- Entity con: `SurveyAssignment` (trạng thái phân công hiện tại + lịch sử).
- **Invariant (state machine chính, US-05):**
  - Operator chỉ được từ chối khi trạng thái = `Mới giao`; đã `Đã nhận` thì không tự từ chối được (mục 3).
  - Phân công lại → lưu người cũ/mới/lý do (mục 4).
  - **[Cross-aggregate]** Chỉ hủy được khi **chưa** có `SurveyDataVersion` được server xác nhận toàn vẹn (mục 5) — domain service phải query aggregate `SurveyDataVersion` trước khi cho phép hủy.
- **Domain Events:** `SurveyRequestAssigned`, `SurveyRequestRejected`, `SurveyRequestCancelled`.

### `SurveyWorkItem` [R]
- Tham chiếu `survey_request_id` và đúng bộ/segment/phiên bản tuyến đã công bố; một request có nhiều work item, một work item có nhiều lượt bay/video. Thu tuyến trước khi có segment (`RouteCapture`) là nhánh khởi tạo riêng cần thiết kế/triển khai rõ, không dùng segment giả.
- Entity con: `SurveyCoverageRequirement` (mỗi band yêu cầu), `SurveyCoverageResult` (append theo requirement + `survey_data_version_id`), `SurveyVideoInterval` (requirement + dataset + file/video gốc + flight + khoảng thời gian).
- `TargetBand` ∈ {`Surface`, `LeftEdge`, `RightEdge`} (mã lưu `SURFACE`, `LEFT_EDGE`, `RIGHT_EDGE`); trái/phải nhìn theo chiều tăng lý trình, không đổi khi bay ngược. Tuyến nhiều phần đường cần xác nhận phần đường/mép cụ thể. Một lượt có thể phục vụ nhiều segment/band, một band có thể cần nhiều lượt; không bắt ba chuyến bay.
- Kết quả độ phủ từng segment/band là `Sufficient`, `Partial`, `Insufficient`, `Unknown`; GPS/checksum tốt hoặc AI chạy xong không chứng minh vùng cần nhìn đã đủ. Giữ kết quả band đạt, bổ sung band thiếu, không kết luận không lỗi ở vùng thiếu.
- Giữ riêng raw aircraft GPS, hành lang bay dự kiến, pose/calibration, footprint/ROI quan sát, lý trình đối chiếu và vị trí Defect. Offset có chủ đích không tự là GPS lỗi; không suy ra mép/vị trí lỗi chỉ từ GPS drone. Giữ GPS/SRT gốc và phương pháp/độ tin cậy đối chiếu, không đổi tuyến theo từng track.
- Khoảng video được xác định theo thời gian/vùng nhìn thấy và lý trình có căn cứ, không chia theo tốc độ đặt trước. Không nội suy qua mất GPS thành độ phủ giả; không có telemetry thì không tạo GPS giả. Clip dẫn xuất giữ checksum và ánh xạ thời gian về video gốc; video dùng cho nhiều segment chỉ upload một lần.

### `SupplementarySurveyRequest` [R]
- Aggregate độc lập cho yêu cầu khảo sát/bay bổ sung; không phải entity con của `Survey`.
- Có thể tham chiếu `survey_id` để chỉ khảo sát phát sinh yêu cầu và tham chiếu `survey_request_id` nếu được tạo từ một yêu cầu khảo sát hiện hữu.
- Vòng đời, phê duyệt và phân công của yêu cầu bổ sung không làm thay đổi ownership của aggregate `Survey`.

### `Survey` [R] *(entity mới từ review vòng 2)*
- Entity con: `Flight` (list), `SurveyFile` (list).
- Field: `survey_type` (ORIGINAL/PERIODIC/SUPPLEMENTARY), `is_baseline_confirmed`, `road_section_version_id`.
- **Invariant:**
  - `is_baseline_confirmed = true` chỉ được set qua hành động PM xác nhận riêng (US-04 mục 5), **không** tự động dù dữ liệu đã xử lý xong.
  - **[Cross-aggregate]** Xác nhận baseline bị chặn nếu dữ liệu chưa toàn vẹn/thiếu định vị hoặc phạm vi/band bắt buộc chưa đạt, `ProcessingJob` chưa hoàn tất, hoặc còn phát hiện chưa được PM xử lý dứt điểm. Mỗi phát hiện phải bị loại có lý do hoặc ánh xạ tới `Defect`; mọi `Defect OPEN` phải được PM kết luận `VERIFIED`/`REJECTED` từ bằng chứng đủ căn cứ. Task đo chỉ bắt buộc hoàn tất nếu đã được yêu cầu để giải quyết phần bằng chứng còn thiếu.

### `SurveyDataVersion` [R]
- Tham chiếu `survey_id`.
- **Invariant:** chuyển `Đã đồng bộ an toàn` chỉ khi server xác nhận đủ tệp + checksum pass (US-02 mục 4, US-06 mục 6).
- Chỉ Backend/System Worker được chuyển `status = SERVER_CONFIRMED`; Drone Operator và PM không được tự xác nhận version.
- **Domain Events:** `SurveyDataConfirmed` → cho phép chuẩn bị manifest, `ProcessingBlock`/`ProcessingJob` (aggregate khác); toàn vẹn tệp không thay thế kiểm tra chất lượng đầu vào của từng band.

### `FieldInspectionTask` [R]
- Aggregate nghiệp vụ cho nhiệm vụ PM giao Repair Crew kiểm chứng khi bằng chứng chưa đủ hoặc cần số đo vật lý; cũng tạo trực tiếp từ hồ sơ phản ánh trước khi có Survey/Defect.
- Entity con: `FieldInspectionAssignment` (lịch sử giao, từ chối và bàn giao; đúng một assignment active tại một thời điểm).
- Tham chiếu `project_id`, `road_section_version_id`, PM giao việc, yêu cầu đo/kiểm tra, phạm vi, thời hạn và Crew hiện tại. Nguồn bất biến `source_type = DEFECT` yêu cầu `defect_id` và không có `incident_case_id`; `source_type = INCIDENT_CASE` yêu cầu `incident_case_id` và không có `defect_id` nguồn. Hai nguồn loại trừ nhau; Defect tạo sau liên kết qua hồ sơ/kết quả, không đổi nguồn task.
- `survey_id` nullable: nguồn Defect dùng survey nguồn khi có; nguồn IncidentCase không cần Survey hoặc Defect. Nếu có tham chiếu phụ thì phải cùng project/phiên bản tuyến và đúng nguồn; không tạo Survey/Defect giả để thỏa FK.
- **State machine:** `NEW_ASSIGNED` → `ACCEPTED` hoặc `REJECTED`; `ACCEPTED` → `IN_PROGRESS` → `SUBMITTED`; PM đánh giá `SUBMITTED` thành `SUPPLEMENT_REQUIRED` hoặc `COMPLETED`. Khi bổ sung, tạo session/phép đo mới và quay lại `IN_PROGRESS`, không ghi đè dữ liệu cũ.
- **Invariant:** task cần assignment hợp lệ và bằng chứng phù hợp yêu cầu; không bắt mỗi `Defect OPEN` có task. Repair Crew chỉ được từ chối trước khi nhận; sau khi nhận, PM thực hiện điều chuyển.
- Quyết định cuối của PM là `DEFECT_CONFIRMED` hoặc `NO_DEFECT`; quyết định, người, thời điểm và lý do phải được lưu trước khi task `COMPLETED`.

### `FieldInspectionSession` [R]
- Đại diện một phiên đo hiện trường dùng cho workflow sản phẩm hoặc Research Validation; `purpose` ∈ {`DEFECT_VERIFICATION`, `RESEARCH_VALIDATION`}.
- Với `DEFECT_VERIFICATION`, bắt buộc tham chiếu `field_inspection_task_id`; người đo phải là Repair Crew thuộc assignment hiện hành.
- Với `RESEARCH_VALIDATION`, `field_inspection_task_id` phải null và có thể nhập từ Excel/giấy theo quy trình nghiên cứu.
- **Invariant:** session phải ghi thời điểm, điều kiện hiện trường, người kiểm tra/đo, phương pháp, bằng chứng và danh sách mẫu khi có yêu cầu đo; session đã gửi/khóa không update-in-place. Research Validation vẫn phải có mẫu ground truth theo đề cương.

### `GroundTruthMeasurement` [R]
- Aggregate độc lập cho một phép đo vật lý tại một `sample_id` duy nhất.
- `measurement_type` tối thiểu gồm `DEPRESSION_DEPTH` và `SLAB_FAULTING_HEIGHT`; có thể thêm `SHOULDER_EROSION_EXTENT` khi thực hiện giả thuyết nghiên cứu.
- Bắt buộc có `field_inspection_session_id`, `road_section_version_id`, vị trí, giá trị, đơn vị, dụng cụ, phương pháp, người đo, thời điểm và bằng chứng.
- Với session `DEFECT_VERIFICATION`, phép đo phải cùng nguồn/phạm vi task; nguồn `DEFECT` tham chiếu đúng Defect, nguồn `INCIDENT_CASE` cho phép `defect_id` null trước khi PM tạo/liên kết Defect. Không bắt tạo Defect cho kết luận `NO_DEFECT`. Với `RESEARCH_VALIDATION`, `defect_id` có thể null để không biến sample nghiên cứu thành Defect sản phẩm.

### `DerivedMeasurement` [R]
- Aggregate cho số đo do DSM/surface model hoặc pipeline xử lý tạo ra để ghép với ground truth.
- Tham chiếu `survey_data_version_id`, `road_section_version_id`, tùy chọn `defect_id`, `measurement_type`, giá trị, đơn vị, uncertainty và phiên bản thuật toán/model.
- Immutable sau khi công bố; chạy lại pipeline tạo bản ghi/version mới, không ghi đè kết quả cũ.

### `MeasurementValidationRun` [R]
- Đại diện một lần phân tích đối chiếu cho một tập mẫu và một phương pháp/model cụ thể.
- Lưu phạm vi mẫu, `derived_measurement_source`, tiêu chí loại outlier, số mẫu hợp lệ, bias, MAE, RMSE, độ không chắc chắn và phương pháp tính.
- Kết quả chỉ là bằng chứng đánh giá khoa học; không tự chuyển trạng thái Defect hoặc kết luận thuộc/ngoài Warranty.

### `MeasurementValidationSample`
- Entity con của `MeasurementValidationRun`, ghép đúng một `GroundTruthMeasurement` với đúng một `DerivedMeasurement`.
- Lưu sai số có dấu, sai số tuyệt đối, trạng thái sử dụng (`INCLUDED`, `EXCLUDED`, `OUTLIER`) và lý do loại mẫu nếu có.

### `QualityCheck` [R]
- Aggregate độc lập, có `scope` phân biệt `SURVEY_FILE` và `SURVEY_DATASET`.
- `execution_stage = CLIENT_PRECHECK`: Drone App kiểm tra sơ bộ định dạng, định vị, thời gian, độ rõ/ánh sáng và cảnh báo vùng phủ trước hoặc trong khi tải; kết quả này không xác nhận toàn vẹn máy chủ.
- `execution_stage = SERVER_VALIDATION`: Backend/System Worker kiểm tra MIME thực, kích thước, malware, checksum, quan hệ nguồn, completeness, coverage/overlap và tính nhất quán; đây là kết quả chính thức dùng để chặn/mở xử lý.
- `SURVEY_FILE` dùng cho định dạng, định vị, đồng bộ của từng `SurveyFile`.
- `SURVEY_DATASET` dùng cho vùng phủ, chồng lấn và các kiểm tra cần toàn bộ dữ liệu; **neo canonical vào `survey_data_version_id`**. `SurveyDataVersion` tham chiếu `survey_id`, nên không cần lưu thêm `survey_id` trên `QualityCheck`.
- Nếu cần kiểm tra trước khi nộp, tạo `SurveyDataVersion` ở trạng thái nháp trước khi chạy kiểm tra; chỉ bản đã server-confirm mới được chuyển sang xử lý.
- Ràng buộc dữ liệu: `scope = SURVEY_FILE` → đúng `survey_file_id`; `scope = SURVEY_DATASET` → đúng `survey_data_version_id`; không được có cả hai hoặc không có đích.
- PM chỉ đọc/tổng hợp `QualityCheck` và tạo `SupplementarySurveyRequest` khi cần; PM không đổi kết quả kỹ thuật từ `FAILED` thành `PASSED`.
- Chất lượng định vị đánh giá track với hành lang bay và độ liên tục; độ phủ/ảnh đánh giá footprint/ROI của từng band. Track lệch tim tuyến có chủ đích không tự `FAILED`; không nhìn thấy mép được yêu cầu vẫn thiếu dữ liệu dù GPS hợp lệ.

---

## 4. Processing

### `ProcessingBlock` [R]
- Tham chiếu dataset, `road_section_version_id`, `segment_set_id`, `segment_id`, `target_band`, phạm vi chính và ngữ cảnh mở rộng cấu hình được. Đây là đơn vị phân tích/retry, khác segment quản lý và lượt bay; không cắt mất ngữ cảnh tại biên segment.
- Quan hệ: 1 `SurveyDataVersion` → N `ProcessingBlock` → nhiều job lịch sử, một job hiện hành theo cấu hình phân tích. Có thể batch để dùng GPU nhưng phải theo dõi kết quả mỗi segment/band.

### `ProcessingJob` [R]
- Tham chiếu `processing_block_id`, `model_version_id`.
- Entity con: `ProcessingAttempt` (list).
- **Invariant:** phải phân biệt lỗi hạ tầng (retry được trên dữ liệu nguyên vẹn, tạo `ProcessingAttempt` mới) và lỗi dữ liệu (không dùng retry, chuyển PM quyết định bổ sung — US-07 mục 4-5, QT08 mục 5). Đây là **business rule dễ bị agent code sai nhất** trong nhóm Processing nếu không tách rõ 2 loại lỗi ngay từ enum `error_type` trên `ProcessingAttempt`.
- Một `ProcessingInputManifest` bất biến trên job chứa contract version, correlation/backend job ID, dataset/segment/band/phiên bản tuyến, hình học/hệ tọa độ, file/checksum, các khoảng video gốc, telemetry/time mapping, pose/calibration nếu có, model/preprocessing/config version và chất lượng đã biết. Fingerprint không phụ thuộc URL tải tạm thời.
- Lưu job và yêu cầu dispatch bền vững trước trả `202 Accepted`/status URL; worker gọi adapter AI bên ngoài bất đồng bộ, theo dõi/polling trạng thái. Adapter mock và AI thật dùng hợp đồng có nguồn kết quả rõ; không giữ request FE đợi GPU.
- Retry cùng manifest/model/config dùng cùng backend job/idempotency key, có giới hạn/backoff và lịch sử attempt; payload khác cùng key bị từ chối. Sau mất kết nối truy vấn danh tính job đã gửi. Đổi dataset/model/config/phạm vi tạo job mới; job/bộ segment cũ không bị sửa.
- Xác thực kết quả theo job, input checksum, schema, model, nguồn file, timestamp/frame/bbox và phạm vi; kết quả gốc bất biến. Nhận lặp không nhân đôi detection; kết quả muộn của job/attempt bị thay thế không ghi đè kết quả hiện hành. Hủy BE chưa chứng minh AI đã ngừng.
- Chỉ cấp AI quyền đọc file cần thiết với thời hạn/phạm vi; không gửi PII Reporter, phê duyệt hoặc chi phí. Không tải URL kết quả tùy ý ngoài storage cho phép.
- `Succeeded` chỉ là xử lý xong; `No detections` không là kết luận PM `NoDefect`. Hoàn tất phân tích cần mọi block bắt buộc có kết quả được chấp nhận, vẫn công bố chất lượng/độ phủ thiếu riêng.

### `AIModelVersion` [R] *(config, Admin quản lý)*
- **Invariant:** đổi phiên bản mô hình **không** cascade update lên `AIDetection.model_version_id` cũ — tham chiếu đó bất biến vĩnh viễn (QT06 mục 2).

---

## 5. AI & Defect

### `AIDetection` [R]
- **Immutable** sau khi tạo — không có action update/delete trong domain model này.
- Tham chiếu `processing_job_id`, `model_version_id`.
- MVP có thể giữ field ước lượng 2D: `estimated_width`, `estimated_length`, `is_2d_estimate = true`.
- Số đo vật lý và số đo surface model phục vụ đề cương không đặt trực tiếp vào `AIDetection`; dùng `GroundTruthMeasurement` và `DerivedMeasurement` để giữ nguồn gốc, uncertainty và cặp validation.
- Danh tính detection ổn định trong job; lưu file/video/time/frame/bbox hoặc mask, band yêu cầu, bên quan sát suy ra và confidence riêng, lý trình/vị trí/phương pháp/sai số khi có căn cứ. Thiếu pose/calibration/định vị thì vị trí null/unknown hoặc ước lượng rõ ràng, không lấy GPS drone làm GPS lỗi; nhãn yêu cầu không chứng minh đã nhìn đúng bên.
- Giữ quan sát gốc từ nhiều frame/block/lượt bay. Gợi ý trùng dùng phạm vi, thời gian, loại, bên và bằng chứng; hai mép đối diện không gộp chỉ vì gần nhau. Trường hợp mơ hồ do PM quyết định.

### `Defect` [R]
- Entity con: `DefectVerificationLog` (list, append), `DefectObservation` (nguồn quan sát), `DefectSegment` (segment bị ảnh hưởng).
- **Invariant:**
  - Khi PM giữ lại hoặc hiệu chỉnh một `AIDetection`, tạo `Defect.status = OPEN`; đây là `Preliminary Defect`, chưa phải hư hỏng chính thức.
  - PM có thể loại `AIDetection` rõ ràng sai ngay ở bước rà soát mà không tạo `Defect`; quyết định được ghi log nhắm tới detection. Nguồn hồ sơ phản ánh/kiểm tra trực tiếp có thể tạo Defect khi PM xác định cần hồ sơ chuyên môn, không yêu cầu Survey hoặc AIDetection giả; phản ánh chưa kiểm chứng không tự là Defect đã xác nhận.
  - Chuyển `OPEN` → `VERIFIED`/`REJECTED` cần quyết định PM với bằng chứng drone hoặc thực địa đủ căn cứ, actor/thời điểm/lý do và nguồn. Nếu cần số đo vật lý hoặc bằng chứng chưa đủ thì giao task; khi đã yêu cầu task cho quyết định đó, cần task `COMPLETED`, session/bằng chứng đã gửi/khóa và kết luận tương ứng `DEFECT_CONFIRMED`/`NO_DEFECT`. Không mặc định mọi lỗi đều phải đo.
  - Mọi sửa loại/mức độ/vị trí → lưu trước/sau trong `DefectVerificationLog` (US-08 mục 3).
  - **Không** tự chuyển trạng thái "Đã loại bỏ" chỉ vì kích thước nhỏ hoặc confidence thấp — phải có hành động PM tường minh (US-08 mục 5).
  - `DefectVerificationLog` phải nhắm đúng một trong `ai_detection_id` hoặc `defect_id`. `action` phân biệt `PRELIMINARY_KEEP`, `ADJUST`, `CONFIRM`, `REJECT`, `MERGE`; log `CONFIRM` và log `REJECT` từ `OPEN` nhắm Defect, ghi căn cứ quyết định. `field_inspection_task_id` chỉ bắt buộc khi quyết định dựa vào nhiệm vụ thực địa.
  - Severity tính theo `SeverityRuleVersion` tại thời điểm xác minh chính thức; lưu snapshot `severity_rule_version_id` trên `DefectVerificationLog`, không tính lại khi rule đổi version.
  - Lỗi vắt qua ranh giới vẫn là một Defect/nhiệm vụ sửa, liên kết nhiều segment/quan sát; segment chính chọn theo quy tắc có căn cứ vị trí. Chưa định vị đủ thì giữ phạm vi ứng viên chờ xác minh. Quan sát các kỳ không bị ghi đè, đối sánh tái phát chỉ là gợi ý đến khi PM quyết định.

### `DefectMergeDecision`
- Ghi lại hành động gộp/giữ riêng — **thao tác thực sự (merge 2 Defect thành 1, giữ liên kết AIDetection nguồn)** nên coi là 1 **operation trong `Defect` aggregate**, không phải aggregate riêng có logic riêng (US-09 mục 1-2).

### `DefectMatch` [R]
- Tham chiếu `defect_id` (A), `defect_id` (B, kỳ khác), `match_confidence`, `match_method`, `reviewed_by`.
- Không cần strong consistency với `Defect` — chỉ là liên kết đối sánh, aggregate độc lập nhẹ.

### `SeverityRuleVersion` [R] *(config, versioned)*
### `TrainingLabelApproval` [R], `TrainingDatasetExport` [R] *(workflow riêng, độc lập)*

---

## 6. Repair

### `RepairBatch` [R]
- Field: `current_version_id` (con trỏ tới `RepairBatchVersion` hiện hành). Bản thân `RepairBatch` là aggregate "mỏng" — chỉ giữ định danh + trỏ tới version hiện tại.

### `RepairBatchVersion` [R] *(aggregate nặng nhất hệ thống)*
- Entity con: `RepairItem` (list — **copy mới khi tạo version mới, không share với version cũ**), `RepairApprovalDecision` (list, per item).
- **Invariant:**
  - **[Cross-aggregate]** Tạo bản nháp → chặn nếu `Defect` được chọn đã thuộc một `RepairBatchVersion` khác đang ở trạng thái "đang thực hiện" (SC01 mục 1: "chặn lỗi bị giao trùng") — phải query cross-aggregate trước khi thêm `RepairItem`.
  - **[Cross-aggregate]** Chỉ tạo `RepairItem` khi `Defect.status = VERIFIED` có quyết định PM dựa trên bằng chứng hợp lệ; nếu đã yêu cầu task kiểm chứng thì task phải hoàn tất. Chặn `OPEN`, `REJECTED` hoặc phần bằng chứng bắt buộc còn thiếu.
  - PM nhập `repair_proposal` (phương án tổng quát) trên version và `estimated_cost` từng item để tổng hợp. `RepairItem` giữ liên kết lỗi, chi phí, trạng thái; không quản lý vật liệu, định mức, khối lượng, giai đoạn/bước thi công hoặc ưu tiên chi tiết (UD-06 cập nhật).
  - Trình → khóa version, chuyển `Chờ duyệt`, snapshot toàn bộ phạm vi lỗi/phương án/chi phí tại thời điểm trình (SC03).
  - Duyệt → chỉ version hiện tại chuyển `Đã duyệt`; **chỉ version này** đủ điều kiện phân công (SC04).
  - Trả chỉnh sửa → **không** tự triển khai phần lỗi đã được chấp thuận riêng lẻ (SC05) — toàn đợt quay về PM cùng lúc.
  - Trình lại → tạo version mới, giữ nguyên version cũ, yêu cầu duyệt lại **toàn bộ** đợt, không duyệt từng phần (SC06).

### `RepairAssignment` [R]
- **Invariant:**
  - Chỉ `RepairBatchVersion.status = Đã duyệt` (và là version hiện tại) mới cho phép phân công (US-12 mục 1).
  - Thay đổi người được phân công không làm thay đổi version đã duyệt. Nếu thay đổi danh sách lỗi, phương án hoặc chi phí thì bắt buộc tạo `RepairBatchVersion` mới (US-12 mục 5, UD-06).

### `RepairProgress` [R], `RepairEvidence` [R] *(append-only, không ghi đè bản gốc — US-13 mục 5)*
- Ghi kết quả tổng quát và ảnh/video trước/sau, vị trí/thời điểm; không biến tiến độ xử lý thành giai đoạn kỹ thuật thi công. Bằng chứng phải server-confirm trước dùng cho hoàn tất/nghiệm thu.
### `RepairInspectionResult` [R]
- **Invariant:** 1 lỗi "Đạt" **không** bị kéo lùi trạng thái chỉ vì lỗi khác trong cùng đợt "Chưa đạt" — mỗi `RepairItem` có trạng thái nghiệm thu độc lập (US-14 mục 2).
- Lưu từng lần sửa/kiểm tra. Crew không tự nghiệm thu; PM quyết định đạt, Supervisor đóng hồ sơ sau Verified; `ReportStatusEvent` chỉ công bố ảnh/kết quả đúng lỗi liên quan theo quyền Reporter.

### `UnplannedDefectReport` [R]
- **Invariant:** phát hiện lỗi ngoài phạm vi tại hiện trường → tạo báo cáo riêng, **không** tự thêm vào `RepairBatchVersion` đã duyệt (US-13 mục 6, quy tắc 14 Use Case) — phải qua flow xác minh/phê duyệt phạm vi riêng (có thể dẫn tới `Defect` mới + `RepairBatchVersion` mới sau này, ngoài phạm vi domain model v1 này).

---

## 7. Evidence / File / Audit

### `File` [R], `Evidence` [R]
- `Evidence`: cột FK nullable riêng từng loại đích (`defect_id`, `repair_item_id`, `handover_document_id`...) + CHECK constraint đúng 1 cột non-null. Append-only.

### `AuditLog`
- **Không phải business aggregate** — là event sink chung, nhận domain event từ **mọi** aggregate khác. **Fields audit chuẩn:** `actor_user_id`, `occurred_at`, `event_type`, `entity_type`, `entity_id`, `before_snapshot`, `after_snapshot`, `reason`, `source`, `correlation_id`.
- Append-only, chỉ đọc; không lưu mật khẩu/token. `PasswordResetLog` và `AccountStatusChangeLog` vẫn được lưu riêng; `AuditLog` không thay thế chúng.

### `ReportExport` [R]

---

## 8. Administration & Retention

### `ReminderRule` [R] *(config)*
### `DataRetentionRequest` [R]
- **Invariant [Cross-aggregate]:** chặn lập/duyệt xóa nếu tồn tại `LegalHold` active trên phạm vi liên quan (US-19 mục 3) — phải query aggregate `LegalHold` trước khi duyệt.
### `LegalHold` [R]
### `RetentionDeletionLog` [R] *(compliance record — giữ riêng khỏi AuditLog vì có ý nghĩa pháp lý khác biệt)*

---

## Tổng hợp: Cross-Aggregate Invariants (quan trọng nhất cho AI agent)

Đây là các quy tắc **FK/schema không tự enforce được** — bắt buộc có domain service/application-layer check, nếu bỏ sót thì DB vẫn "hợp lệ" nhưng sai nghiệp vụ:

| # | Quy tắc | Aggregate cần đọc chéo | Nguồn |
|---|---|---|---|
| 1 | Survey/Defect và phạm vi tác nghiệp phải neo vào đúng phiên bản tuyến/bộ segment; không di chuyển lịch sử khi chia lại | `RoadSection`, `RoadSegmentSet`, `SurveyWorkItem`, `Defect`, `ProcessingBlock` | US-03, Incident/Segment |
| 2 | Hủy `SurveyRequest` bị chặn nếu `SurveyDataVersion` đã server-confirm | `SurveyDataVersion` | US-05 mục 5 |
| 3 | Baseline cần dataset toàn vẹn, band/phạm vi đạt, job hoàn tất, không còn Defect OPEN/phát hiện chưa xử lý; task hoàn tất khi được yêu cầu | `Survey`, `SurveyWorkItem`, `ProcessingJob`, `Defect`, `FieldInspectionTask` | US-04, UD-05 cập nhật |
| 4 | RepairItem chỉ dùng Defect VERIFIED có quyết định PM/bằng chứng đủ, task hoàn tất nếu được yêu cầu; chặn lỗi thuộc đợt khác đang thực hiện | `Defect`, `FieldInspectionTask`, `RepairBatchVersion` | SC01, US-11, UD-05 cập nhật |
| 5 | `RepairAssignment` yêu cầu `RepairBatchVersion.status = Đã duyệt` | `RepairBatchVersion` | US-12 mục 1 |
| 6 | Thay đổi phạm vi lỗi, phương án hoặc chi phí đã duyệt → bắt buộc version mới và duyệt lại trước giao sửa | `RepairBatchVersion`, `RepairAssignment` | US-12, UD-06 cập nhật |
| 7 | Duyệt `DataRetentionRequest` chặn nếu có `LegalHold` active | `LegalHold` | US-19 mục 3 |
| 8 | `Session` phải bị thu hồi khi `User` bị suspend hoặc reset password | `User` | US-01 mục 2, 6 |
| 9 | Ground truth nghiên cứu phải ghép đúng mẫu với số đo derived trước khi tính uncertainty | `FieldInspectionSession`, `GroundTruthMeasurement`, `DerivedMeasurement`, `MeasurementValidationRun` | Đề cương, RS01–RS06 |
| 10 | Research validation không tự tạo Defect hoặc kết luận trách nhiệm Warranty | `MeasurementValidationRun`, `Defect`, `Warranty` | Đề cương; tách mục đích bằng `FieldInspectionSession.purpose` |
| 11 | PM kết luận Defect từ drone/thực địa đủ căn cứ; cần đo khi thiếu bằng chứng/cần số đo vật lý; session/phép đo đã gửi bất biến | `Defect`, `AIDetection`, `FieldInspectionTask`, `FieldInspectionSession`, `GroundTruthMeasurement` | AI13, TN01–TN06, UD-05 cập nhật |
| 12 | Reporter chỉ đọc report của mình và nội dung công khai; subtype InvestorRepresentative không thêm quyền, không lộ danh tính report liên quan | `User`, `IncidentReport`, `IncidentCase` | Incident/Segment §2, §4 |
| 13 | Nguồn task XOR IncidentCase/Defect; nguồn trực tiếp không yêu cầu Survey/Defect; mọi tham chiếu phụ đúng project/phiên bản tuyến | `FieldInspectionTask`, `IncidentCase`, `Defect`, `Survey` | Incident/Segment §4 |
| 14 | Receiving/Accepted/DefectFound/NoDefect do hành động PM; NoDefect có lý do, không suy ra từ AI rỗng/từ chối kinh phí/trùng report | `IncidentReport`, `IncidentCase`, `Defect`, `ProcessingJob` | Incident/Segment §4–5 |
| 15 | Fixed cần đủ hạng mục/bằng chứng; Verified cần PM kiểm tra tất cả đạt; Closed sau sửa cần Supervisor; không xóa kết quả đạt khi hạng mục khác phải sửa lại | `IncidentCase`, `RepairBatchVersion`, `RepairAssignment`, `RepairInspectionResult`, `RepairEvidence` | Incident/Segment §5–6 |
| 16 | Công bố REPAIRED chỉ sau Verified + PM chọn ảnh sau sửa đã xác nhận và đúng phạm vi Reporter | `IncidentReport`, `IncidentCase`, `RepairInspectionResult`, `RepairEvidence`, `File` | Incident/Segment §4.2 |
| 17 | Job chỉ dùng manifest/dataset xác nhận và đúng segment/band/model; retry không nhân đôi, kết quả muộn không ghi đè; công bố bộ mới giữ job cũ | `SurveyDataVersion`, `SurveyWorkItem`, `RoadSegmentSet`, `ProcessingBlock`, `ProcessingJob`, `AIModelVersion`, `AIDetection` | AI/Segment/Edge §3, §5–9 |
| 18 | Độ phủ từng band độc lập trạng thái AI; raw GPS/corridor/footprint/Defect position riêng; offset chủ đích không tự là GPS lỗi | `SurveyWorkItem`, `QualityCheck`, `ProcessingJob`, `AIDetection` | AI/Segment/Edge §4, §7 |
| 19 | Một lỗi qua biên/nhiều lượt bay giữ nhiều quan sát/segment, PM quyết định gộp; không nhân đôi sửa; ánh xạ mới phải có căn cứ vị trí | `AIDetection`, `Defect`, `RoadSegmentSet`, `RepairBatchVersion` | AI/Segment/Edge §8 |
| 20 | Gộp report vào hồ sơ chính giữ nguồn/bằng chứng; chuyển trạng thái/giao lại/duyệt/nộp kết quả chống cập nhật đồng thời và lặp request | `IncidentReport`, `IncidentCase`, `SurveyRequest`, `FieldInspectionTask`, `RepairBatchVersion` | Incident/Segment §6 |

---

## Trạng thái quyết định

Đây là mô hình đích 22/09/2026; không dùng danh sách aggregate để suy ra mức hoàn thành runtime. TN01–TN06, TN12/AI13 vẫn hỗ trợ kiểm chứng/đo khi cần; Research Validation là nhánh mục đích riêng với ground truth bắt buộc. Phải đối chiếu code và thiết kế migration khi triển khai, giữ lịch sử trạng thái, task và phiên bản dữ liệu hiện hữu.
