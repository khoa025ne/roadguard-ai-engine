# Đặc tả use case RoadGuard / CÁT TƯỜNG

> Phạm vi bàn giao BE — 18/09/2026: đợt hiện tại phát triển backend ASP.NET Core; Android/Web thuộc FE, AI thật và thu thập số đo thực địa là tích hợp bên ngoài ở giai đoạn sau. Backend vẫn triển khai đầy đủ workflow bắt buộc, adapter AI giả lập xác định và chức năng Research Validation nhập/ghép/tính sai số/xuất báo cáo bằng dữ liệu kiểm thử hoặc dữ liệu ngoài đã có. Nghiệm thu phần mềm BE không tuyên bố độ chính xác AI hay kết quả thực nghiệm từ dữ liệu giả. Các yêu cầu sản phẩm/nghiên cứu đầy đủ bên dưới vẫn được giữ để truy vết. Xem [ADR 003](../adr/003-backend-delivery-and-ai-boundary.md).

Phiên bản thiết kế đồng bộ 22/09/2026 — dùng kèm các sơ đồ trong thư mục này. Các yêu cầu mới dưới đây là thiết kế mục tiêu, chưa xác nhận đã triển khai backend; ghi chú bàn giao 18/09/2026 ở trên là phạm vi lịch sử.  
Căn cứ thêm: [Data Dictionary](RoadGuard_Data_Dictionary_v1.md) là chuẩn dữ liệu/công nghệ ưu tiên; đề cương `RoadGuard_Contractor_Warranty_Inspection_phuonglhk.md` và các quyết định đã chốt (vai trò tiếng Anh, khảo sát gốc bàn giao, Backend C# + hệ AI ngoài qua adapter, **thu thập ground truth nghiên cứu là bắt buộc**).

## 1. Cơ sở và ranh giới

Căn cứ đề cương RoadGuard_Contractor_Warranty_Inspection_phuonglhk.md, tài liệu yêu cầu hệ thống đã chốt và đặc biệt là [Data Dictionary](RoadGuard_Data_Dictionary_v1.md). Khi có khác biệt, tên entity, field, kiểu dữ liệu logic, quan hệ và quy tắc trong Data Dictionary được dùng làm chuẩn; tài liệu tổng kết/giao diện cũ chỉ là tham khảo.

Ranh giới bao gồm ứng dụng di động Android, trang web (Web Dashboard), Backend, lưu trữ, dữ liệu không gian, và dịch vụ AI tách biệt. Có bốn vai trò nhân sự nội bộ và vai trò thứ năm `Reporter` cho người dân/đại diện chủ đầu tư; Reporter không cần membership dự án để gửi và xem phản ánh của mình. Thiết bị bay thu thập dữ liệu ngoài thực địa; hệ thống này **không** điều khiển thiết bị bay.

### 1.1 Kiến trúc logic (đã hướng)

```
┌─────────────────────────────────────────────────────────────┐
│                    HỆ THỐNG ROADGUARD                       │
├─────────────────────────────────────────────────────────────┤
│  Android App              Web Dashboard                     │
│  (Drone Operator,         (Supervisor/Admin, PM, Reporter)            │
│   Repair Crew, Reporter)                                    │
│           │                        │                        │
│           └──────────┬─────────────┘                        │
│                      ▼                                      │
│           Backend Server (C# / ASP.NET Core)                │
│           - API, nghiệp vụ, auth, queue                     │
│           - Database (SQL Server + SQL Server Spatial)      │
│           - File storage                                    │
│                      │                                      │
│                      ▼  Adapter async / mock có nhãn nguồn      │
│           External AI Service                               │
│           - Nhận video / job                                │
│           - Phát hiện hư hỏng (YOLO…)                       │
│           - Trả JSON: loại, confidence, bbox, GPS, metadata │
└─────────────────────────────────────────────────────────────┘
```

| Thành phần | Công nghệ gợi ý | Vai trò |
|---|---|---|
| Backend | **C#**, ASP.NET Core, SQL Server + SQL Server Spatial, EF Core | Auth, dự án, khảo sát, đợt sửa, gọi AI, lưu kết quả |
| AI Service bên ngoài | Hệ AI qua hợp đồng có phiên bản; Python/YOLO chỉ là một hướng triển khai | Xử lý manifest theo phiên bản dữ liệu/segment/vùng quan sát; trả ứng viên phát hiện |
| Giao tiếp BE ↔ AI | Adapter, job bền vững, REST bất đồng bộ/polling | BE trả 202 + JobId sau khi lưu job; worker gọi AI; mock và AI thật cùng hợp đồng có nguồn rõ ràng |
| Android | Kotlin | Upload video/SRT, nhiệm vụ, ảnh trước/sau, sync |
| Web Dashboard | (chưa bắt buộc chốt framework) | Quản lý dự án, xác minh AI, duyệt đợt, báo cáo |

Backend sở hữu nghiệp vụ, lưu trữ và điều phối job; AI là hệ thống tích hợp bên ngoài qua adapter/hợp đồng có phiên bản. Python là hướng triển khai trước đây, không ràng buộc nhà cung cấp mới. Mock vẫn dùng để kiểm thử hợp đồng và phải ghi rõ nguồn mock; không tự xác nhận hư hỏng. Xem [thiết kế phản ánh/segment](RoadGuard_Incident_Segment_Design_v1.md) và [thiết kế AI/edge](RoadGuard_AI_Segment_Edge_Design_v1.md).

### 1.2 Tác nhân

| Tác nhân | Trách nhiệm |
|---|---|
| **Supervisor** (kèm quyền **Admin**) | Tạo dự án; nhập tuyến/đoạn đường sau bàn giao; phân công PM; duyệt danh sách lỗi và chi phí đợt sửa; xác nhận hoàn tất cuối cùng. Quyền Admin: cấp tài khoản, đặt lại mật khẩu, cấu hình, nhật ký, quản trị mô hình/dữ liệu. |
| **PM** (Project Manager) | Lập kế hoạch và yêu cầu khảo sát (gồm khảo sát gốc); hủy/thu hồi yêu cầu chưa có dữ liệu đã nộp; giao Drone Operator; kiểm tra danh sách phát hiện AI sơ bộ; tiếp nhận phản ánh, chia segment; chọn drone hoặc Repair Crew kiểm chứng và giao đo khi cần; đánh giá bằng chứng rồi xác minh hư hỏng chính thức; yêu cầu/xác nhận bay bổ sung; lập đợt sửa; giao Repair Crew thi công; kiểm tra kết quả và trình Supervisor. **Một dự án chỉ có một PM chính; một PM có thể quản lý nhiều dự án.** |
| **Drone Operator** | Nhận/từ chối nhiệm vụ; thu thập và nhập video/SRT; theo dõi đồng bộ, chất lượng và xử lý; nộp dữ liệu bay bổ sung. |
| **Repair Crew** | Đội trưởng có tài khoản; nhận/từ chối đợt sửa hoặc nhiệm vụ đo đạc thực tế khi được giao; ghi số đo/bằng chứng; báo cáo tiến độ và hoàn thành. Thành viên đội không có tài khoản riêng. |

| **Reporter** | Gửi/bổ sung phản ánh, xác nhận vị trí riêng từng ảnh, xem tiến độ và kết quả được công bố của chính mình. `ReporterType = CITIZEN / INVESTOR_REPRESENTATIVE` (Citizen / InvestorRepresentative) không cấp quyền dự án, duyệt hoặc xem chi phí nội bộ. |

## 2. Cách đọc sơ đồ

Có các nhóm tổng quan, được phân rã thành các mục trong sơ đồ chi tiết. Một số mục là hành vi con bắt buộc, không có liên kết trực tiếp tới tác nhân; chúng được gọi qua «include». Đây là danh mục chức năng, không phải số màn hình hay số API.

- Đường liền không mũi tên: tác nhân tham gia chức năng.
- A «include» B: A bắt buộc thực hiện hành vi B trong điều kiện của A.
- A «extend» B: A bổ sung cho B khi điều kiện trên đường nối xảy ra.
- Đăng nhập, quyền dự án, phiên bản hồ sơ và trạng thái hợp lệ được áp dụng làm điều kiện chung.
- Gửi hồ sơ, duyệt hồ sơ và giao việc là các tương tác riêng qua nhiều thời điểm; không nối «include» chỉ để diễn tả bước trước/sau.

## 3. Quy tắc nghiệp vụ xuyên suốt

1. **Supervisor** tạo dự án. PM/Drone Operator/Repair Crew chỉ thấy dữ liệu trong phạm vi được phân công; Repair Crew không tự nhận đợt của đội khác. Reporter đăng nhập và chỉ xem phản ánh của chính mình cùng kết quả được công bố, không cần và không tự được cấp membership dự án.
2. **Một dự án chỉ có một PM chính. Một PM có thể quản lý nhiều dự án cùng lúc.** Supervisor phân công đúng một PM khi tạo/cập nhật dự án.
3. **Khảo sát gốc sau bàn giao:** sau khi công trình được bàn giao (ngoài hệ thống), Supervisor nhập dữ liệu đoạn đường / tuyến vào hệ thống, gắn hồ sơ bàn giao và thời hạn bảo hành, rồi phân công PM. PM lập yêu cầu khảo sát gốc (baseline), giao Drone Operator bay lần đầu để lấy dữ liệu mẫu phục vụ đối chiếu bảo hành trong thời gian bảo hành (hồ sơ lưu tối thiểu hết bảo hành + 5 năm — xem quy tắc lưu trữ).
4. Một yêu cầu khảo sát có thể gom nhiều segment và nhiều video/lượt bay. PM chọn bộ segment đã công bố và vùng `Surface`, `LeftEdge`, `RightEdge`; Backend chia ProcessingBlock để giới hạn tài nguyên, không đồng nhất block, segment và lượt bay. Khảo sát gốc/định kỳ không cần có phản ánh. RouteCapture trước khi có segment là nhiệm vụ khởi tạo riêng, chưa phải tính năng hiện có.
5. Nhập video phải sao chép vào bộ nhớ thiết bị và kiểm tra bản sao; không phụ thuộc thẻ nhớ còn cắm. Trích phụ đề định vị từ MP4 nếu có; cho bổ sung SRT tương ứng khi cần. SRT không được mặc định là nhật ký bay đầy đủ.
6. Khi có mạng và mở lại ứng dụng, hệ thống tiếp tục tải dữ liệu theo hàng đợi, có thể dùng Wi-Fi hoặc dữ liệu di động. Chỉ dọn bản sao cục bộ khi máy chủ xác nhận toàn vẹn và người dùng chủ động chọn dọn.
7. Lỗi định dạng, thiếu định vị hoặc dữ liệu không đạt được thông báo cụ thể. Sự cố máy chủ dùng cơ chế thử lại. **PM là người quyết định và xác nhận bay bổ sung** vùng chưa đạt, có thể đổi người và không giới hạn số lượt; mỗi lượt giữ lý do, phạm vi và nguồn gốc.
8. PM kiểm tra, hiệu chỉnh hoặc loại bỏ kết quả AI nhưng phải lưu lý do và lịch sử trước/sau. Kết quả được giữ lại là `Preliminary Defect`, ánh xạ bằng `Defect.status = OPEN` và chưa được xác minh chính thức; kết quả bị loại bỏ vẫn được lưu để đối chiếu. Nhãn được PM duyệt; Admin (Supervisor) phát hành mô hình.
9. Kết quả AI MVP gồm loại hư hỏng, độ tin cậy, khung bao (bounding box), liên kết khung hình/thời gian và vị trí GPS khi có. Kích thước vật lý trong MVP có thể chỉ là ước lượng 2D; không coi đầu ra YOLO tự có độ sâu hay độ chính xác địa lý đã bảo đảm. Tuy nhiên, **đề cương nghiên cứu bắt buộc** phải có một bộ dữ liệu validation riêng: kỹ sư đo thực địa bằng straightedge/depth gauge tại một mẫu điểm, ghép với số đo từ surface model và tính sai số/độ không chắc chắn. Bộ dữ liệu nghiên cứu này không biến toàn bộ pipeline nâng cao thành tiêu chí nghiệm thu MVP.
10. **Kiểm chứng theo căn cứ:** PM chọn drone hoặc Repair Crew kiểm tra trực tiếp; dữ liệu drone đủ căn cứ có thể được PM xác nhận. Khi cần độ sâu/chênh cao/kích thước vật lý hoặc ảnh/định vị chưa đủ, đo thực địa là bắt buộc trước quyết định cần số đo đó. Số đo lưu trong `FieldInspectionSession`/`GroundTruthMeasurement` với loại đo, đơn vị, dụng cụ, phương pháp, người/thời điểm, vị trí và bằng chứng. Kiểm tra từ phản ánh không bắt có Survey/Defect được xác nhận; không tạo Survey giả. AI/số đo không tự chuyển `Defect` hay `Warranty`; PM quyết định. Ground truth nghiên cứu RS01–RS06 vẫn bắt buộc và độc lập.
11. PM chọn các `Defect VERIFIED` đã có bằng chứng được chấp nhận; nếu cần đo thì phải hoàn tất và được PM chấp nhận. PM nhập `RepairProposal` dạng phương án tổng quát và `EstimatedCost`; liên kết lỗi/tổng hợp chi phí theo phạm vi, không quản lý vật liệu, định mức, nhân công, giai đoạn hay quy trình thi công chi tiết. Supervisor duyệt phiên bản gồm phạm vi, phương án và chi phí; chỉnh sửa phải giữ lịch sử và trình lại khi ảnh hưởng phê duyệt.
12. Chỉ giao Repair Crew khi phiên bản đợt hiện tại đã được duyệt. Một Repair Crew (đội trưởng) có thể quản lý nhiều đợt. Thay đổi danh sách lỗi, phương án tổng quát hoặc chi phí ngoài phê duyệt phải trình lại trước khi triển khai phần thay đổi.
13. Bằng chứng trước/sau, số liệu thực hiện và kết quả kiểm tra quản lý theo từng lỗi. PM kiểm tra rồi trình Supervisor; Supervisor xác nhận cuối cùng. Lỗi chưa đạt quay lại Repair Crew phụ trách; chỉ sửa lại những lỗi đó.
14. Lỗi phát sinh tại hiện trường phải đi qua xác minh và phê duyệt phạm vi; không tự chen vào công việc đã duyệt.
15. Thông tin nghiệp vụ ngừng sử dụng vẫn giữ lịch sử. Nhật ký truy vết chỉ đọc, lưu người/thời gian/trước/sau và nguồn dữ liệu.
16. Hồ sơ dự án lưu ít nhất đến hết bảo hành cộng 5 năm. Việc xóa sau hạn phải được Supervisor duyệt; đang giữ hồ sơ tranh chấp thì không được xóa.
17. Khi tài khoản bị ngừng sử dụng (QT01) mà còn nhiệm vụ hoặc đợt dở dang: hệ thống thu hồi phiên, chặn đăng nhập mới, **không xóa lịch sử** và **không tự hủy hay tự hoàn tất** công việc đang mở. Hệ thống lập danh sách việc cần bàn giao và thông báo người có quyền phân công lại. **Drone Operator:** PM phân công lại người bay (KS04); dữ liệu đã nộp được giữ. **Repair Crew:** PM phân công lại nhiệm vụ đo đạc (TN01) hoặc đợt sửa (SC11); bằng chứng đã gửi vẫn gắn đúng lỗi/đợt. **PM:** Supervisor gán đúng một PM mới (DA03); PM mới tiếp nhận yêu cầu khảo sát, đợt sửa và hồ sơ đang trình. Bản nháp trên thiết bị giữ nguyên chủ sở hữu; khi có mạng nếu tài khoản đã ngừng thì không đồng bộ và không chuyển nháp sang người khác.
18. **Chuẩn dữ liệu bắt buộc:** `Warranty` là aggregate riêng; `Survey.is_baseline_confirmed` là cờ xác nhận baseline; `SupplementarySurveyRequest` độc lập với `Survey`; `QualityCheck` phải trỏ đúng một trong `survey_file_id` hoặc `survey_data_version_id`; `Evidence` phải có đúng một FK nghiệp vụ đích. `Survey`, `Defect` và các phép đo phải neo vào `RoadSectionVersion` cụ thể khi có vị trí.
19. **Chuẩn kỹ thuật:** Backend dùng C# / ASP.NET Core / EF Core với SQL Server + SQL Server Spatial. GPS/raw location dùng `geography(4326)`; geometry kỹ thuật dùng UTM `32648` hoặc `32649` theo cấu hình dự án. JSON logic ánh xạ SQL Server `nvarchar(max)` và phải qua kiểm tra `ISJSON` cùng schema ứng dụng; không dùng cú pháp PostgreSQL/PostGIS trong use case hoặc API contract.

## 4. Danh mục chức năng và kết quả mong đợi

### 01. Truy cập và làm việc ngoại tuyến

| Mã | Chức năng | Tác nhân trực tiếp | Quy tắc / kết quả |
|---|---|---|---|
| CN01 | Đăng nhập / đăng xuất | Supervisor; PM; Drone Operator; Repair Crew; Reporter | Tài khoản do Admin cấp; phiên đăng nhập mang snapshot vai trò nhưng backend phải đối chiếu vai trò và quyền dự án hiện tại phía server trên mỗi request. Phiên hết hạn, mật khẩu đã đặt lại (CN10), tài khoản bị suspend hoặc role toàn hệ thống thay đổi thì thu hồi toàn bộ phiên/token và phải đăng nhập lại. |
| CN02 | Xem và cập nhật hồ sơ cá nhân | Supervisor; PM; Drone Operator; Repair Crew; Reporter | Chỉnh thông tin cá nhân; không tự thay đổi vai trò hay quyền dự án. |
| CN03 | Xem phạm vi dữ liệu được phép | Supervisor; PM; Drone Operator; Repair Crew; Reporter | Supervisor có quyền danh mục sau kiểm tra role server-side; PM/Drone Operator/Repair Crew cần membership active, còn hiệu lực và đúng vai trò. Reporter chỉ xem phản ánh của mình và dữ liệu công bố liên quan theo ownership; không truy cập API danh mục dự án. Không tin claim client thay cho kiểm tra quyền. |
| CN04 | Xem thông báo và nhắc việc | Supervisor; PM; Drone Operator; Repair Crew; Reporter | Hiển thị thông báo phù hợp vai trò: khảo sát, kết quả, duyệt, sửa lại, từ chối/hủy nhiệm vụ, phân công lại, đến hạn bảo hành; Reporter chỉ nhận sự kiện công bố của phản ánh mình. |
| CN05 | Lưu công việc và bản đồ phục vụ ngoại tuyến | Drone Operator; Repair Crew | Chuẩn bị dữ liệu đã được phép truy cập để tra cứu khi mất mạng; phạm vi bản đồ phụ thuộc dữ liệu đã tải. |
| CN06 | Lưu bản nháp và bằng chứng khi không có mạng | Drone Operator; Repair Crew | Lưu dữ liệu trong bộ nhớ ứng dụng và hiển thị trạng thái chưa đồng bộ. |
| CN07 | Theo dõi và tiếp tục đồng bộ dữ liệu | Drone Operator; Repair Crew | Khi có mạng và mở lại ứng dụng, tiếp tục hàng đợi; hỗ trợ Wi-Fi và dữ liệu di động. |
| CN08 | Kiểm tra trạng thái đồng bộ an toàn | Drone Operator; Repair Crew | Chỉ báo đã đồng bộ khi máy chủ xác nhận đủ dữ liệu và kiểm tra tính toàn vẹn thành công. |
| CN09 | Dọn bản sao cục bộ đã đồng bộ an toàn | Drone Operator; Repair Crew | Người dùng chủ động chọn dọn; giữ bản chưa đồng bộ và dữ liệu nguồn trên máy chủ. |
| CN10 | Yêu cầu / đặt lại mật khẩu | Supervisor; PM; Drone Operator; Repair Crew; Reporter | Người dùng gửi yêu cầu khôi phục. **Chỉ Supervisor (Admin) đặt lại mật khẩu**; bắt đổi mật khẩu ở lần đăng nhập kế tiếp. Không tiết lộ mật khẩu cũ. Ghi nhật ký người thực hiện và thời điểm (QT09), không ghi mật khẩu. Tài khoản đang ngừng sử dụng thì từ chối đặt lại. |

### 02. Dự án, bảo hành và kế hoạch khảo sát

| Mã | Chức năng | Tác nhân trực tiếp | Quy tắc / kết quả |
|---|---|---|---|
| DA01 | Tạo và cập nhật dự án | Supervisor | Supervisor tạo dự án sau (hoặc gắn với) bàn giao công trình; cập nhật thông tin quản lý công trình. |
| DA02 | Quản lý tuyến và đoạn đường | Supervisor | **Sau bàn giao, Supervisor nhập** hình học, lý trình, loại mặt đường và phạm vi công trình vào hệ thống; khác với các khối xử lý video. Mọi chỉnh sửa hình học/lý trình sau khi đoạn đã có khảo sát, lỗi hoặc đợt sửa đều **tạo phiên bản mới**: giữ hình học cũ, lý do, người và thời điểm; dữ liệu khảo sát/lỗi không bị tự gắn lại sang hình học mới. Ngừng sử dụng đoạn thay vì xóa. |
| DA03 | Phân công nhân sự và quyền theo dự án | Supervisor | **Giao đúng một PM chính cho mỗi dự án**; giao Drone Operator và Repair Crew theo nhu cầu; không cấp quyền xem dự án khác ngoài phạm vi. Một PM có thể được giao nhiều dự án. |
| DA04 | Quản lý hồ sơ bàn giao và thông tin bảo hành | Supervisor | Ngày nghiệm thu/bàn giao, thời hạn bảo hành, ngày hết bảo hành, giá trị giữ lại và tài liệu liên quan. |
| DA05 | Xem hồ sơ dự án và thời hạn bảo hành | Supervisor; PM | PM xem dự án được giao; Supervisor xem toàn danh mục. |
| DA06 | Lập và điều chỉnh kế hoạch khảo sát định kỳ | PM | Lập kế hoạch cho dự án, **gồm khảo sát gốc (baseline) ngay sau bàn giao** và các lần kiểm tra tiếp theo trong thời gian bảo hành, kể cả khi chưa có phản ánh. |
| DA07 | Xem lịch và nhắc khảo sát sắp đến hạn | PM | Nhắc theo lịch và trước hạn bảo hành; nhắc việc không tự tạo lệnh bay. |
| DA08 | Tạo yêu cầu khảo sát từ kế hoạch hoặc phát sinh | PM | Chọn công trình, phạm vi cần kiểm tra, loại yêu cầu (gốc / định kỳ / phát sinh), thời hạn và yêu cầu đầu ra. |
| DA09 | Ghi nhận hoãn / không triển khai khảo sát theo kế hoạch | PM | Bắt buộc lý do; nếu thời tiết có thể lên lịch ngày khác; lưu lịch sử quyết định. |
| DA10 | Chọn và xác nhận hồ sơ khảo sát gốc bàn giao | PM | Sau khi dữ liệu khảo sát gốc đã xử lý và được xác minh đủ, PM chọn/xác nhận phiên bản gốc để so sánh các lần sau trong bảo hành. |
| DA11 | Xem tình trạng công trình qua các kỳ khảo sát | Supervisor; PM | Theo dõi lỗi còn mở, mức độ và thay đổi so với hồ sơ gốc. |
| DA12 | Đóng / ngừng sử dụng dự án và tra cứu hồ sơ đã đóng | Supervisor | Ngừng tác nghiệp thông thường nhưng giữ hồ sơ theo thời hạn lưu trữ; không xóa cứng. |

### 03. Phân công khảo sát và tiếp nhận dữ liệu bay

| Mã | Chức năng | Tác nhân trực tiếp | Quy tắc / kết quả |
|---|---|---|---|
| KS01 | Phân công người bay cho yêu cầu khảo sát | PM | Giao đích danh một Drone Operator; yêu cầu có thể cần nhiều video. |
| KS02 | Xem và tiếp nhận yêu cầu khảo sát | Drone Operator | Người được giao xem phạm vi, thời hạn, hướng dẫn và xác nhận tiếp nhận; nếu không nhận được thì dùng KS03. |
| KS03 | Từ chối nhiệm vụ khảo sát kèm lý do | Drone Operator | Chỉ khi trạng thái Mới giao (chưa tiếp nhận). Lý do bắt buộc. Trả yêu cầu về PM để phân công lại (KS04). Đã nhận thì không tự từ chối; PM điều chỉnh phân công. |
| KS04 | Điều chỉnh lịch và phân công lại người bay | PM | Có thể đổi người thực hiện; lưu người cũ, người mới, lý do và lịch mới. |
| KS05 | Ghi nhận thông tin chuyến bay và tài liệu khảo sát | Drone Operator | Lưu thiết bị, thời gian, phạm vi đã bay, ghi chú và tài liệu thực hiện chuyến bay. |
| KS06 | Nhập và sao chép video từ thẻ nhớ vào ứng dụng | Drone Operator | Sao chép thật vào bộ nhớ thiết bị; không chỉ lưu đường dẫn trên thẻ nhớ; kiểm tra bản sao. |
| KS07 | Bổ sung tệp phụ đề định vị tương ứng với video | Drone Operator | Dùng khi video không có luồng phụ đề trích xuất được; kiểm tra ghép đúng video và thời gian. |
| KS08 | Kiểm tra tính hợp lệ và chất lượng dữ liệu khảo sát | Drone Operator | Kiểm tra định dạng, định vị, đồng bộ thời gian, độ rõ, ánh sáng, vùng phủ và độ chồng lấn; báo vùng không đạt. |
| KS09 | Gửi bộ dữ liệu khảo sát và theo dõi tải lên | Drone Operator | Nhiều video trong cùng lần khảo sát; xếp hàng ngoại tuyến; tiếp tục tải khi có mạng và mở ứng dụng. |
| KS10 | Xem tiến độ xử lý và kết quả kiểm tra chất lượng | Drone Operator; PM | Theo dõi trạng thái tiếp nhận, xử lý, hoàn tất hoặc lỗi; Backend gọi AI Service sau khi dữ liệu hợp lệ (hoặc trả mock ở Phase 1). |
| KS11 | Yêu cầu / xác nhận bay bổ sung vùng dữ liệu chưa đạt | PM | **PM xác nhận** cần bay bổ sung; chỉ rõ vùng và lý do; không giới hạn số lần; có thể giao người khác. |
| KS12 | Nộp dữ liệu bay bổ sung vào cùng lần khảo sát | Drone Operator | Giữ dữ liệu cũ và nguồn gốc mỗi lượt; hợp nhất có kiểm tra vùng phủ và đối sánh. |
| KS13 | Yêu cầu thử lại tác vụ xử lý thất bại | PM; Supervisor | Lỗi máy chủ thử lại trên dữ liệu đã lưu; lỗi dữ liệu chuyển PM quyết định bổ sung. |
| KS14 | Hủy / thu hồi yêu cầu khảo sát kèm lý do | PM | Lý do bắt buộc. Được hủy khi chưa có bộ dữ liệu máy chủ đã xác nhận toàn vẹn (chưa nhận hoặc đã nhận nhưng chưa nộp). Thông báo Drone Operator nếu đã giao/đã nhận. Không hủy khi đã có dữ liệu nộp thành công — khi đó chỉ điều chỉnh phân công (KS04) hoặc yêu cầu bổ sung (KS11). Yêu cầu đã hủy không xóa cứng; lưu trạng thái, lý do và lịch sử. Khác DA09 (hoãn kế hoạch, chưa tạo lệnh bay) và KS04 (đổi người/lịch, không hủy hẳn). |

### 04. Khai thác AI, rà soát sơ bộ và theo dõi hư hỏng

| Mã | Chức năng | Tác nhân trực tiếp | Quy tắc / kết quả |
|---|---|---|---|
| AI01 | Xem kết quả phân tích trên bản đồ và ảnh khảo sát | PM | Xem lỗi dự kiến, loại, độ tin cậy, khung bao và liên kết ảnh/video nguồn. |
| AI02 | Xem ảnh trực giao và mô hình bề mặt | PM | Hiển thị sản phẩm xử lý ảnh theo đề cương khi pipeline hỗ trợ; phạm vi phủ và trạng thái chất lượng. (Nâng cao / theo đề cương.) |
| AI03 | Xem vị trí, kích thước và độ không chắc chắn | PM | Trong sản phẩm: phân biệt ước lượng 2D, số đo surface model (nếu pipeline hỗ trợ) và số đo thực địa. Trong nghiên cứu: các số đo phải được ghép cặp và báo cáo sai số/độ không chắc chắn; không gán kích thước thật chỉ từ khung bao. |
| AI04 | Giữ lại phát hiện sơ bộ để kiểm chứng | PM | Tạo `Defect OPEN` biểu diễn `Preliminary Defect`, lưu nguồn/người/thời gian; PM chọn drone hoặc thực địa, chưa xác minh chính thức. Không tự tạo nhiệm vụ đo cho mọi phát hiện. |
| AI05 | Hiệu chỉnh loại, mức độ, vị trí và vùng hư hỏng | PM | Cho phép sửa kết quả sai; lưu nguồn AI và phiên bản sau chỉnh; dữ liệu sửa có thể dùng làm nhãn. |
| AI06 | Loại bỏ phát hiện sai và giữ hồ sơ đối chiếu | PM | Đánh dấu đã loại bỏ, không xóa; giữ ảnh gốc và dữ liệu phục vụ kiểm tra, huấn luyện. |
| AI07 | Ghi lý do và lịch sử quyết định rà soát/xác minh | Hành vi con trong chức năng cha | Lưu người thực hiện, thời điểm, giá trị trước/sau, phiên bản mô hình và liên kết bằng chứng kiểm chứng và số đo khi cần để xác minh chính thức. |
| AI08 | Đối chiếu các phát hiện trùng cùng một hư hỏng | PM | AI có thể đề xuất gộp; **PM xác nhận gộp hoặc giữ riêng**. Tránh đếm một lỗi nhiều lần; giữ audit. |
| AI09 | Đối chiếu cùng hư hỏng qua nhiều lần khảo sát | PM | Xác nhận hoặc sửa ghép nối; dùng chung định danh lỗi khi đủ bằng chứng. |
| AI10 | Xem lịch sử và so sánh với hồ sơ gốc bàn giao | PM; Supervisor | Xem lần đầu xuất hiện, hình ảnh, số đo và quyết định theo thời gian so với baseline (DA10). |
| AI11 | Xem lỗi mới, ổn định hoặc đang phát triển | PM; Supervisor | So sánh các kỳ tương thích; báo thiếu dữ liệu khi chưa đủ căn cứ tính mức tăng trưởng. |
| AI12 | Xem cảnh báo hư hỏng cần ưu tiên kiểm tra | PM; Supervisor | Cảnh báo mức độ cao, thay đổi nhanh hoặc nứt cần theo dõi; không cam kết dự báo thời điểm hỏng. |
| AI13 | Yêu cầu đo đạc thực tế khi cần căn cứ vật lý | PM | Khi cần số đo vật lý hoặc bằng chứng chưa đủ, PM bắt buộc giao Repair Crew đo; dùng `FieldInspectionSession`/`GroundTruthMeasurement`. PM đánh giá kết quả trước kết luận cần số đo đó; không áp dụng như tiền điều kiện chung cho mọi Defect. |
| AI14 | Duyệt nhãn hư hỏng phục vụ huấn luyện | PM | Kiểm tra loại và vùng nhãn từ kết quả đã sửa hoặc báo cáo hiện trường trước khi đưa vào tập dữ liệu. |

### 05. Đo đạc thực tế theo nhu cầu kiểm chứng

| Mã | Chức năng | Tác nhân trực tiếp | Quy tắc / kết quả |
|---|---|---|---|
| TN01 | Giao nhiệm vụ đo đạc thực tế | PM | Giao Repair Crew khi kiểm chứng cần số đo; chỉ rõ nguồn IncidentCase hoặc Defect, phiên bản tuyến/phạm vi nếu đã xác định, loại đo và thời hạn. Liên kết Survey khi có; nguồn phản ánh trực tiếp không bị buộc tạo Survey giả. |
| TN02 | Xem và tiếp nhận nhiệm vụ đo đạc | Repair Crew | Đội trưởng xác nhận tiếp nhận; nếu từ chối trước khi nhận thì dùng TN12. |
| TN03 | Ghi số đo và bằng chứng tại hiện trường | Repair Crew | Ghi `measurement_type` (`DEPRESSION_DEPTH`, `SLAB_FAULTING_HEIGHT` hoặc `SHOULDER_EROSION_EXTENT`), `value`, `unit`, `instrument_name`, `measurement_method`, `measured_at`, vị trí `geography(4326)` và `evidence_file_id`; hỗ trợ ngoại tuyến. |
| TN04 | Gửi kết quả đo đạc cho PM | Repair Crew | Đồng bộ đầy đủ trước khi gửi chính thức; tạo/khóa bản ghi `FieldInspectionSession` và `GroundTruthMeasurement`. |
| TN05 | Đánh giá kết quả đo đạc và xác minh chính thức | PM | Kiểm tra đủ field, đơn vị, dụng cụ, vị trí, bằng chứng và tính phù hợp với `road_section_version_id`; chấp nhận để chuyển `Defect OPEN` sang `VERIFIED` khi bằng chứng đủ (kèm số đo nếu cần), yêu cầu bổ sung hoặc chuyển `REJECTED` có lý do; đo không phải điều kiện chung nếu không cần phép đo. |
| TN06 | Yêu cầu bổ sung phép đo/bằng chứng | PM | Nêu rõ mẫu hoặc loại đo còn thiếu; không ghi đè phép đo cũ, tạo bản ghi/phiên bản mới. |
| TN12 | Từ chối nhiệm vụ đo đạc thực tế kèm lý do | Repair Crew | Chỉ khi trạng thái Mới giao (chưa tiếp nhận). Lý do bắt buộc. Trả nhiệm vụ về PM để giao lại (TN01). Đã nhận thì không tự từ chối; PM điều chỉnh phân công. |

### 06. Lập, phê duyệt và phân công đợt sửa chữa

| Mã | Chức năng | Tác nhân trực tiếp | Quy tắc / kết quả |
|---|---|---|---|
| SC01 | Chọn và gộp thủ công nhiều lỗi vào một đợt sửa | PM | Chỉ chọn `Defect VERIFIED` có bằng chứng được PM chấp nhận; nếu yêu cầu số đo vật lý thì nhiệm vụ đo phải hoàn tất/được chấp nhận. Tránh giao trùng lỗi đang thuộc đợt sửa đang thực hiện. |
| SC02 | Nhập phương án tổng quát và chi phí sửa dự kiến | PM | Nhập `RepairProposal` dạng văn bản và `EstimatedCost` cho phạm vi lỗi đề xuất; không lập bảng vật liệu, định mức hoặc các giai đoạn thi công chi tiết. |
| SC03 | Tính tổng chi phí đợt sửa | PM | Hệ thống cộng chi phí từng lỗi và tính lại khi danh sách lỗi hoặc số tiền thay đổi. |
| SC04 | Trình toàn bộ đợt sửa cho Supervisor phê duyệt | PM | Gửi danh sách lỗi, phương án tổng quát, chi phí và bằng chứng dưới một phiên bản hồ sơ. |
| SC05 | Thẩm định và quyết định phê duyệt toàn bộ đợt sửa | Supervisor | Supervisor duyệt **cả đợt**; đợt chỉ sẵn sàng phân công khi phiên bản hiện tại được duyệt đầy đủ. |
| SC06 | Đánh giá chi phí dự kiến | Hành vi con trong chức năng cha | Kiểm tra phương án tổng quát, chi phí cho phạm vi lỗi và tổng dự toán của phiên bản đang trình. |
| SC07 | Ghi lỗi chưa được chấp thuận và lý do yêu cầu chỉnh sửa | Supervisor | Có thể chỉ yêu cầu chỉnh một số lỗi; đợt quay lại PM để cập nhật. |
| SC08 | Chỉnh sửa hồ sơ đợt sửa theo yêu cầu Supervisor | PM | Sửa các mục bị trả lại, lưu phản hồi và thay đổi; giữ lịch sử các mục trước đó. |
| SC09 | Tính lại chi phí và trình lại toàn bộ đợt sửa | PM | Tạo phiên bản mới, tính lại tổng; không triển khai riêng phần cũ khi toàn đợt chưa duyệt. |
| SC10 | Phân công Repair Crew sau khi đợt sửa được duyệt | PM | Giao đích danh một đội trưởng phụ trách đợt; một đội trưởng có thể nhận nhiều đợt. |
| SC11 | Điều chỉnh phân công Repair Crew phụ trách | PM | Ghi lý do và lịch sử bàn giao; thay đổi danh sách lỗi hoặc chi phí đã duyệt phải trình lại. |
| SC12 | Theo dõi tiến độ và lịch sử phê duyệt đợt sửa | Supervisor; PM | Tra cứu phiên bản hồ sơ, người duyệt, thời điểm và tình trạng từng lỗi. |

### 07. Thi công, kiểm tra và xác nhận hoàn tất

| Mã | Chức năng | Tác nhân trực tiếp | Quy tắc / kết quả |
|---|---|---|---|
| HT01 | Xem và tiếp nhận đợt sửa chữa được giao | Repair Crew | Xem danh sách lỗi, lịch, chi phí đã duyệt và yêu cầu bằng chứng. Xác nhận tiếp nhận; nếu không nhận được thì dùng HT15. |
| HT02 | Xem vị trí và hướng dẫn tiếp cận lỗi tại hiện trường | Repair Crew | Sử dụng tọa độ, bản đồ và ảnh tham chiếu; hiển thị độ chính xác/ước lượng khi có. |
| HT03 | Ghi chú tổ chức đội thực hiện | Repair Crew | Giữ ghi chú/phân công tổng quát của đội trưởng; thành viên không có tài khoản riêng. Không quản lý kế hoạch thi công theo giai đoạn, vật tư, nhân công hoặc định mức. |
| HT04 | Ghi bằng chứng trước và sau sửa chữa từng lỗi | Repair Crew | Ảnh, thời gian, vị trí, ghi chú; giữ bản gốc và tách trạng thái trước/sau. |
| HT05 | Cập nhật tiến độ và chi phí thực tế | Repair Crew | Ghi tình trạng và chi phí thực tế từng lỗi để PM đối chiếu. |
| HT06 | Báo cáo hư hỏng mới phát hiện tại hiện trường | Repair Crew | Lỗi phát sinh chuyển về PM xác minh; không tự thêm vào phạm vi đã duyệt. |
| HT07 | Gửi báo cáo hoàn thành cho PM | Repair Crew | Báo cáo theo từng lỗi trong đợt; hoàn tất đồng bộ và kiểm tra bằng chứng bắt buộc. |
| HT08 | Kiểm tra đủ bằng chứng trước/sau từng lỗi | Hành vi con trong chức năng cha | Chặn gửi chính thức nếu thiếu ảnh bắt buộc hoặc còn bản chưa đồng bộ. |
| HT09 | Kiểm tra kết quả sửa chữa của từng lỗi | PM | Đối chiếu chi phí đã duyệt, bằng chứng và kết quả; ghi đạt/chưa đạt kèm nhận xét. |
| HT10 | Yêu cầu sửa lại những lỗi chưa đạt | PM; Supervisor | PM hoặc Supervisor chỉ rõ lỗi chưa đạt và lý do; trả đúng Repair Crew đang phụ trách. |
| HT11 | Trình kết quả hoàn thành cho Supervisor xác nhận | PM | Chỉ trình kết quả đã được PM kiểm tra; giữ hồ sơ từng lỗi và chi phí thực tế. |
| HT12 | Xác nhận hoàn tất các lỗi và đợt sửa chữa | Supervisor | Supervisor quyết định cuối cùng; đợt chỉ đóng khi toàn bộ lỗi trong phạm vi đã đạt. |
| HT13 | Thực hiện sửa lại và bổ sung báo cáo từng lỗi | Repair Crew | Chỉ làm lại lỗi bị trả; giữ bằng chứng cũ, bổ sung phiên bản mới rồi gửi lại qua PM. |
| HT14 | Xem lịch sử sửa chữa và chi phí sau hoàn tất | Supervisor; PM; Repair Crew | Supervisor xem toàn bộ; PM và Repair Crew xem hồ sơ thuộc phạm vi phân công. |
| HT15 | Từ chối đợt sửa chữa được giao kèm lý do | Repair Crew | Chỉ khi đợt đã phân công và chưa tiếp nhận. Lý do bắt buộc. Không hủy đợt đã duyệt và không đổi phạm vi/chi phí. PM phân công lại (SC11). Cấm từ chối khi đã nhận, đang thi công hoặc đã có bằng chứng. |

### 08. Báo cáo quản lý và hồ sơ bằng chứng

| Mã | Chức năng | Tác nhân trực tiếp | Quy tắc / kết quả |
|---|---|---|---|
| BC01 | Xem tổng quan danh mục dự án bảo hành | Supervisor | Tình trạng, lỗi còn mở, dự án sắp hết hạn và tình trạng khảo sát. |
| BC02 | Xem tổng quan dự án được phân công | PM | Chỉ báo tương tự trong phạm vi quyền của PM. |
| BC03 | Xem chi phí sửa chữa dự kiến và thực tế | Supervisor; PM | Phân biệt dự toán đang chờ duyệt, đã duyệt và chi phí đã thực hiện; tránh cộng trùng. |
| BC04 | Xem công trình rủi ro cao và hư hỏng phát triển nhanh | Supervisor; PM | Hỗ trợ ưu tiên kiểm tra/sửa chữa; hiển thị căn cứ và độ tin cậy của chỉ báo. |
| BC05 | So sánh tình trạng giữa các dự án và kỳ khảo sát | Supervisor | So sánh tỷ lệ lỗi theo loại mặt đường, giai đoạn và phạm vi dữ liệu có thể so sánh. |
| BC06 | Xuất báo cáo theo dự án và khoảng thời gian | Supervisor; PM | Bộ lọc thời gian, phạm vi quyền và trạng thái được lưu trong thông tin báo cáo. |
| BC07 | Xuất hồ sơ bằng chứng cho đoạn đường hoặc một lỗi | Supervisor; PM | Chọn đoạn đường/toàn đoạn, lỗi nếu cần, và khoảng thời gian; đề xuất PDF tổng hợp kèm ZIP dữ liệu gốc. |
| BC08 | Tổng hợp ảnh gốc, số đo, lịch sử và quyết định | Hành vi con trong chức năng cha | Gồm hồ sơ bàn giao, khảo sát hiện tại, loại/số đo/độ không chắc chắn, sửa chữa, trách nhiệm (khi có) và phiên bản mô hình. |
| BC09 | Kèm nguồn gốc và thông tin kiểm tra toàn vẹn hồ sơ | Hành vi con trong chức năng cha | Kèm mã tệp, dấu kiểm tra toàn vẹn, thời gian, tác giả và lịch sử sửa đổi để đối chiếu. |
| BC10 | Tra cứu hồ sơ lưu trữ sau khi dự án đã đóng | Supervisor; PM | Dữ liệu vẫn truy xuất theo quyền trong thời hạn bảo hành cộng 5 năm hoặc lâu hơn khi còn giữ hồ sơ tranh chấp. |

### 09. Quản trị, mô hình AI và vòng đời dữ liệu

| Mã | Chức năng | Tác nhân trực tiếp | Quy tắc / kết quả |
|---|---|---|---|
| QT01 | Tạo, cập nhật và ngừng sử dụng tài khoản | Supervisor (Admin) | Không xóa lịch sử hành động khi tài khoản ngừng sử dụng. Khi ngừng mà còn việc mở: liệt kê việc cần bàn giao, thông báo PM/Supervisor; phân công lại theo quy tắc 17. |
| QT02 | Quản lý vai trò và quyền truy cập dự án | Supervisor (Admin) | Phân quyền theo năm vai trò; Reporter dùng ownership phản ánh, subtype không tăng quyền; thay đổi quyền được ghi nhật ký và có hiệu lực ngay. Đổi role toàn hệ thống phải thu hồi toàn bộ phiên/refresh token trong cùng transaction; đổi, hết hạn hoặc kết thúc quyền project phải được guard server-side áp dụng từ request kế tiếp. |
| QT03 | Quản lý danh mục loại lỗi | Supervisor (Admin) | Ngừng sử dụng mục cũ thay vì làm mất dữ liệu lịch sử. |
| QT04 | Quản lý bộ quy tắc phân mức và dung sai có phiên bản | Supervisor (Admin) | Cố định quy tắc vận hành theo chuẩn đã chọn và loại mặt đường; thay phiên bản phải lưu căn cứ. |
| QT05 | Cấu hình nhắc khảo sát và nhắc trước hạn bảo hành | Supervisor (Admin) | Quản lý giá trị mặc định, nhắc định kỳ và mốc sắp hết hạn; không tự áp dụng thời hạn pháp lý chưa xác minh. |
| QT06 | Quản lý, phát hành và ngừng dùng phiên bản mô hình AI | Supervisor (Admin) | Lưu chỉ số đánh giá, ngưỡng vận hành và phiên bản áp dụng trên hệ AI tích hợp; Python/YOLO chỉ là hướng triển khai trước đây; kết quả cũ giữ mô hình nguồn. |
| QT07 | Xuất dữ liệu và nhãn đã được duyệt cho huấn luyện | Supervisor (Admin) | Chỉ xuất tập đã qua PM duyệt; có nguồn gốc, phiên bản và phân quyền. |
| QT08 | Theo dõi tác vụ xử lý, dung lượng và tình trạng máy chủ | Supervisor (Admin) | Giám sát tải/tiến trình/lỗi Backend và hàng đợi AI; tác vụ thất bại có thể thử lại trên dữ liệu còn nguyên. |
| QT09 | Tra cứu nhật ký truy vết và lịch sử thay đổi dữ liệu | Supervisor (Admin) | Nhật ký chỉ đọc; giữ tác giả, thời gian, trước/sau và nguyên nhân; không có chức năng sửa nhật ký. |
| QT10 | Quản lý thông tin thiết bị bay và tài liệu quy trình khảo sát | Supervisor (Admin) | Lưu thiết bị và tài liệu quy trình/checklist/hồ sơ chuyến bay theo đề cương; không điều khiển bay. |
| QT11 | Lập yêu cầu xóa dữ liệu đã hết hạn lưu trữ | PM | Hồ sơ đủ thời hạn được đưa vào danh sách chờ Supervisor duyệt; không xóa ngay khi hết bảo hành. |
| QT12 | Phê duyệt yêu cầu xóa dữ liệu hết hạn | Supervisor | Supervisor xem phạm vi và điều kiện; quyết định xóa phải được lưu lịch sử. |
| QT13 | Kiểm tra hạn lưu trữ và trạng thái giữ hồ sơ | Hành vi con trong chức năng cha | Tối thiểu hết bảo hành cộng 5 năm; chặn xóa khi có tranh chấp/đang giữ hồ sơ. |
| QT14 | Thiết lập / gỡ giữ hồ sơ phục vụ tranh chấp | Supervisor | Có căn cứ và lý do; gỡ giữ không tự động xóa dữ liệu. |

### 10. Phản ánh, hồ sơ sự cố và kết quả công bố

| Mã | Chức năng | Tác nhân trực tiếp | Quy tắc / kết quả |
|---|---|---|---|
| PA01 | Gửi phản ánh và ảnh có vị trí riêng | Reporter | Đăng nhập; mỗi ReportPhoto có tọa độ được xác nhận, nguồn DeviceCapture/Exif/Manual, thời điểm và độ chính xác nếu có. Ảnh cũ không dùng GPS lúc upload; giữ nguồn gốc và lịch sử chỉnh. Tạo IncidentReport gắn IncidentCase New, chưa rõ dự án thì chờ điều phối. |
| PA02 | Bổ sung và theo dõi phản ánh của mình | Reporter | Ownership kiểm tra server-side, kể cả tệp/URL ảnh. Xem lịch sử công bố và ảnh sau sửa đúng phạm vi; không xem chi phí, người gửi khác hoặc toàn bộ hồ sơ dự án. |
| PA03 | Điều phối, tiếp nhận và liên kết phản ánh trùng | Supervisor; PM | Gán PM tạo Assigned; PM bắt đầu xem tạo RECEIVING, xác nhận nhận xử lý tạo ACCEPTED và Open. PM liên kết phản ánh trùng vào hồ sơ chính, giữ người gửi/bằng chứng/lịch sử; không tạo sửa trùng hoặc công bố danh tính người khác. |
| PA04 | Chọn và giao cách kiểm chứng | PM | Chọn drone theo segment/vùng hoặc Crew kiểm tra trực tiếp; tạo VERIFYING khi thực sự giao. Kiểm tra từ IncidentCase chưa có Survey/Defect xác nhận vẫn được phép. Cần số đo vật lý thì áp dụng AI13/TN01–TN06. |
| PA05 | Ghi kết luận có/không có hư hỏng | PM | DEFECT_FOUND cần căn cứ PM chấp nhận; NO_DEFECT bắt buộc lý do do PM nhập. AI không tự kết luận; trùng/ngoài phạm vi có mã riêng DUPLICATE/OUT_OF_SCOPE. Thiếu bằng chứng tiếp tục kiểm chứng. |
| PA06 | Theo dõi vòng đời và kiểm tra lại hồ sơ | PM; Repair Crew; Supervisor | New → Assigned → Open → Fixed → Retest → Verified → Closed; Crew nộp đủ kết quả mới Fixed, PM kiểm tra đạt mới Verified, Supervisor xác nhận mới Closed đối với đã sửa. Retest không đạt về Open, giữ lịch sử; không nhảy qua nghiệm thu. |
| PA07 | Công bố kết quả và ảnh sau sửa | PM | Chỉ công bố REPAIRED khi PM đã kiểm tra đạt phần liên quan, hồ sơ Verified và ảnh sau sửa hợp lệ được PM chọn đúng lỗi/phạm vi. Fixed chưa đủ; Reporter không xem ảnh nội bộ chưa được công bố. |

### 11. Phiên bản segment và phạm vi khảo sát

| Mã | Chức năng | Tác nhân trực tiếp | Quy tắc / kết quả |
|---|---|---|---|
| DA13 | Dựng và xác nhận hình học tuyến | Supervisor; PM | Supervisor nhập đầu–cuối/hồ sơ; PM vẽ/import polyline nháp có chiều lý trình. Tuyến cong không suy từ hai điểm; track drone chỉ tham khảo. Đề xuất Supervisor công bố RoadSectionVersion, PM công bố segment. Đây là quyền thiết kế mới. |
| DA14 | Xem trước, chia/gộp và chỉnh segment | PM | Nhập chiều dài dương, gồm 100 m, 250 m, 500 m, 1.000 m hoặc giá trị hợp lệ khác; chia theo khoảng cách dọc tuyến, cho trộn độ dài, chia tại lý trình/gộp đoạn liên tiếp/kéo ranh giới trên tuyến. Preview chỉ rõ đoạn dư; không hở/chồng. |
| DA15 | Công bố bộ segment và truy vết phiên bản | PM | RoadSegmentSet đã công bố bất biến; thay đổi tạo bộ mới. Nhiệm vụ/video/job/Defect cũ giữ ID cũ; RoadSegmentMapping lưu khoảng giao nhau. Chỉ ánh xạ kết quả có vị trí đủ căn cứ, không tự phân phát lỗi 1 km cho mọi đoạn con 100 m. |
| DA16 | Lập nhiệm vụ khởi tạo RouteCapture | PM; Drone Operator | Thiết kế mở rộng thu tuyến trước segment theo tuyến nháp/hành lang; giữ tệp và track gốc. PM xem/chỉnh, Supervisor xác nhận hình học rồi mới chia segment. Khác baseline tình trạng; không giả định bỏ RoadSectionVersionId là chạy được API hiện có. |
| KS15 | Giao segment và vùng cần quan sát | PM; Drone Operator | SurveyWorkItem gắn bộ/segment, thời hạn và Surface/LeftEdge/RightEdge. Trái/phải theo chiều tăng lý trình, không theo chiều bay; xác định phần đường nếu nhiều phần. Một nhiệm vụ/lượt/video có thể phục vụ nhiều segment/vùng. |
| KS16 | Đối chiếu video và đánh giá độ phủ từng vùng | PM; Drone Operator | SurveyVideoInterval lưu video gốc + segment + band + thời gian/độ tin cậy; nhiều khoảng/lượt được phép. SurveyCoverageRequirement/Result tách độ phủ/quang học khỏi GPS/job. Giữ GPS drone, hành lang bay, footprint/ROI và vị trí lỗi riêng; offset có chủ đích không tự là GPS sai. |

### 12. Hợp đồng phân tích AI bên ngoài

| Mã | Chức năng | Tác nhân trực tiếp | Quy tắc / kết quả |
|---|---|---|---|
| AI15 | Tạo và theo dõi phân tích bất đồng bộ | PM; Supervisor | Tái sử dụng ProcessingBlock/ProcessingJob; lưu job và ProcessingInputManifest bền vững trước trả 202/JobId. Khóa phạm vi gồm SurveyDataVersion + RoadSectionVersion + SegmentSet/Segment + TargetBand + model/preprocessing/config; worker gọi AI ngoài vòng đời request FE. |
| AI16 | Nhận kết quả có truy vết và thử lại an toàn | PM; Supervisor | Giữ tệp/raw payload bất biến; xác thực service, schema, checksum/model/phạm vi, timestamp, bbox và quyền tệp. Cùng key/fingerprint trả cùng job, payload khác bị từ chối; dedup detection theo job + detection ID; retry có backoff/giới hạn, kết quả muộn không ghi đè phiên bản hiện hành. |
| AI17 | Xử lý ngữ cảnh biên và phát hiện trùng | PM | Block có vùng chính/ngữ cảnh overlap có cấu hình; giữ các quan sát gốc, gợi ý nhóm theo lý trình/bên/thời điểm/ảnh, PM quyết định. Lỗi qua biên có một Defect liên kết nhiều segment, không tạo sửa trùng. Succeeded/no detections không chứng minh phủ đủ hoặc NO_DEFECT. |

## 5. Đặc tả các tình huống trọng tâm

### 5.1 Khảo sát gốc sau bàn giao — DA01–DA10, KS01–KS14, AI04, DA10

**Điều kiện:** công trình đã bàn giao ngoài hệ thống; Supervisor có quyền tạo dự án.  
**Kết quả thành công:** dự án có đoạn đường, có đúng một PM, có hồ sơ khảo sát gốc (baseline) đã được PM xác nhận để đối chiếu bảo hành.

1. Supervisor tạo dự án (DA01) và nhập tuyến/đoạn đường, lý trình, loại mặt đường (DA02).
2. Supervisor ghi hồ sơ bàn giao và thời hạn bảo hành (DA04).
3. Supervisor phân công **đúng một PM** cho dự án (DA03). PM đó có thể đang quản lý các dự án khác.
4. PM lập kế hoạch / tạo yêu cầu **khảo sát gốc** (DA06, DA08) và phân công Drone Operator (KS01).
5. Drone Operator nhận nhiệm vụ, thu thập và nộp MP4 (+ SRT nếu cần) (KS02, KS06–KS09).
6. Backend lưu dữ liệu, gọi AI Service ngoài qua adapter hoặc dùng mock có nhãn nguồn; PM xem tiến độ (KS10).
7. Nếu vùng chưa đạt, **PM xác nhận bay bổ sung** (KS11); Drone Operator nộp bổ sung (KS12).
8. PM xác minh phát hiện (AI04…) rồi **chọn và xác nhận hồ sơ khảo sát gốc** (DA10).
9. Các kỳ khảo sát sau so sánh với hồ sơ gốc (AI10, DA11) trong thời gian bảo hành.

**Ngoại lệ:** chưa phân công PM thì không tạo yêu cầu khảo sát gốc; dữ liệu không đạt thì chưa xác nhận DA10; thiếu định vị/định dạng thì không coi bộ dữ liệu đạt. PM hủy/thu hồi yêu cầu (KS14) khi chưa có dữ liệu đã nộp; Drone Operator từ chối kèm lý do (KS03) thì PM phân công lại (KS04), không coi khảo sát gốc đã hoàn tất. Chỉnh sửa tuyến/đoạn sau khi đã có khảo sát (DA02) tạo phiên bản mới, không tự gắn lại dữ liệu cũ.

### 5.2 Nhập dữ liệu khảo sát và xử lý — KS06–KS13

**Điều kiện:** Drone Operator được giao yêu cầu đang còn hiệu lực; thiết bị có đủ bộ nhớ để lưu bản sao. **Kết quả thành công:** bộ dữ liệu hợp lệ được lưu toàn vẹn trên máy chủ, xử lý xong (AI Service hoặc mock) và kết quả chuyển tới PM.

1. Drone Operator mở yêu cầu, chọn một hoặc nhiều video trên thẻ nhớ.
2. Ứng dụng sao chép, kiểm tra bản sao và gắn dữ liệu vào đúng lần khảo sát.
3. Hệ thống đọc định vị từ phụ đề trong video nếu có; nếu không, người dùng bổ sung SRT tương ứng.
4. Ứng dụng lưu hàng đợi; khi có mạng và được mở lại thì tiếp tục tải. Backend xác nhận toàn vẹn bộ dữ liệu.
5. Backend lưu job/manifest bền vững theo dataset + segment + TargetBand + model/config, trả 202 + JobId; worker gọi AI ngoài hoặc mock có nhãn nguồn, kiểm tra hợp đồng và lưu detections theo AI15–AI17.
6. Drone Operator / PM xem tiến độ, vùng dữ liệu chưa đạt và kết quả.

**Ngoại lệ:** thiếu bộ nhớ thì chưa coi nhập thành công; thiếu định vị hoặc sai định dạng thì không coi bộ dữ liệu đạt; lỗi máy chủ thử lại, không tự yêu cầu bay lại. Khi cần bổ sung, **PM xác nhận** vùng/lý do, có thể giao người khác; dữ liệu mới liên kết cùng lần khảo sát và không ghi đè bản gốc. PM không hủy yêu cầu (KS14) sau khi máy chủ đã xác nhận toàn vẹn bộ dữ liệu.

### 5.3 Kiểm tra phát hiện sơ bộ, đo thực tế và xác minh chính thức — AI01–AI14, TN01–TN06

**Điều kiện:** PM có quyền trên dự án; kết quả có liên kết dữ liệu nguồn và phiên bản mô hình. **Kết quả:** phát hiện bị loại có lý do, còn chờ rà soát/đo bổ sung, hoặc được PM xác minh thành `Defect` chính thức bằng bằng chứng drone/thực địa phù hợp; số đo vật lý bắt buộc khi quyết định cần số đo đó.

1. Mở phát hiện trên bản đồ, xem ảnh/video, khung bao, loại và độ tin cậy.
2. Đối chiếu vị trí, số đo ước lượng, chất lượng, lỗi trùng và lịch sử khảo sát (kể cả hồ sơ gốc).
3. PM giữ lại thành `Preliminary Defect` bằng cách tạo `Defect OPEN`; hoặc sửa thuộc tính/vùng nhãn; hoặc đánh dấu đã loại bỏ và ghi lý do. `OPEN` chưa phải xác minh chính thức.
4. AI có thể đề xuất gộp trùng; PM quyết định gộp hoặc giữ riêng (AI08).
5. PM chọn bằng chứng drone hoặc giao Crew kiểm chứng. Khi cần số đo vật lý hoặc còn thiếu căn cứ, dùng AI13/TN01–TN06 để giao đo; Crew nhập số liệu/bằng chứng rồi gửi PM. Kiểm tra trực tiếp từ phản ánh chưa có Survey vẫn được phép.
6. PM đánh giá kết quả: yêu cầu bổ sung nếu chưa đạt; chuyển lỗi sang `REJECTED` có lý do nếu bằng chứng không xác nhận; hoặc chuyển lỗi từ `OPEN` sang `VERIFIED` và liên kết đầy đủ nguồn AI/ảnh, quyết định kiểm chứng và bằng chứng; kèm nhiệm vụ/số đo nếu cần đo. Không có detection không đồng nghĩa không có hư hỏng.
7. Lưu quyết định và phiên bản; nhãn hiệu chỉnh phải được duyệt trước khi xuất huấn luyện. **Research Validation Track** vẫn thực hiện RS01–RS06 độc lập và phải giữ định danh/mục đích nghiên cứu riêng.

**Ngoại lệ:** chưa đủ căn cứ thì giữ trạng thái chờ xác minh. Vết nứt nhỏ vẫn được ghi nhận để kiểm tra; không tự loại chỉ vì nhỏ hoặc mô hình không chắc chắn.

### 5.4 Lập và trình đợt sửa — SC01–SC04

**Điều kiện:** lỗi ở trạng thái `VERIFIED`, bằng chứng đã được PM chấp nhận và nhiệm vụ đo bắt buộc theo nhu cầu (nếu có) đã hoàn tất; PM có quyền; lỗi không đang được giao trùng trong một đợt khác đang thực hiện. **Kết quả:** phiên bản toàn đợt ở trạng thái chờ Supervisor duyệt.

1. Hệ thống chỉ hiển thị cho PM chọn thủ công các lỗi đã đủ bằng chứng và được PM xác minh chính thức cần xử lý cùng đợt.
2. Nhập phương án sửa tổng quát và chi phí dự kiến cho phạm vi lỗi; không nhập vật liệu, định mức hoặc giai đoạn thi công chi tiết.
3. Hệ thống tính tổng dự toán; PM đính kèm bằng chứng và xác nhận danh sách lỗi.
4. Gửi toàn bộ đợt. Hệ thống lưu phiên bản được trình để Supervisor đánh giá.

**Ngoại lệ:** lỗi chưa được PM xác minh hoặc còn thiếu số đo bắt buộc theo nhu cầu thì bị chặn chọn/gửi; thiếu phương án, chi phí hoặc bằng chứng bắt buộc thì giữ bản nháp; không cho giao thi công khi chưa duyệt.

### 5.5 Duyệt và trình lại — SC05–SC10

**Điều kiện:** Supervisor nhận phiên bản đợt đang chờ duyệt. **Kết quả:** đợt được duyệt toàn bộ hoặc được trả để chỉnh sửa.

1. Supervisor đánh giá phạm vi, phương án tổng quát và chi phí từng lỗi/tổng chi phí của đúng phiên bản.
2. Nếu đạt, duyệt phiên bản toàn đợt; PM có thể phân công Repair Crew.
3. Nếu một số lỗi chưa đạt, ghi rõ lỗi và lý do. Đợt chuyển về PM.
4. PM sửa các phần bị trả, tính lại tổng và trình lại toàn đợt ở phiên bản mới.

**Ngoại lệ:** quyết định ở phiên bản cũ không cho phép tự triển khai phiên bản đã đổi. Lưu lịch sử phần từng được chấp thuận để đối chiếu, không xóa quyết định cũ. Repair Crew từ chối đợt chưa nhận (HT15) thì chưa vào thi công; PM phân công lại (SC11), đợt đã duyệt vẫn còn hiệu lực.

### 5.6 Báo cáo hoàn thành và sửa lại — HT04–HT13, HT15

**Điều kiện:** Repair Crew đã tiếp nhận đợt đã duyệt. **Kết quả:** từng lỗi có bằng chứng và quyết định hoàn tất; cả đợt chỉ đóng khi mọi lỗi trong phạm vi đạt.

1. Repair Crew ghi ảnh trước/sau, tiến độ và chi phí thực tế cho từng lỗi.
2. Đồng bộ bằng chứng, gửi báo cáo cho PM.
3. PM kiểm tra từng lỗi. Lỗi chưa đạt được trả lại đúng Repair Crew và ghi lý do.
4. Với kết quả đạt, PM trình Supervisor. Supervisor xác nhận hoặc trả lại các lỗi chưa đạt.
5. Repair Crew chỉ sửa lại lỗi bị trả, bổ sung bằng chứng mới và gửi qua PM lần nữa.
6. Supervisor xác nhận hoàn tất; hệ thống đóng đợt khi đủ điều kiện và giữ lịch sử mọi lượt sửa.

**Ngoại lệ:** thiếu ảnh bắt buộc hoặc còn bằng chứng chưa đồng bộ thì chưa gửi chính thức. Phát hiện lỗi mới chuyển về luồng xác minh; phát sinh lỗi ngoài danh sách hoặc vượt chi phí đã duyệt phải trình điều chỉnh. Từ chối đợt (HT15) chỉ áp dụng trước khi tiếp nhận; đã nhận thì không tự bỏ, PM điều chuyển (SC11).

### 5.7 Xuất hồ sơ — BC06–BC10

**Điều kiện:** người yêu cầu có quyền đọc phạm vi dữ liệu được chọn. **Kết quả:** tệp xuất tái hiện được nội dung và nguồn gốc hồ sơ tại thời điểm xuất.

1. Chọn dự án, đoạn đường hoặc một lỗi và khoảng thời gian.
2. Hệ thống tổng hợp hồ sơ bàn giao, dữ liệu khảo sát, số đo, quyết định và bằng chứng sửa chữa.
3. Kèm phiên bản mô hình, nhật ký, thông tin tệp và dấu kiểm tra toàn vẹn.
4. Người dùng tải về. Phương án đề xuất là PDF tổng hợp cùng ZIP chứa dữ liệu gốc và bảng kê.

**Ngoại lệ:** dữ liệu thiếu phải được ghi rõ, không tạo cảm giác hồ sơ đầy đủ khi thiếu bằng chứng.

### 5.8 Xóa hồ sơ sau thời hạn — QT11–QT14

**Điều kiện:** dữ liệu đủ hạn bảo hành cộng 5 năm; không bị giữ do tranh chấp. **Kết quả:** Supervisor duyệt hoặc từ chối; lịch sử quyết định được bảo toàn.

1. Lập yêu cầu với phạm vi dữ liệu cụ thể và căn cứ hết hạn.
2. Hệ thống kiểm tra hạn lưu trữ, hồ sơ liên quan và trạng thái giữ hồ sơ.
3. Supervisor xem xét và quyết định.
4. Chỉ khi đủ điều kiện và đã duyệt mới thực hiện xóa theo chính sách; lưu biên bản/mục nhật ký về thao tác.

**Ngoại lệ:** còn thời hạn, đang tranh chấp hoặc chưa rõ phạm vi thì chặn xóa. Dọn bản sao trên điện thoại là chức năng riêng, không phải xóa hồ sơ trên máy chủ.

### 5.9 Phản ánh tới kết quả sau sửa — PA01–PA07, SC01–SC12, HT01–HT15

1. Reporter đăng nhập, gửi mô tả và ảnh; mỗi ảnh có vị trí riêng từ GPS lúc chụp/EXIF/nhập tay và được người gửi xác nhận. Không tự sao chép vị trí ảnh đầu; dùng chung vị trí phải được xác nhận rõ. Thiếu GPS yêu cầu đặt ghim; không giả tạo độ chính xác.
2. Hệ thống tạo IncidentReport và IncidentCase New; xác định tuyến/PM khi đủ căn cứ để Assigned. Trường hợp chưa rõ tuyến giữ New để điều phối, không chọn PM tùy tiện. PM bắt đầu xử lý tạo RECEIVING rồi xác nhận ACCEPTED/Open.
3. PM chọn drone hoặc Crew kiểm chứng (PA04); kiểm tra thực địa trực tiếp không yêu cầu Survey giả. PM ghi DEFECT_FOUND hoặc NO_DEFECT có lý do; chưa đủ căn cứ tiếp tục kiểm chứng.
4. Có lỗi: PM trình phương án tổng quát/chi phí; Supervisor duyệt đúng phiên bản, PM mới giao sửa. Trả/từ chối kinh phí giữ Open, không đổi thành NO_DEFECT. Tiến độ công bố AWAITING_REPAIR/REPAIRING dựa trên sự kiện thật.
5. Crew nộp đầy đủ bằng chứng thành Fixed; PM tổ chức Retest và công bố RETESTING. Không đạt quay Open để sửa lại; đạt tất cả hạng mục bắt buộc mới Verified. PM chọn ảnh sau sửa đúng phần phản ánh và công bố REPAIRED; Supervisor xác nhận Closed sau đó.
6. Nhánh không sửa: PM đóng với ClosureReason NoDefect/Duplicate/OutOfScope, lý do và audit. Duplicate liên kết hồ sơ chính để theo dõi; không gọi trùng/ngoài phạm vi là không có lỗi. Sự cố tái phát tạo hồ sơ mới liên kết hồ sơ Closed, không ghi đè lịch sử.

**Ngoại lệ:** chống cập nhật đồng thời/retry ở gửi, tiếp nhận, duyệt và chuyển trạng thái. Hồ sơ nhiều lỗi chỉ Fixed/Verified khi tất cả phần bắt buộc đạt điều kiện; kết quả đã đạt của từng lỗi vẫn được giữ. Reporter chỉ nhận dữ liệu công bố liên quan tới mình.

### 5.10 Phân đoạn, khảo sát hai mép và phân tích — DA13–DA16, KS15–KS16, AI15–AI17

1. Supervisor nhập tuyến; PM dựng polyline nháp và xác định chiều lý trình. Xác nhận hình học khác xác nhận baseline. Nếu cần thu track trước segment thì dùng nhiệm vụ RouteCapture thiết kế riêng.
2. PM xem trước/chỉnh và công bố segment. Tuyến 100 km chia 100 m cho 1.000 segment; tuyến 100,4 km chia 1 km cho 100 đoạn 1 km và đoạn dư 400 m. Biên theo [đầu, cuối), đoạn cuối gồm điểm cuối; chiều dài tính dọc polyline theo mét.
3. PM lên lịch baseline/định kỳ hoặc khảo sát từ phản ánh, chọn bộ segment và vùng cần nhìn. Bay ngược không đổi LeftEdge/RightEdge. Không buộc mỗi segment/vùng có một chuyến bay hoặc video riêng.
4. Operator nộp video/telemetry; Backend giữ bản gốc và ánh xạ khoảng thời gian theo định vị đồng bộ/vùng thực nhìn thấy. Không chia video theo tốc độ cố định, không lấp khoảng mất GPS để giả phủ đủ và không gán GPS drone thành GPS lỗi.
5. Backend tạo manifest/job theo phiên bản và vùng quan sát, worker gọi AI. Block có overlap tại biên; clip dẫn xuất giữ checksum và ánh xạ về video gốc. URL đọc có phạm vi/thời hạn; không gửi PII/chi phí hoặc ảnh Reporter không liên quan cho AI.
6. Backend kiểm tra nhận kết quả; theo dõi phần trăm job riêng với độ phủ Sufficient/Partial/Insufficient/Unknown từng segment/band/dataset. Mép trái đạt nhưng phải thiếu thì giữ trái, bổ sung phải. PM kiểm chứng ứng viên và quyết định gộp, không tự kết luận không lỗi khi danh sách AI rỗng.

**Ngoại lệ:** cùng input retry giữ danh tính; thay dataset/model/config/phạm vi tạo phân tích mới. Bộ segment mới không đổi job đang chạy. Ánh xạ kết quả sang bộ mới chỉ khi đủ vị trí; trường hợp không đủ thì PM đối chiếu hoặc phân tích lại.

## 6. Các trạng thái để triển khai nhất quán

| Đối tượng | Các trạng thái nghiệp vụ chính |
|---|---|
| IncidentCase | New → Assigned → Open → Fixed → Retest → Verified → Closed; Retest không đạt → Open; đóng không sửa cần lý do riêng và người quyết định. |
| IncidentReport (công bố) | SUBMITTED → RECEIVING → ACCEPTED → VERIFYING → DEFECT_FOUND hoặc NO_DEFECT (lý do bắt buộc); nhánh có lỗi tiếp AWAITING_REPAIR/REPAIRING → RETESTING → REPAIRED; DUPLICATE/OUT_OF_SCOPE riêng. |
| Độ phủ theo segment/band/dataset | Sufficient; Partial; Insufficient; Unknown — độc lập trạng thái job AI. |
| Nhiệm vụ khảo sát | Mới giao; đã nhận; từ chối; đã hủy; hoãn; đang thực hiện; đã nộp; yêu cầu bổ sung; hoàn tất. |
| Dữ liệu khảo sát | Đang sao chép; đã lưu cục bộ; chờ tải; đang tải; máy chủ đã xác nhận toàn vẹn; không hợp lệ. |
| Tác vụ phân tích | Chờ xử lý; đang xử lý; thất bại có thể thử lại; cần bổ sung dữ liệu; hoàn tất. |
| Phát hiện AI / Preliminary Defect | Chờ rà soát; cần kiểm tra thêm; chờ kiểm chứng; đang kiểm chứng/đo khi cần; chờ PM đánh giá; đã loại bỏ; đã xác minh chính thức. `Preliminary Defect = Defect OPEN`; PM xác minh bằng chứng phù hợp mới chuyển `Defect VERIFIED`, kèm số đo đã chấp nhận khi cần. |
| Nhiệm vụ đo đạc thực tế | Mới giao; đã nhận; từ chối; đang thực hiện; cần bổ sung; đã gửi; hoàn tất. |
| Đợt sửa | Nháp; chờ duyệt; yêu cầu chỉnh sửa; đã duyệt; đã phân công; từ chối; đang thực hiện; chờ kiểm tra; cần sửa lại; hoàn tất. |
| Kết quả từng lỗi | Chưa sửa; đang sửa; chờ PM kiểm tra; cần sửa lại; chờ Supervisor xác nhận; đã hoàn tất. |

Các trạng thái ở bảng là đề xuất tên chuẩn cho thiết kế dữ liệu. `Defect VERIFIED` là xác nhận hư hỏng trước sửa; `IncidentCase Verified` là nghiệm thu sau sửa. ReportStatusEvent là tiến độ công bố cho chủ phản ánh, không lấy trực tiếp enum nội bộ và không công khai chi phí. Trạng thái đợt tổng hợp từ các lỗi; một lỗi đã đạt không bị kéo về chưa đạt chỉ vì lỗi khác cần sửa lại. Supervisor duyệt cả đợt khi phê duyệt danh sách lỗi/chi phí; khi xác nhận hoàn tất có thể trả riêng lỗi chưa đạt — đợt chỉ `Hoàn tất` khi mọi lỗi trong phạm vi đạt.

## 7. Đối chiếu độ phủ với đề cương

| Nhóm yêu cầu trong đề cương | Mã chức năng / nơi thể hiện |
|---|---|
| Reporter, ảnh có vị trí và kết quả công bố | PA01–PA07; §5.9; US-21–US-23 |
| Segment có phiên bản, RouteCapture, hai mép và coverage | DA13–DA16, KS15–KS16; §5.10; US-24–US-25 |
| AI ngoài bất đồng bộ, manifest, retry và ngữ cảnh biên | AI15–AI17; §5.10; US-26 |
| Danh mục dự án, giá trị giữ lại, thời hạn và nhắc bảo hành | DA01–DA12, BC01–BC05, QT05 |
| Hồ sơ khảo sát gốc lúc bàn giao | DA01–DA04, DA06, DA08, DA10, AI10, BC08; kịch bản §5.1 |
| Phân công bay, siêu dữ liệu, tiếp nhận và kiểm tra chất lượng | KS01–KS14, QT10 |
| Ảnh trực giao, mô hình bề mặt, phân tích hình học | AI02–AI03 (nâng cao); chuỗi xử lý nội bộ / AI Service |
| Phát hiện, phân đoạn, mức độ, ghép lỗi và theo dõi tăng trưởng | AI01–AI12, QT04, QT06; AI08 do PM xác nhận gộp |
| Kiểm chứng và đo khi cần do Repair Crew | AI13, TN01–TN06 — bắt buộc khi cần số đo vật lý/thiếu căn cứ; PM kết luận sau đánh giá |
| Gộp đợt, duyệt ngân sách, phân công và bằng chứng sửa chữa | SC01–SC12, HT01–HT15 |
| Trang web cuối kỳ và ứng dụng hiện trường ngoại tuyến | Ranh giới tổng quan, CN05–CN09, KS06–KS09, HT04–HT07 |
| Báo cáo, hồ sơ bằng chứng, nguồn gốc và lưu trữ | BC01–BC10, QT09, QT11–QT14 |
| Dữ liệu nhãn và phiên bản mô hình | AI05–AI07, AI14, QT06–QT07 |
| Backend C# + AI ngoài qua adapter | §1.1 kiến trúc; KS10, QT06, QT08 |
| Đo đạc thực tế và thử nghiệm thực địa | AI13, TN01–TN06 cho căn cứ nghiệp vụ; RS01–RS06 cho Research Validation. |

## 8. Các điểm cần chốt khi đặc tả kỹ thuật, không cản trở vẽ use case

- **Stack đã hướng:** Backend **C# (ASP.NET Core)**; hệ AI ngoài qua adapter có phiên bản, Python/YOLO là hướng trước đây. Chốt capability async/polling, storage, model/version và idempotency bằng hợp đồng/video mẫu; mock có nhãn nguồn không chứng minh độ chính xác. Framework Web/queue và onboarding Reporter cần đặc tả kỹ thuật riêng.
- Ngưỡng chất lượng ảnh/định vị/chồng lấn; giới hạn dung lượng, thời gian xử lý và số tác vụ song song cần chốt sau khảo sát thử. Không gán các con số thử nghiệm trước đây thành tiêu chuẩn đã nghiệm thu.
- Bộ quy tắc phân mức phải gắn đúng loại mặt đường, từng loại hư hỏng và phiên bản tài liệu chuẩn. Chưa mặc định các ngưỡng chiều rộng nứt áp dụng chung cho toàn hệ thống.
- Phân quyền PM lập yêu cầu xóa, định dạng PDF + ZIP và việc Repair Crew ghi kế hoạch phân việc là lựa chọn thiết kế được đề xuất; có thể tinh giản khi đặc tả màn hình mà không đổi quyền năm vai trò đã nêu.
- **Đo đạc theo nhu cầu (AI13, TN01–TN06):** PM ghi căn cứ chọn drone hoặc thực địa. Khi cần số đo vật lý hoặc còn thiếu bằng chứng, Repair Crew phải đo; PM chấp nhận kết quả trước kết luận cần phép đo đó. Không bỏ nghĩa vụ ground truth nghiên cứu RS01–RS06.
- **Research Validation Track là bắt buộc theo đề cương:** phải lập mẫu các đoạn/điểm khảo sát, kỹ sư đo depression depth và slab faulting bằng straightedge/depth gauge, lưu phương pháp/dụng cụ/người đo/thời điểm/tọa độ, ghép với số đo từ surface model và báo cáo sai số (ít nhất bias, MAE/RMSE và độ không chắc chắn phù hợp thiết kế thí nghiệm).
- Ground truth nghiên cứu có thể được thu thập ngoài app bằng Excel/giấy, nhưng trước khi phân tích phải nhập/chuẩn hóa vào `FieldInspectionSession`, `GroundTruthMeasurement`, `DerivedMeasurement` và `MeasurementValidationSample` theo Data Dictionary. Đo đạc hỗ trợ nghiệp vụ do Repair Crew thực hiện cũng dùng cùng cấu trúc đo, nhưng không tự chuyển trạng thái `Defect` hoặc `Warranty`.
- Ảnh trực giao, mô hình bề mặt, so sánh RGB với RGB + surface model và nghiên cứu liên hệ xói lề–vỡ mép thuộc đề cương nghiên cứu. Sơ đồ chức năng không chứng minh mô hình đã đạt độ chính xác trước khi có báo cáo validation.

## 9. Research Validation Track (bắt buộc theo đề cương, độc lập với MVP sản phẩm)

Các mã `RS01–RS06` dưới đây là yêu cầu thực nghiệm của đề cương, không phải màn hình nghiệp vụ bắt buộc trong MVP. Việc ghi nhận ngoài app bằng Excel/giấy được phép, nhưng dữ liệu cuối cùng phải được chuẩn hóa và truy vết trong bộ dữ liệu nghiên cứu.

| Mã | Hoạt động bắt buộc | Kết quả tối thiểu |
|---|---|---|
| `RS01` | Chọn mẫu đoạn đường/điểm lún và điểm slab faulting đại diện; gắn với `RoadSectionVersion` và survey tương ứng. | Có danh sách mẫu và mã mẫu duy nhất. |
| `RS02` | Kỹ sư kiểm tra tại chỗ, ghi loại lỗi, mức độ, phạm vi; đo depression depth/slab faulting bằng straightedge và depth gauge. | Có `GroundTruthMeasurement` cho từng mẫu đo thực tế. |
| `RS03` | Ghi dụng cụ, phương pháp, người đo, thời điểm, vị trí, đơn vị và bằng chứng ảnh/biên bản. | Có chain of custody và metadata đủ tái hiện phép đo. |
| `RS04` | Ghép từng ground-truth sample với kết quả đo từ DSM/surface model hoặc pipeline tương ứng. | Có cặp `GroundTruthMeasurement`–`DerivedMeasurement`, không ghép theo thứ tự dòng không có ID. |
| `RS05` | Tính sai số và độ không chắc chắn; tối thiểu báo bias, MAE/RMSE và số lượng mẫu, kèm phương pháp tính. | Có `MeasurementValidationRun` và kết quả theo loại phép đo. |
| `RS06` | Đưa dữ liệu paired ground truth vào annotated dataset và báo cáo field trial. | Dataset/báo cáo nêu rõ mẫu, thiếu dữ liệu, outlier và giới hạn suy luận. |

Ràng buộc: RS01–RS06 chỉ là bằng chứng đánh giá độ tin cậy của phép đo và mô hình.

## 10. Nguồn đồng bộ và trạng thái thiết kế

- [Thiết kế phản ánh và segment](RoadGuard_Incident_Segment_Design_v1.md).
- [Thiết kế AI, segment và hai mép](RoadGuard_AI_Segment_Edge_Design_v1.md).
- [User stories và AC](User_Stories_Acceptance_Criteria_v2.md), [Domain model](RoadGuard_Domain_Model_v1.md), [Data Dictionary](RoadGuard_Data_Dictionary_v1.md), [ERD](RoadGuard_ERD_v1.md).

Giữ nguyên mã CN/DA01–DA12/KS01–KS14/AI01–AI14/TN/SC/HT/BC/QT/RS hiện có; mã mới không đổi nghĩa ID lịch sử. Các quyền, entity, trạng thái và hợp đồng mới ở tài liệu này là thiết kế để triển khai sau, không phải bằng chứng endpoint hoặc migration đã tồn tại. Đề cương được nêu tên là căn cứ lịch sử, chưa có bản tệp trong checkout này để tạo liên kết.
