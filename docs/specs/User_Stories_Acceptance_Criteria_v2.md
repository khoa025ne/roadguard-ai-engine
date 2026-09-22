# User Story và Acceptance Criteria - RoadGuard / CÁT TƯỜNG

> Thiết kế mục tiêu đồng bộ 22/09/2026; các phần Reporter, IncidentCase, segment, coverage và AI ngoài là đề xuất chưa triển khai. Phạm vi bàn giao BE — 18/09/2026: đợt hiện tại phát triển backend ASP.NET Core; Android/Web thuộc FE, AI thật và thu thập số đo thực địa là tích hợp bên ngoài ở giai đoạn sau. Backend vẫn triển khai đầy đủ workflow bắt buộc, adapter AI giả lập xác định và chức năng Research Validation nhập/ghép/tính sai số/xuất báo cáo bằng dữ liệu kiểm thử hoặc dữ liệu ngoài đã có. Nghiệm thu phần mềm BE không tuyên bố độ chính xác AI hay kết quả thực nghiệm từ dữ liệu giả. Các yêu cầu sản phẩm/nghiên cứu đầy đủ bên dưới vẫn được giữ để truy vết. Xem [ADR 003](../adr/003-backend-delivery-and-ai-boundary.md).

## 1. Mục đích và phạm vi

Tài liệu này chuyển đặc tả use case trong [Dac_ta_UseCase_v2.md](Dac_ta_UseCase_v2.md) thành các User Story lớn theo nhóm nghiệp vụ. Mỗi story giữ mã chức năng nguồn để truy vết và có Acceptance Criteria theo dạng **Given / When / Then**.

Phạm vi là **MVP hiện tại** của hệ thống RoadGuard, gồm Android App cho Drone Operator/Repair Crew/Reporter, Web Dashboard cho Supervisor/PM, Backend C# + SQL Server/SQL Server Spatial theo [RoadGuard_Data_Dictionary_v1.md](RoadGuard_Data_Dictionary_v1.md), và hệ AI ngoài qua adapter/job bất đồng bộ. Mock chỉ để kiểm thử hợp đồng, luôn gắn nguồn; các phần mới là thiết kế chưa triển khai.

### 1.1 Ngoài phạm vi MVP

- `AI13` và `TN01-TN06`, `TN12` là luồng đo thực địa khi PM cần số đo vật lý hoặc bằng chứng chưa đủ; không phải tiền điều kiện chung cho mọi phát hiện. Ground truth nghiên cứu `RS01–RS06` vẫn bắt buộc và độc lập.
- `AI02` (ảnh trực giao/mô hình bề mặt) và các phép đo phụ thuộc pipeline nâng cao: không phải điều kiện nghiệm thu MVP sản phẩm. Tuy nhiên, **Research Validation Track của đề cương là bắt buộc**: phải thu thập ground truth vật lý cho mẫu depression/slab faulting và đối chiếu với số đo drone để báo cáo measurement uncertainty.
- Điều khiển thiết bị bay; hệ thống chỉ tiếp nhận dữ liệu do thiết bị bay tạo ra.
- Reporter là vai trò thứ năm, subtype `CITIZEN` hoặc `INVESTOR_REPRESENTATIVE`; gửi và xem phản ánh của mình qua ownership, không cần membership dự án hoặc quyền xem chi phí.
- Cam kết độ chính xác địa lý, độ sâu hoặc thời điểm hỏng chỉ từ đầu ra YOLO/bounding box.

### 1.1A Phần nghiên cứu bắt buộc nhưng tách khỏi MVP sản phẩm

Đề cương yêu cầu một track validation độc lập với các User Story sản phẩm. Track này có thể thu thập ngoài app bằng Excel/giấy, nhưng dữ liệu cuối cùng phải được chuẩn hóa và có định danh để tái hiện phân tích.

| Mã | Yêu cầu bắt buộc | Tiêu chí nghiệm thu nghiên cứu |
|---|---|---|
| `RS01` | Chọn mẫu đoạn/điểm đo và liên kết với survey/road section version. | Mỗi mẫu có `sample_id` duy nhất. |
| `RS02` | Kỹ sư đo depression depth và slab faulting bằng straightedge/depth gauge. | Có giá trị, đơn vị, dụng cụ, người đo, thời điểm, tọa độ và bằng chứng. |
| `RS03` | Ghi metadata và chain of custody cho từng phép đo. | Có phương pháp, dụng cụ, người đo, thời điểm, điều kiện hiện trường và bằng chứng. |
| `RS04` | Ghép số đo thực địa với số đo surface model/DSM tương ứng. | Mỗi cặp có `ground_truth_measurement_id` và `derived_measurement_id`; không ghép theo vị trí dòng Excel. |
| `RS05` | Tính độ chính xác và độ không chắc chắn. | Báo bias, MAE/RMSE, số mẫu và phương pháp/giả định tính toán theo loại phép đo. |
| `RS06` | Đưa mẫu paired vào dataset và báo cáo field trial. | Nêu rõ outlier, mẫu thiếu, điều kiện khô/mưa nếu có và giới hạn suy luận. |

`RS01–RS06` là tính năng đo đạc phục vụ nghiên cứu; kết quả chỉ dùng để đánh giá mô hình và phép đo.

### 1.2 Vai trò

| Vai trò | Trách nhiệm trong MVP |
|---|---|
| Supervisor (Admin) | Tạo dự án, nhập tuyến/đoạn đường, phân công PM, duyệt đợt sửa, xác nhận hoàn tất, quản trị tài khoản/cấu hình/nhật ký/dữ liệu. |
| PM | Lập kế hoạch và yêu cầu khảo sát, điều phối Drone Operator, rà soát phát hiện AI sơ bộ, chọn drone hoặc giao đo thực địa khi cần căn cứ vật lý, xác minh hư hỏng từ bằng chứng phù hợp, lập và theo dõi đợt sửa, kiểm tra báo cáo hoàn thành, trình Supervisor. |
| Drone Operator | Nhận nhiệm vụ, nhập video/SRT, kiểm tra chất lượng, tải dữ liệu và thực hiện bay bổ sung khi được phân công. |
| Repair Crew | Đội trưởng nhận đợt sửa hoặc nhiệm vụ đo đạc khi PM giao, tổ chức thành viên không có tài khoản riêng, ghi số đo/bằng chứng khi cần, tiến độ và báo cáo hoàn thành. |
| Reporter | Citizen hoặc InvestorRepresentative; gửi phản ánh, xác nhận vị trí từng ảnh, bổ sung bằng chứng và xem tiến độ/kết quả công bố của chính mình. Không có quyền project membership. |

### 1.3 Quy tắc chung áp dụng cho mọi story

1. Người dùng chỉ được xem và thao tác trong phạm vi dự án được cấp quyền; Supervisor có quyền toàn danh mục.
2. Mọi thay đổi nghiệp vụ quan trọng phải lưu người thực hiện, thời điểm, giá trị trước/sau, lý do và nguồn dữ liệu trong nhật ký chỉ đọc.
3. Hệ thống không xóa cứng hồ sơ nghiệp vụ trong các luồng thông thường; bản ghi bị loại bỏ, hủy hoặc ngừng sử dụng vẫn phải tra cứu được.
4. Một dự án có đúng một PM chính tại mỗi thời điểm. Một PM có thể quản lý nhiều dự án.
5. Bản ghi hoặc phiên bản chưa được phê duyệt không được dùng để giao việc hoặc kết luận hoàn tất.
6. Dữ liệu chưa đồng bộ phải hiển thị rõ trạng thái và không được báo là đã lưu an toàn trên máy chủ.
7. Các tiêu chí chất lượng chưa có số đo chuẩn trong đặc tả phải được cấu hình, không tự gán một ngưỡng thử nghiệm thành tiêu chuẩn nghiệm thu.
8. Tài liệu và Acceptance Criteria dùng tên/quan hệ theo Data Dictionary: `Warranty` là aggregate riêng; baseline nằm trên `Survey`; `SupplementarySurveyRequest` độc lập; `QualityCheck` và `Evidence` phải thỏa ràng buộc đúng một FK đích.
9. Dữ liệu có vị trí phải giữ `road_section_version_id` khi liên quan hình học đoạn; GPS/raw location dùng `geography(4326)`, còn geometry kỹ thuật dùng SRID UTM của dự án. JSON phải hợp lệ và đúng schema ứng dụng, không dùng cú pháp PostgreSQL/PostGIS.

## 2. Danh sách User Story MVP

| ID | Nhóm | User Story | Mã chức năng |
|---|---|---|---|
| US-01 | Truy cập | Đăng nhập, hồ sơ, quyền và thông báo theo vai trò | CN01-CN04, CN10 |
| US-02 | Truy cập | Làm việc ngoại tuyến và đồng bộ an toàn | CN05-CN09 |
| US-03 | Dự án | Quản lý dự án, tuyến/đoạn, bàn giao và nhân sự | DA01-DA05, DA12 |
| US-04 | Dự án | Lập kế hoạch khảo sát và xác nhận baseline | DA06-DA11 |
| US-05 | Khảo sát | Điều phối, tiếp nhận, từ chối và hủy yêu cầu khảo sát | KS01-KS04, KS14 |
| US-06 | Khảo sát | Nhập, kiểm tra và tải dữ liệu bay | KS05-KS10 |
| US-07 | Khảo sát | Bay bổ sung và thử lại xử lý | KS11-KS13 |
| US-08 | AI | Kiểm tra và hiệu chỉnh danh sách phát hiện sơ bộ của AI | AI01, AI04-AI07 |
| US-09 | AI | Gộp, đối sánh theo kỳ và theo dõi diễn biến lỗi | AI08-AI12 |
| US-10 | AI | Duyệt nhãn hư hỏng cho dữ liệu huấn luyện | AI14 |
| US-11 | Sửa chữa | Lập, trình, duyệt và trình lại đợt sửa | SC01-SC09, SC12 |
| US-12 | Sửa chữa | Phân công và bàn giao Repair Crew | SC10-SC11 |
| US-13 | Thi công | Tiếp nhận đợt sửa, ghi tiến độ và bằng chứng | HT01-HT08, HT14-HT15 |
| US-14 | Thi công | Kiểm tra, sửa lại và xác nhận hoàn tất | HT09-HT13 |
| US-20 | Đo đạc thực tế | Đo đạc bắt buộc và xác minh hư hỏng chính thức | AI13, TN01-TN06, TN12 |
| US-15 | Báo cáo | Dashboard quản lý dự án, chi phí và rủi ro | BC01-BC05 |
| US-16 | Báo cáo | Xuất hồ sơ, nguồn gốc và tra cứu lưu trữ | BC06-BC10 |
| US-17 | Quản trị | Quản lý tài khoản, quyền, danh mục và nhắc việc | QT01-QT05 |
| US-18 | Quản trị | Quản trị mô hình AI, tác vụ và thiết bị | QT06-QT10 |
| US-19 | Quản trị | Lưu trữ, giữ hồ sơ và xóa dữ liệu có phê duyệt | QT11-QT14 |

---

## 3. User Stories và Acceptance Criteria

### US-01 - Đăng nhập, hồ sơ, quyền và thông báo theo vai trò

**User Story**  
Là một người dùng nội bộ (Supervisor, PM, Drone Operator hoặc Repair Crew), tôi muốn đăng nhập bằng tài khoản được cấp, xem/cập nhật hồ sơ cá nhân, xem đúng dự án được phân công và nhận thông báo phù hợp để làm việc đúng quyền.

**Tiền điều kiện**

- Tài khoản đã được Admin tạo và đang hoạt động.
- Người dùng có thông tin xác thực hợp lệ.

**Acceptance Criteria**

1. **Đăng nhập và phiên làm việc**
   - **Given** tài khoản đang hoạt động và mật khẩu đúng
   - **When** người dùng đăng nhập
   - **Then** hệ thống tạo phiên, nhận diện đúng vai trò hiện tại từ server và chỉ tải các dự án/công việc thuộc membership active, còn hiệu lực và đúng vai trò.
   - Nếu tài khoản không tồn tại, bị ngừng sử dụng, mật khẩu sai hoặc phiên hết hạn, hệ thống từিসে chối truy cập và không tiết lộ thông tin nhạy cảm.
2. **Đăng xuất và hết hạn phiên**
   - **When** người dùng đăng xuất hoặc phiên hết hạn
   - **Then** token/phiên hiện tại không thể gọi dữ liệu nghiệp vụ; người dùng phải đăng nhập lại.
3. **Hồ sơ cá nhân**
   - **Given** người dùng đã đăng nhập
   - **When** người dùng sửa thông tin được phép
   - **Then** hệ thống lưu thay đổi và nhật ký; người dùng không thể tự đổi vai trò, quyền dự án hoặc tài khoản người khác.
4. **Phạm vi dữ liệu**
   - **Given** PM, Drone Operator hoặc Repair Crew truy cập danh sách
   - **Then** chỉ các dự án, nhiệm vụ, lỗi và hồ sơ được phân công được hiển thị.
   - **Given** Supervisor truy cập danh sách
   - **Then** có thể xem toàn bộ dữ liệu thuộc danh mục được cấp quyền Admin.
5. **Thông báo và nhắc việc**
   - **When** có sự kiện khảo sát, kết quả xử lý, yêu cầu duyệt, trả sửa, từ chối/hủy nhiệm vụ, phân công lại hoặc sắp hết hạn bảo hành
   - **Then** hệ thống tạo thông báo cho đúng vai trò, có liên kết tới đối tượng và trạng thái đã đọc/chưa đọc.
6. **Đặt lại mật khẩu**
   - **Given** người dùng gửi yêu cầu khôi phục
   - **When** Supervisor (Admin) thực hiện đặt lại
   - **Then** mật khẩu cũ không bị hiển thị, tài khoản buộc đổi mật khẩu ở lần đăng nhập kế tiếp và nhật ký chỉ lưu người/thời điểm, không lưu mật khẩu.
   - Tài khoản đã ngừng sử dụng không được đặt lại mật khẩu.

**Ngoại lệ và kiểm tra**

- Không trả về dữ liệu dự án trước khi kiểm tra quyền.
- Không cho phép dùng phiên cũ sau khi mật khẩu bị Admin đặt lại.

**Mã truy vết:** `CN01-CN04`, `CN10`, `QT02`, `QT09`.

### US-02 - Làm việc ngoại tuyến và đồng bộ an toàn

**User Story**  
Là Drone Operator hoặc Repair Crew, tôi muốn chuẩn bị dữ liệu, ghi nháp và bằng chứng khi mất mạng rồi tiếp tục đồng bộ khi có mạng để không mất dữ liệu hiện trường.

**Acceptance Criteria**

1. **Chuẩn bị ngoại tuyến**
   - **Given** người dùng có quyền với một nhiệm vụ
   - **When** chọn lưu công việc/bản đồ ngoại tuyến
   - **Then** ứng dụng lưu đúng phạm vi được phép và hiển thị thời điểm/phạm vi dữ liệu đã tải.
2. **Lưu nháp và bằng chứng**
   - **Given** thiết bị không có mạng
   - **When** người dùng ghi biểu mẫu, ảnh, video, số đo hoặc ghi chú
   - **Then** dữ liệu được lưu trong bộ nhớ ứng dụng với trạng thái `Chưa đồng bộ`, không báo thành công trên máy chủ.
3. **Hàng đợi đồng bộ**
   - **When** thiết bị có mạng và ứng dụng được mở lại
   - **Then** hệ thống tiếp tục tải theo hàng đợi, hỗ trợ Wi-Fi và dữ liệu di động, hiển thị tiến độ và lỗi từng mục.
4. **Xác nhận toàn vẹn**
   - **Given** máy chủ chưa xác nhận đủ tệp hoặc kiểm tra checksum thất bại
   - **Then** mục dữ liệu vẫn ở trạng thái chưa an toàn và không được chuyển sang `Đã đồng bộ`.
   - Chỉ sau khi máy chủ xác nhận đủ dữ liệu và toàn vẹn thì mới hiển thị `Đã đồng bộ an toàn`.
5. **Thử lại và giữ dữ liệu**
   - **When** đồng bộ lỗi tạm thời
   - **Then** hệ thống giữ bản cục bộ, ghi lỗi và cho phép tiếp tục/thử lại; không tạo bản ghi trùng ngoài ý muốn.
6. **Dọn bản sao cục bộ**
   - **Given** dữ liệu đã đồng bộ an toàn
   - **When** người dùng chủ động chọn dọn bản sao
   - **Then** chỉ bản đã xác nhận mới bị dọn; bản chưa đồng bộ không bị xóa và dữ liệu máy chủ vẫn giữ nguyên.

**Mã truy vết:** `CN05-CN09`, các quy tắc ngoại tuyến tại mục 3 của đặc tả.

### US-03 - Quản lý dự án, tuyến/đoạn, bàn giao và nhân sự

**User Story**  
Là Supervisor, tôi muốn tạo dự án từ hồ sơ bàn giao, quản lý tuyến/đoạn đường và phân công nhân sự để mọi dữ liệu khảo sát và sửa chữa có đúng phạm vi bảo hành.

**Acceptance Criteria**

1. **Tạo dự án**
   - **Given** Supervisor có quyền tạo dự án
   - **When** nhập thông tin công trình và lưu
   - **Then** hệ thống tạo dự án với mã duy nhất, trạng thái hoạt động và thông tin người tạo/thời điểm.
2. **Tuyến và đoạn đường**
   - **When** Supervisor nhập hình học, lý trình, loại mặt đường và phạm vi công trình
   - **Then** hệ thống lưu dữ liệu không gian riêng với các khối xử lý video, cho phép tra cứu theo đoạn.
3. **Phiên bản hình học**
   - **Given** đoạn đã có khảo sát, lỗi hoặc đợt sửa
   - **When** Supervisor sửa hình học/lý trình
   - **Then** hệ thống tạo phiên bản mới, giữ bản cũ, lý do, người và thời điểm; dữ liệu cũ không tự gắn sang hình học mới.
4. **Hồ sơ bàn giao và bảo hành**
   - **When** nhập ngày nghiệm thu/bàn giao, thời hạn, ngày hết hạn, giá trị giữ lại và tài liệu
   - **Then** hệ thống kiểm tra dữ liệu bắt buộc, tính/hiển thị ngày hết hạn và liên kết tài liệu với dự án.
5. **Phân công PM**
   - **Given** dự án được tạo hoặc cập nhật
   - **When** Supervisor phân công nhân sự
   - **Then** dự án có đúng một PM chính; có thể có nhiều Drone Operator/Repair Crew theo nhu cầu; một PM có thể thuộc nhiều dự án.
6. **Kiểm soát phạm vi**
   - **Then** nhân sự được phân công chỉ xem dự án tương ứng; thay đổi phân công có nhật ký và thông báo.
7. **Đóng dự án**
   - **When** Supervisor ngừng sử dụng dự án
   - **Then** hệ thống chặn tác nghiệp thông thường nhưng giữ toàn bộ lịch sử và cho phép tra cứu theo chính sách lưu trữ.

**Mã truy vết:** `DA01-DA05`, `DA12`, `QT09`.

### US-04 - Lập kế hoạch khảo sát và xác nhận baseline

**User Story**  
Là PM, tôi muốn lập lịch khảo sát gồm khảo sát gốc sau bàn giao, tạo yêu cầu khảo sát và xác nhận phiên bản baseline để so sánh tình trạng công trình trong thời gian bảo hành.

**Acceptance Criteria**

1. **Kế hoạch khảo sát**
   - **Given** dự án đã có đúng một PM
   - **When** PM lập kế hoạch
   - **Then** kế hoạch có loại khảo sát (gốc/định kỳ/phát sinh), phạm vi, thời hạn, yêu cầu đầu ra và lịch sử thay đổi.
2. **Nhắc việc**
   - **When** đến mốc nhắc theo cấu hình hoặc gần hết hạn bảo hành
   - **Then** PM nhận thông báo; thông báo không tự tạo lệnh bay.
3. **Hoãn kế hoạch**
   - **When** PM ghi nhận hoãn/không triển khai
   - **Then** lý do là bắt buộc, có thể chọn lịch mới và lưu quyết định; hành động này không đồng nghĩa hủy một yêu cầu bay đã tạo.
4. **Tạo yêu cầu khảo sát**
   - **Given** dự án và phạm vi hợp lệ
   - **When** PM tạo yêu cầu
   - **Then** hệ thống lưu loại yêu cầu, thời hạn, phạm vi và yêu cầu đầu ra, sẵn sàng để phân công Drone Operator.
5. **Baseline**
   - **Given** dữ liệu khảo sát gốc đã xử lý và các phát hiện được giữ lại đã hoàn tất đo đạc thực tế, được PM chấp nhận kết quả và xác minh chính thức
   - **When** PM chọn và xác nhận phiên bản gốc
   - **Then** hệ thống đánh dấu phiên bản đó là baseline của dự án và dùng làm mốc so sánh cho các kỳ sau.
6. **Chặn xác nhận thiếu dữ liệu**
   - **Given** dữ liệu chưa toàn vẹn, thiếu định vị, chưa xử lý hoặc còn vùng không đạt
   - **Then** hệ thống không cho xác nhận baseline và chỉ rõ nguyên nhân cần bổ sung.
7. **Theo dõi tình trạng**
   - **When** Supervisor hoặc PM mở dự án
   - **Then** có thể xem lỗi còn mở, mức độ, thay đổi so với baseline và kỳ khảo sát tương ứng.

**Mã truy vết:** `DA06-DA11`, kịch bản khảo sát gốc §5.1.

### US-05 - Điều phối, tiếp nhận, từ chối và hủy yêu cầu khảo sát

**User Story**  
Là PM, tôi muốn giao đích danh Drone Operator và điều chỉnh phân công; là Drone Operator, tôi muốn tiếp nhận hoặc từ chối nhiệm vụ chưa bắt đầu với lý do rõ ràng.

**Acceptance Criteria**

1. **Phân công**
   - **Given** yêu cầu khảo sát còn hiệu lực
   - **When** PM chọn một Drone Operator và lịch thực hiện
   - **Then** hệ thống chuyển yêu cầu sang `Mới giao`, gửi thông báo và lưu người giao/thời điểm.
2. **Tiếp nhận**
   - **When** Drone Operator xác nhận
   - **Then** yêu cầu chuyển `Đã nhận`, hiển thị phạm vi, thời hạn, hướng dẫn và cho phép nhập dữ liệu.
3. **Từ chối**
   - **Given** trạng thái là `Mới giao`
   - **When** Drone Operator từ chối
   - **Then** phải nhập lý do, yêu cầu trả về PM để phân công lại và không được coi là hoàn tất.
   - Nếu đã tiếp nhận, Drone Operator không được tự từ chối; PM phải điều chỉnh phân công.
4. **Phân công lại**
   - **When** PM đổi người hoặc lịch
   - **Then** hệ thống lưu người cũ, người mới, lý do, lịch mới và thông báo các bên liên quan.
5. **Hủy/thu hồi**
   - **Given** chưa có bộ dữ liệu máy chủ xác nhận toàn vẹn
   - **When** PM hủy yêu cầu và nhập lý do
   - **Then** yêu cầu chuyển `Đã hủy`, thông báo Drone Operator nếu đã giao/đã nhận và giữ lịch sử.
   - **Given** đã có dữ liệu nộp thành công
   - **Then** hệ thống chặn hủy; PM chỉ được điều chỉnh phân công hoặc yêu cầu bay bổ sung.
6. **Phân biệt hoãn và hủy**
   - Hoãn kế hoạch không tạo lệnh bay; hủy yêu cầu là trạng thái của lệnh đã tạo; đổi người/lịch không làm mất yêu cầu.

**Mã truy vết:** `KS01-KS04`, `KS14`.

### US-06 - Nhập, kiểm tra và tải dữ liệu bay

**User Story**  
Là Drone Operator, tôi muốn sao chép video vào thiết bị, bổ sung SRT khi cần, kiểm tra chất lượng và tải nhiều tệp theo hàng đợi để Backend có bộ dữ liệu khảo sát toàn vẹn cho xử lý AI.

**Acceptance Criteria**

1. **Ghi nhận chuyến bay**
   - **When** Drone Operator nhập thiết bị, thời gian, phạm vi đã bay, ghi chú và tài liệu
   - **Then** thông tin được liên kết với đúng yêu cầu khảo sát.
2. **Sao chép từ thẻ nhớ**
   - **When** chọn video
   - **Then** ứng dụng sao chép nội dung thật vào bộ nhớ thiết bị, kiểm tra bản sao và không chỉ lưu đường dẫn thẻ nhớ.
   - Thiếu bộ nhớ phải được báo rõ và không đánh dấu nhập thành công.
3. **Phụ đề định vị**
   - **Given** MP4 không có luồng phụ đề định vị trích xuất được
   - **When** Drone Operator bổ sung SRT
   - **Then** hệ thống kiểm tra ghép đúng video và khoảng thời gian; SRT không được coi mặc định là nhật ký bay đầy đủ.
4. **Kiểm tra chất lượng**
   - **When** chạy kiểm tra
   - **Then** hệ thống kiểm tra định dạng, định vị, đồng bộ thời gian, độ rõ, ánh sáng, vùng phủ và chồng lấn; vùng không đạt có lý do cụ thể.
5. **Nộp nhiều video**
   - **Given** các tệp thuộc cùng lần khảo sát
   - **When** Drone Operator nộp
   - **Then** hệ thống gom đúng lần khảo sát, lưu trạng thái từng tệp và xếp hàng tải khi ngoại tuyến.
6. **Xác nhận máy chủ và xử lý**
   - **When** máy chủ nhận đủ và kiểm tra toàn vẹn thành công
   - **Then** dữ liệu chuyển sang xử lý; Backend lưu manifest/job bền vững theo dataset + segment + TargetBand + model/config, trả 202 + JobId; worker gọi AI ngoài hoặc mock có nhãn nguồn, retry/dedup theo fingerprint.
7. **Theo dõi**
   - Drone Operator và PM xem được trạng thái `Tiếp nhận`, `Đang xử lý`, `Hoàn tất`, `Lỗi` hoặc `Cần bổ sung`, cùng thông báo lỗi có thể hành động.

**Mã truy vết:** `KS05-KS10`, `CN05-CN09`.

### US-07 - Bay bổ sung và thử lại xử lý

**User Story**  
Là PM, tôi muốn xác nhận vùng dữ liệu chưa đạt và yêu cầu bay bổ sung hoặc thử lại tác vụ để hoàn thiện khảo sát mà không ghi đè dữ liệu gốc.

**Acceptance Criteria**

1. **Xác nhận nhu cầu bổ sung**
   - **Given** kết quả chất lượng chỉ ra vùng thiếu/không đạt hoặc tác vụ cần thêm dữ liệu
   - **When** PM chỉ rõ vùng, lý do và người thực hiện
   - **Then** hệ thống tạo yêu cầu bổ sung, liên kết cùng lần khảo sát và lưu người xác nhận/thời điểm.
2. **Không giới hạn lượt**
   - PM có thể tạo nhiều lượt bổ sung; mỗi lượt có phạm vi, lý do, người và nguồn gốc riêng.
3. **Nộp bổ sung**
   - **When** Drone Operator nộp dữ liệu
   - **Then** hệ thống giữ dữ liệu cũ, kiểm tra vùng phủ/đối sánh và ghi rõ tệp thuộc lượt bổ sung nào.
4. **Thử lại tác vụ**
   - **Given** lỗi máy chủ trên dữ liệu đã lưu nguyên vẹn
   - **When** PM hoặc Supervisor chọn thử lại
   - **Then** hệ thống tạo lần xử lý mới trên cùng dữ liệu, giữ lịch sử lỗi/lần thử và không yêu cầu bay lại tự động.
5. **Lỗi dữ liệu**
   - **Given** lỗi do định dạng, thiếu định vị hoặc chất lượng không đạt
   - **Then** hệ thống không cho coi thử lại máy chủ là giải pháp; PM phải quyết định bay bổ sung hoặc xử lý theo ngoại lệ.

**Mã truy vết:** `KS11-KS13`.

### US-08 - Kiểm tra và hiệu chỉnh danh sách phát hiện sơ bộ của AI

**User Story**  
Là PM, tôi muốn xem và rà soát phát hiện AI trên bản đồ cùng nguồn ảnh/video, giữ lại, sửa hoặc loại bỏ có lý do để hình thành danh sách `Preliminary Defect` phải đo thực tế và vẫn truy vết được kết quả AI ban đầu.

**Acceptance Criteria**

1. **Hiển thị phát hiện**
   - **When** PM mở một phát hiện
   - **Then** hệ thống hiển thị loại lỗi, độ tin cậy, bounding box, khung hình/thời gian, GPS khi có, dữ liệu nguồn và phiên bản mô hình.
    - Hệ thống phân biệt rõ kích thước ước lượng 2D, số đo từ sản phẩm nâng cao và số đo thực địa; không tự gán độ sâu/độ chính xác địa lý. Nếu dùng dữ liệu cho nghiên cứu, số đo thực địa phải liên kết tới mẫu ground truth và số đo derived tương ứng.
2. **Giữ lại phát hiện sơ bộ**
   - **When** PM đánh dấu phát hiện cần xử lý
   - **Then** hệ thống tạo `Defect` ở trạng thái `OPEN` để biểu diễn `Preliminary Defect`, lưu người và thời gian, rồi chuyển sang chờ giao đo đạc thực tế; chưa phải `Defect VERIFIED` và chưa sẵn sàng cho đợt sửa chữa.
3. **Hiệu chỉnh**
   - **When** PM sửa loại, mức độ, vị trí hoặc vùng nhãn
   - **Then** hệ thống lưu giá trị trước/sau, nguồn AI, phiên bản sau chỉnh và lý do nếu cấu hình yêu cầu.
4. **Loại bỏ**
   - **When** PM đánh dấu phát hiện sai
   - **Then** phải nhập lý do; bản ghi chuyển `Đã loại bỏ` nhưng ảnh gốc, dữ liệu AI và lịch sử vẫn tra cứu được.
5. **Chưa đủ căn cứ**
   - **Given** PM chưa thể kết luận
   - **Then** phát hiện giữ `Chờ rà soát` hoặc `Cần kiểm tra thêm`, không tự bị loại chỉ vì nhỏ hoặc độ tin cậy thấp.
6. **Audit**
   - Mọi quyết định rà soát sơ bộ có người, thời gian, trước/sau, phiên bản mô hình và liên kết nguồn dữ liệu trong nhật ký chỉ đọc.
7. **Không bỏ qua đo đạc**
   - **Given** phát hiện đã được PM giữ lại
   - **Then** hệ thống buộc PM tạo và phân công nhiệm vụ đo đạc cho Repair Crew, đồng thời chặn chuyển lỗi sang `VERIFIED` hoặc chọn vào đợt sửa cho đến khi PM chấp nhận kết quả đo.

**Mã truy vết:** `AI01`, `AI04-AI07`, `QT09`.

### US-09 - Gộp, đối sánh theo kỳ và theo dõi diễn biến lỗi

**User Story**  
Là PM hoặc Supervisor, tôi muốn đối chiếu các phát hiện trùng và cùng một hư hỏng qua nhiều kỳ để tránh đếm trùng, theo dõi lỗi mới/ổn định/phát triển và ưu tiên xử lý dựa trên bằng chứng.

**Acceptance Criteria**

1. **Gợi ý trùng**
   - **When** hệ thống phát hiện các kết quả có khả năng cùng một lỗi
   - **Then** hệ thống chỉ đề xuất gộp, không tự gộp.
2. **Quyết định gộp/giữ riêng**
   - **When** PM xác nhận gộp hoặc giữ riêng
   - **Then** hệ thống cập nhật định danh lỗi, giữ liên kết các phát hiện nguồn và lưu quyết định/audit.
3. **Đối sánh qua khảo sát**
   - **Given** có baseline và các kỳ tương thích
   - **Then** PM có thể xác nhận hoặc sửa liên kết cùng hư hỏng; dữ liệu không đủ tương thích phải báo rõ.
4. **Phân loại diễn biến**
   - Hệ thống hiển thị lỗi mới, ổn định hoặc đang phát triển theo dữ liệu đã có; nếu thiếu kỳ/thiếu chất lượng thì hiển thị cảnh báo thiếu căn cứ.
5. **Cảnh báo ưu tiên**
   - **When** lỗi có mức độ cao, thay đổi nhanh hoặc thuộc nhóm cần theo dõi
   - **Then** PM/Supervisor nhận cảnh báo kèm căn cứ và độ tin cậy; cảnh báo không cam kết dự báo thời điểm hỏng.

**Mã truy vết:** `AI08-AI12`, `DA10-DA11`.

### US-10 - Duyệt nhãn hư hỏng cho dữ liệu huấn luyện

**User Story**  
Là PM, tôi muốn duyệt loại và vùng nhãn đã hiệu chỉnh trước khi xuất dữ liệu huấn luyện để chỉ dữ liệu có nguồn gốc và chất lượng được kiểm soát mới được sử dụng.

**Acceptance Criteria**

1. Chỉ phát hiện đã được PM xác nhận hoặc hiệu chỉnh mới xuất hiện trong danh sách chờ duyệt nhãn.
2. **When** PM duyệt nhãn
   **Then** hệ thống lưu người, thời gian, phiên bản nhãn, nguồn AI và ảnh/video gốc.
3. Nhãn bị từ chối phải có lý do và không được đưa vào tập huấn luyện được duyệt.
4. Supervisor (Admin) chỉ xuất tập đã duyệt, kèm phiên bản và quyền truy cập.

**Mã truy vết:** `AI05-AI07`, `AI14`, `QT06-QT07`.

### US-11 - Lập, trình, duyệt và trình lại đợt sửa

**User Story**  
Là PM, tôi muốn chỉ chọn các lỗi đã đo đạc đạt và xác minh chính thức, nhập chi phí sửa chữa dự kiến cho từng lỗi rồi trình toàn bộ đợt cho Supervisor; là Supervisor, tôi muốn duyệt hoặc trả lại từng lỗi với lý do để kiểm soát phạm vi và ngân sách.

**Acceptance Criteria**

1. **Chọn lỗi**
   - **Given** lỗi đã hoàn tất đo đạc thực tế, kết quả/bằng chứng đã được PM chấp nhận, đã xác minh chính thức và chưa thuộc đợt đang thực hiện khác
   - **When** PM chọn nhiều lỗi
   - **Then** hệ thống tạo bản nháp đợt và chặn lỗi bị giao trùng.
2. **Chi phí sửa chữa dự kiến**
   - PM nhập phương án sửa tổng quát và chi phí dự kiến cho phạm vi lỗi; không lập vật liệu, định mức hoặc giai đoạn thi công chi tiết. Hệ thống tự tính tổng và tính lại khi phạm vi/phương án/chi phí thay đổi.
3. **Trình duyệt**
   - **Given** các trường bắt buộc, bằng chứng và phạm vi đã đủ
   - **When** PM trình
   - **Then** hệ thống khóa phiên bản trình, chuyển `Chờ duyệt` và lưu toàn bộ danh sách lỗi/chi phí tại thời điểm trình.
4. **Duyệt cả đợt**
   - **When** Supervisor duyệt
   - **Then** phiên bản hiện tại chuyển `Đã duyệt`; chỉ phiên bản này mới đủ điều kiện phân công Repair Crew.
5. **Trả chỉnh sửa**
   - **When** Supervisor không chấp thuận một hoặc nhiều lỗi
   - **Then** phải chỉ rõ lỗi và lý do; đợt chuyển `Yêu cầu chỉnh sửa` về PM, không tự triển khai phần đã được chấp thuận.
6. **Trình lại**
   - **When** PM sửa và trình lại
   - **Then** hệ thống tạo phiên bản mới, tính lại tổng, giữ quyết định cũ và yêu cầu duyệt lại toàn bộ đợt.
7. **Theo dõi lịch sử**
   - PM/Supervisor xem được các phiên bản, người duyệt, thời gian, phản hồi và trạng thái từng lỗi.

**Mã truy vết:** `SC01-SC09`, `SC12`.

### US-12 - Phân công và bàn giao Repair Crew

**User Story**  
Là PM, tôi muốn giao đích danh một đội trưởng cho đợt đã duyệt và bàn giao khi cần để việc thi công luôn gắn với đúng danh sách lỗi và chi phí được phê duyệt.

**Acceptance Criteria**

1. Chỉ đợt ở phiên bản hiện tại `Đã duyệt` mới cho phép phân công.
2. **When** PM chọn đội trưởng và lịch
   **Then** hệ thống chuyển đợt sang `Đã phân công`, gửi thông báo và lưu người giao/thời điểm.
3. Một đội trưởng có thể nhận nhiều đợt; Repair Crew không tự nhận đợt của đội khác.
4. **When** PM đổi đội trưởng
   **Then** phải lưu người cũ, người mới, lý do và lịch sử bàn giao; bằng chứng đã gửi vẫn gắn đúng lỗi/đợt.
5. Thay đổi người được phân công không làm thay đổi chi phí đã duyệt; nếu cần sửa danh sách lỗi hoặc chi phí thì phải tạo phiên bản trình duyệt mới.

**Mã truy vết:** `SC10-SC11`, quy tắc phân công tại mục 3.

### US-13 - Tiếp nhận đợt sửa, ghi tiến độ và bằng chứng

**User Story**  
Là đội trưởng Repair Crew, tôi muốn xem đợt đã duyệt, tổ chức thành viên, ghi ảnh trước/sau, tiến độ và chi phí thực tế kể cả khi ngoại tuyến để gửi báo cáo có đủ bằng chứng cho PM.

**Acceptance Criteria**

1. **Tiếp nhận**
   - **Given** đợt đã được phân công và chưa tiếp nhận
   - **When** đội trưởng xác nhận
   - **Then** được xem danh sách lỗi, lịch, chi phí đã duyệt và yêu cầu bằng chứng; đợt chuyển sang trạng thái đang thực hiện.
2. **Từ chối trước khi nhận**
   - **When** đội trưởng từ chối trước khi tiếp nhận
   - **Then** lý do là bắt buộc, đợt trả về PM để phân công lại; không hủy đợt và không đổi phạm vi/chi phí.
   - Sau khi đã nhận, đang thi công hoặc đã có bằng chứng thì không được tự từ chối.
3. **Hướng dẫn hiện trường**
   - Ứng dụng hiển thị vị trí, tọa độ, bản đồ, ảnh tham chiếu và độ chính xác/ước lượng khi có.
4. **Phân việc nội bộ**
   - Đội trưởng ghi kế hoạch và phân việc cho thành viên; thành viên không cần tài khoản riêng và không được tạo quyền hệ thống mới.
5. **Bằng chứng theo lỗi**
   - Ảnh trước/sau, thời gian, vị trí, ghi chú và chi phí thực tế được gắn riêng từng lỗi; bản gốc không bị ghi đè.
6. **Lỗi phát sinh**
   - **When** phát hiện lỗi mới ngoài phạm vi
   - **Then** Repair Crew tạo báo cáo phát sinh cho PM; hệ thống không tự thêm vào đợt đã duyệt.
7. **Gửi báo cáo**
   - **Given** mọi bằng chứng bắt buộc đã đồng bộ
   - **When** đội trưởng gửi
   - **Then** báo cáo chuyển tới PM theo từng lỗi và khóa phiên bản gửi.
   - Thiếu ảnh bắt buộc hoặc còn tệp chưa đồng bộ phải chặn gửi chính thức và chỉ rõ mục thiếu.
8. **Lịch sử**
   - Repair Crew, PM và Supervisor xem được lịch sử tiến độ, bằng chứng và chi phí trong phạm vi quyền.

**Mã truy vết:** `HT01-HT08`, `HT14`, `HT15`, `CN05-CN09`.

### US-14 - Kiểm tra, sửa lại và xác nhận hoàn tất

**User Story**  
Là PM, tôi muốn kiểm tra kết quả theo từng lỗi và trình Supervisor; là Supervisor, tôi muốn xác nhận hoặc trả lại lỗi chưa đạt để đợt chỉ đóng khi mọi lỗi trong phạm vi đều hoàn tất.

**Acceptance Criteria**

1. **PM kiểm tra**
   - **When** PM mở báo cáo
   - **Then** đối chiếu chi phí dự kiến đã duyệt, bằng chứng trước/sau và chi phí thực tế cho từng lỗi, ghi `Đạt` hoặc `Chưa đạt` kèm nhận xét.
2. **Trả sửa lại**
   - **When** PM hoặc Supervisor đánh dấu chưa đạt
   - **Then** chỉ rõ lỗi và lý do, trả đúng Repair Crew đang phụ trách; lỗi đạt không bị kéo ngược trạng thái chỉ vì lỗi khác chưa đạt.
3. **Trình Supervisor**
   - **Given** PM đã kiểm tra các lỗi đủ điều kiện
   - **When** PM trình
   - **Then** hệ thống lưu kết quả từng lỗi, chi phí thực tế và phiên bản báo cáo để Supervisor xem.
4. **Xác nhận cuối**
   - **When** Supervisor xác nhận một lỗi đạt
   - **Then** lỗi chuyển `Đã hoàn tất`; khi còn lỗi chưa đạt, đợt vẫn không đóng.
5. **Sửa lại**
   - **When** Repair Crew sửa lỗi bị trả
   - **Then** chỉ bổ sung bằng chứng/phiên bản mới cho lỗi đó, giữ bằng chứng cũ và tạo tiến độ/bằng chứng mới.
6. **Đóng đợt**
   - **Given** mọi lỗi trong phạm vi đã được Supervisor xác nhận đạt
   - **Then** đợt chuyển `Hoàn tất`, lưu người/thời điểm và khóa kết quả nghiệp vụ theo chính sách lịch sử.
7. **Vượt phạm vi**
   - Nếu phát sinh lỗi ngoài danh sách hoặc chi phí thực tế vượt chi phí duyệt, hệ thống chặn hoàn tất phần vượt và yêu cầu PM lập hồ sơ điều chỉnh/trình lại.

**Mã truy vết:** `HT09-HT13`.

### US-20 - Đo đạc thực tế theo nhu cầu và xác minh hư hỏng chính thức

**User Story**  
Là PM, tôi muốn chọn drone hoặc giao Repair Crew kiểm chứng; khi cần số đo vật lý hoặc bằng chứng bổ sung, tôi muốn giao và đánh giá phép đo trước quyết định liên quan.

**Acceptance Criteria**

1. **Chọn cách kiểm chứng**
   - Given PM giữ lại `Preliminary Defect` hoặc IncidentCase cần xác minh
   - When PM xem phạm vi, độ tin cậy và căn cứ hiện có
   - Then PM chọn drone hoặc Crew kiểm tra trực tiếp; kiểm tra từ phản ánh chưa có Survey/Defect được xác nhận vẫn hợp lệ.
2. **Giao đo khi cần**
   - Given quyết định cần depression depth, slab faulting, shoulder extent hoặc bằng chứng thực địa chưa đủ
   - When PM giao nhiệm vụ
   - Then hệ thống ghi nguồn IncidentCase/Defect, phạm vi, loại đo, thời hạn và liên kết Survey/RoadSectionVersion khi có; không bắt tạo Survey giả.
   - Nếu không cần số đo vật lý, PM không bị chặn xác minh chỉ vì chưa có nhiệm vụ đo.
3. **Ghi và chuẩn hóa**
   - Repair Crew nhập ngoại tuyến các trường đo, vị trí `geography(4326)`, dụng cụ/phương pháp, người/thời điểm và bằng chứng; bản chưa đồng bộ không phải kết quả máy chủ.
   - Khi gửi, hệ thống tạo phiên bản `FieldInspectionSession`/`GroundTruthMeasurement`, không ghi đè bản cũ.
4. **PM kết luận**
   - PM kiểm tra bằng chứng drone/thực địa; nếu có nhiệm vụ đo thì kiểm tra đơn vị, dụng cụ, phương pháp, vị trí và độ phù hợp.
   - PM có thể chấp nhận `Defect` chuyển `OPEN` → `VERIFIED` khi căn cứ đủ, kèm số đo đã chấp nhận nếu quyết định cần đo; hoặc yêu cầu bổ sung/chuyển `REJECTED` có lý do.
5. **Không tự động kết luận**
   - AI chạy xong, `No detections` hoặc số đo không tự tạo/sửa `Defect`, chuyển `Warranty`, tạo lệnh sửa hoặc công bố `NO_DEFECT`; PM quyết định.
   - Chỉ lỗi đã `VERIFIED` và mọi phép đo bắt buộc theo nhu cầu đã hoàn tất/được chấp nhận mới đủ điều kiện vào đợt sửa.
6. **Audit, quyền và nghiên cứu**
   - Giao, nhận/từ chối, gửi, chấp nhận và yêu cầu bổ sung lưu người/thời điểm/lý do/nguồn; Crew chỉ xem nhiệm vụ được giao.
   - `RS01–RS06` ground truth nghiên cứu vẫn bắt buộc, độc lập với việc có cần đo hỗ trợ nghiệp vụ hay không.

**Mã truy vết:** `AI13`, `TN01-TN06`, `TN12`, `CN05-CN09`.

### US-15 - Dashboard quản lý dự án, chi phí và rủi ro

**User Story**  
Là Supervisor hoặc PM, tôi muốn xem dashboard theo phạm vi quyền để theo dõi tình trạng bảo hành, lỗi còn mở, chi phí, khảo sát và rủi ro cần ưu tiên.

**Acceptance Criteria**

1. Supervisor xem tổng quan toàn danh mục; PM chỉ xem các dự án được giao.
2. Dashboard hiển thị trạng thái dự án, khảo sát, lỗi còn mở, dự án sắp hết hạn bảo hành và các việc cần xử lý.
3. Chi phí được tách tối thiểu thành dự toán chờ duyệt, dự toán đã duyệt và chi phí thực tế; tổng không cộng trùng phiên bản.
4. Chỉ báo rủi ro cao/hư hỏng phát triển nhanh hiển thị kèm nguồn dữ liệu, kỳ khảo sát và độ tin cậy; không trình bày như dự báo chắc chắn.
5. Supervisor có thể so sánh dự án/kỳ khảo sát theo phạm vi và loại mặt đường tương thích; dữ liệu thiếu tương thích phải được cảnh báo.
6. Mọi con số trên dashboard có liên kết tới hồ sơ nguồn hoặc bộ lọc đã áp dụng.

**Mã truy vết:** `BC01-BC05`.

### US-16 - Xuất hồ sơ, nguồn gốc và tra cứu lưu trữ

**User Story**  
Là Supervisor hoặc PM, tôi muốn xuất báo cáo và hồ sơ bằng chứng theo dự án/đoạn/lỗi/khoảng thời gian để tái hiện được nội dung, nguồn gốc và tính toàn vẹn tại thời điểm xuất.

**Acceptance Criteria**

1. Người dùng chỉ chọn được dự án, đoạn, lỗi và khoảng thời gian trong phạm vi quyền.
2. **When** xuất báo cáo
   **Then** hệ thống lưu bộ lọc, người xuất, thời điểm, trạng thái và phiên bản dữ liệu được dùng.
3. Hồ sơ tổng hợp gồm, khi có: bàn giao, khảo sát/baseline, ảnh gốc, loại và số đo lỗi, độ không chắc chắn, quyết định xác minh, sửa chữa, chi phí và lịch sử duyệt.
4. Tệp xuất kèm nguồn gốc: mã tệp, checksum/dấu kiểm tra toàn vẹn, thời gian, tác giả, phiên bản mô hình và lịch sử sửa đổi.
5. Dữ liệu thiếu hoặc bằng chứng chưa có phải được ghi rõ trong báo cáo; hệ thống không tạo cảm giác hồ sơ đầy đủ.
6. Phương án xuất MVP hỗ trợ PDF tổng hợp và ZIP dữ liệu gốc/bảng kê khi cấu hình cho phép; lỗi tạo tệp phải báo rõ và không làm mất dữ liệu nguồn.
7. Sau khi dự án đóng, Supervisor/PM vẫn tra cứu được hồ sơ trong phạm vi quyền cho tới hết thời hạn lưu trữ hoặc lâu hơn nếu đang giữ tranh chấp.

**Mã truy vết:** `BC06-BC10`, `QT09`, `QT11-QT14`.

### US-17 - Quản lý tài khoản, quyền, danh mục và nhắc việc

**User Story**  
Là Supervisor (Admin), tôi muốn quản lý vòng đời tài khoản, quyền dự án, danh mục lỗi, quy tắc phân mức và cấu hình nhắc để hệ thống vận hành nhất quán.

**Acceptance Criteria**

1. **Tài khoản**
   - Admin tạo/cập nhật/ngừng sử dụng tài khoản, gán một trong năm vai trò và ghi nhật ký thay đổi.
2. **Ngừng tài khoản có việc mở**
   - **When** tài khoản bị ngừng sử dụng
   - **Then** hệ thống thu hồi phiên, chặn đăng nhập mới, giữ lịch sử, lập danh sách việc cần bàn giao và thông báo người có quyền phân công lại.
   - Không tự hủy, tự hoàn tất hoặc xóa bản nháp/công việc đang mở.
3. **Phân quyền**
   - Admin cấp/sửa quyền dự án theo vai trò; thay đổi được audit và có hiệu lực ngay. PM/Drone Operator/Repair Crew không xem được dữ liệu ngoài membership active, còn hiệu lực và đúng vai trò.
   - Khi Admin đổi role toàn hệ thống, hệ thống thu hồi toàn bộ phiên và refresh token trong cùng transaction; JWT role cũ không tiếp tục cấp quyền.
   - Khi quyền project bị đổi, hết hạn hoặc kết thúc, request kế tiếp phải bị kiểm tra theo membership hiện tại phía server; client claim không được dùng thay thế.
4. **Danh mục**
   - Admin thêm hoặc ngừng sử dụng loại lỗi; mục cũ không bị xóa khỏi lịch sử.
5. **Quy tắc phân mức**
   - Admin tạo phiên bản quy tắc theo chuẩn và loại mặt đường, lưu căn cứ; thay phiên bản không làm thay đổi ngược kết quả lịch sử.
6. **Nhắc việc**
   - Admin cấu hình nhắc khảo sát và mốc trước hạn bảo hành; cấu hình không tự áp dụng thời hạn pháp lý chưa được xác minh.

**Mã truy vết:** `QT01-QT05`, `CN10`.

### US-18 - Quản trị mô hình AI, tác vụ và thiết bị

**User Story**  
Là Supervisor (Admin), tôi muốn quản lý phiên bản mô hình AI, theo dõi hàng đợi/tài nguyên và thông tin thiết bị để biết kết quả được tạo bởi mô hình nào và xử lý lỗi vận hành có kiểm soát.

**Acceptance Criteria**

1. **Phiên bản mô hình**
   - Admin tạo, phát hành hoặc ngừng sử dụng phiên bản; lưu chỉ số đánh giá, ngưỡng vận hành, thời điểm và phiên bản áp dụng.
2. **Nguồn kết quả**
   - Mỗi phát hiện AI giữ tham chiếu tới phiên bản mô hình; đổi mô hình không làm mất nguồn của kết quả cũ.
3. **Tập huấn luyện**
   - Chỉ nhãn đã được PM duyệt mới được xuất; tệp xuất có nguồn gốc, phiên bản và quyền truy cập.
4. **Giám sát tác vụ**
   - Admin xem tải, tiến trình, lỗi Backend/hàng đợi AI, dung lượng và trạng thái từng tác vụ.
5. **Thử lại an toàn**
   - Tác vụ thất bại do hạ tầng có thể thử lại trên dữ liệu còn nguyên; lỗi dữ liệu phải chuyển PM quyết định bổ sung.
6. **Thiết bị và quy trình**
   - Admin quản lý thông tin thiết bị bay, checklist và tài liệu chuyến bay; hệ thống không gửi lệnh điều khiển thiết bị bay.

**Mã truy vết:** `QT06-QT10`, `KS10`, `KS13`.

### US-19 - Lưu trữ, giữ hồ sơ và xóa dữ liệu có phê duyệt

**User Story**  
Là PM, tôi muốn lập yêu cầu xóa hồ sơ đã hết hạn; là Supervisor, tôi muốn kiểm tra điều kiện, trạng thái tranh chấp và phê duyệt để dữ liệu chỉ bị xóa đúng chính sách.

**Acceptance Criteria**

1. **Điều kiện lưu trữ**
   - Hệ thống tính tối thiểu tới hết bảo hành cộng 5 năm và hiển thị căn cứ tính cho từng hồ sơ.
2. **Lập yêu cầu**
   - **Given** hồ sơ đủ điều kiện thời hạn
   - **When** PM chọn phạm vi và lập yêu cầu
   - **Then** hệ thống đưa yêu cầu vào trạng thái chờ Supervisor, chưa xóa dữ liệu.
3. **Kiểm tra tranh chấp**
   - **Given** hồ sơ đang bị giữ do tranh chấp hoặc phạm vi chưa rõ
   - **Then** hệ thống chặn lập/duyệt xóa và hiển thị lý do.
4. **Phê duyệt**
   - **When** Supervisor xem xét và phê duyệt
   - **Then** hệ thống chỉ xóa đúng phạm vi đã duyệt theo chính sách, lưu biên bản, người, thời điểm và kết quả.
5. **Từ chối**
   - **When** Supervisor từ chức
   - **Then** phải có lý do; dữ liệu vẫn tra cứu được và yêu cầu chuyển trạng thái bị từ chối.
6. **Giữ/gỡ giữ hồ sơ**
   - Admin/Supervisor ghi căn cứ và lý do khi thiết lập hoặc gỡ giữ; gỡ giữ không tự động xóa dữ liệu.
7. **Phân biệt dọn thiết bị**
   - Dọn bản sao cục bộ trên điện thoại chỉ là thao tác đồng bộ an toàn, không được coi là xóa hồ sơ máy chủ.

**Mã truy vết:** `QT11-QT14`.

## 4. Ma trận trạng thái MVP

| Đối tượng | Trạng thái tối thiểu | Điều kiện chuyển chính |
|---|---|---|
| Yêu cầu khảo sát | Mới giao, Đã nhận, Từ chối, Đã hủy, Hoãn, Đang thực hiện, Đã nộp, Yêu cầu bổ sung, Hoàn tất | Theo US-04, US-05, US-06, US-07. |
| Dữ liệu khảo sát | Đang sao chép, Đã lưu cục bộ, Chờ tải, Đang tải, Máy chủ xác nhận toàn vẹn, Không hợp lệ | Chỉ xác nhận máy chủ khi đủ tệp và kiểm tra toàn vẹn đạt. |
| Tác vụ phân tích | Chờ xử lý, Đang xử lý, Thất bại có thể thử lại, Cần bổ sung dữ liệu, Hoàn tất | Lỗi hạ tầng và lỗi dữ liệu phải phân biệt. |
| Phát hiện AI / Preliminary Defect | Chờ rà soát, Cần kiểm tra thêm, Chờ giao đo, Đang đo, Chờ PM đánh giá, Đã loại bỏ, Đã xác minh chính thức | Preliminary Defect ánh xạ `Defect OPEN`; chỉ chuyển `VERIFIED` sau khi PM chấp nhận đo. |
| Nhiệm vụ đo đạc thực tế | Mới giao, Đã nhận, Từ chối, Đang thực hiện, Cần bổ sung, Đã gửi, Hoàn tất | Repair Crew thực hiện; bản đo đã gửi không bị ghi đè. |
| Đợt sửa | Nháp, Chờ duyệt, Yêu cầu chỉnh sửa, Đã duyệt, Đã phân công, Từ chối, Đang thực hiện, Chờ kiểm tra, Cần sửa lại, Hoàn tất | Đợt chỉ phân công sau khi phiên bản hiện tại được duyệt. |
| Kết quả từng lỗi | Chưa sửa, Đang sửa, Chờ PM kiểm tra, Cần sửa lại, Chờ Supervisor xác nhận, Đã hoàn tất | Một lỗi đạt không bị kéo lùi vì lỗi khác. |

## 5. Definition of Done cho MVP

Một User Story chỉ được xem là hoàn thành khi:

- Tất cả Acceptance Criteria bắt buộc của story đã được kiểm thử ở luồng thành công và các ngoại lệ nêu trong story.
- Quyền truy cập được kiểm thử với đúng vai trò và một người ngoài phạm vi.
- Các chuyển trạng thái hợp lệ và chuyển trạng thái bị chặn được kiểm thử.
- Dữ liệu, tệp, phiên bản và nhật ký truy vết được tạo đúng; không có mật khẩu hoặc dữ liệu nhạy cảm không được phép trong log.
- Luồng ngoại tuyến/đồng bộ liên quan đã kiểm thử mất mạng, nối mạng lại, lỗi tạm thời và dữ liệu chưa toàn vẹn.
- Không có thao tác MVP nào tự động kết luận trách nhiệm hợp đồng, tự thêm lỗi phát sinh vào đợt đã duyệt hoặc xóa lịch sử.

## 6. Ma trận truy vết đầy đủ

| Mã chức năng | User Story MVP | Ghi chú |
|---|---|---|
| `PA01`-`PA07` | US-21, US-22, US-23 | Reporter, IncidentReport/Case, public timeline, checking and published repair result. |
| `DA13`-`DA16` | US-24 | Polyline/segment versioning and RouteCapture design. |
| `KS15`, `KS16` | US-25 | Target bands and coverage separate from AI/job status. |
| `AI15`-`AI17` | US-26 | External async jobs, immutable manifest, retry/dedup and context overlap. |
| `CN01`, `CN02`, `CN03`, `CN04`, `CN10` | US-01 | Đăng nhập, hồ sơ, phạm vi, thông báo, đặt lại mật khẩu. |
| `CN05`, `CN06`, `CN07`, `CN08`, `CN09` | US-02 | Ngoại tuyến, nháp, đồng bộ, kiểm tra toàn vẹn, dọn bản sao. |
| `DA01`, `DA02`, `DA03`, `DA04`, `DA05`, `DA12` | US-03 | Dự án, tuyến/đoạn, bàn giao, bảo hành, nhân sự, đóng dự án. |
| `DA06`, `DA07`, `DA08`, `DA09`, `DA10`, `DA11` | US-04 | Kế hoạch, nhắc việc, yêu cầu, hoãn, baseline, theo dõi tình trạng. |
| `KS01`, `KS02`, `KS03`, `KS04`, `KS14` | US-05 | Phân công, tiếp nhận, từ chối, phân công lại, hủy/thu hồi. |
| `KS05`, `KS06`, `KS07`, `KS08`, `KS09`, `KS10` | US-06 | Chuyến bay, sao chép video, SRT, chất lượng, tải lên, xử lý. |
| `KS11`, `KS12`, `KS13` | US-07 | Bay bổ sung, nộp bổ sung, thử lại tác vụ. |
| `AI01`, `AI04`, `AI05`, `AI06`, `AI07` | US-08 | Xem, xác nhận, hiệu chỉnh, loại bỏ, lịch sử xác minh. |
| `AI08`, `AI09`, `AI10`, `AI11`, `AI12` | US-09 | Gộp, đối sánh kỳ, baseline, diễn biến, cảnh báo. |
| `AI14` | US-10 | Duyệt nhãn huấn luyện. |
| `SC01`, `SC02`, `SC03`, `SC04`, `SC05`, `SC06`, `SC07`, `SC08`, `SC09`, `SC12` | US-11 | Lập, tính chi phí, trình, duyệt, trả và trình lại. |
| `SC10`, `SC11` | US-12 | Phân công và bàn giao Repair Crew. |
| `HT01`, `HT02`, `HT03`, `HT04`, `HT05`, `HT06`, `HT07`, `HT08`, `HT14`, `HT15` | US-13 | Tiếp nhận, hướng dẫn, phân việc, bằng chứng, báo cáo, từ chối. |
| `HT09`, `HT10`, `HT11`, `HT12`, `HT13` | US-14 | Kiểm tra, trả sửa, trình, xác nhận, sửa lại. |
| `AI13`, `TN01`, `TN02`, `TN03`, `TN04`, `TN05`, `TN06`, `TN12` | US-20 | Giao, thực hiện, gửi và đánh giá đo đạc thực tế; không tự kết luận bảo hành. |
| `BC01`, `BC02`, `BC03`, `BC04`, `BC05` | US-15 | Dashboard dự án, chi phí, rủi ro, so sánh. |
| `BC06`, `BC07`, `BC08`, `BC09`, `BC10` | US-16 | Xuất báo cáo, hồ sơ bằng chứng, nguồn gốc, lưu trữ. |
| `QT01`, `QT02`, `QT03`, `QT04`, `QT05` | US-17 | Tài khoản, quyền, danh mục, quy tắc, nhắc việc. |
| `QT06`, `QT07`, `QT08`, `QT09`, `QT10` | US-18 | Mô hình, nhãn, tác vụ, nhật ký, thiết bị. |
| `QT11`, `QT12`, `QT13`, `QT14` | US-19 | Xóa hết hạn, phê duyệt, kiểm tra lưu trữ, legal hold. |

### Mã không thuộc phạm vi MVP

| Mã | Lý do loại khỏi MVP |
|---|---|
| `AI02`, `AI03` | Tính năng sản phẩm/phép đo phụ thuộc pipeline nâng cao; không phải điều kiện nghiệm thu MVP, nhưng kết quả đo vẫn được dùng trong Research Validation Track khi đề cương yêu cầu. |

## 7. Liên kết nguồn

- Đặc tả use case nguồn: [Dac_ta_UseCase_v2.md](Dac_ta_UseCase_v2.md).
- Các mã chức năng trong tài liệu này giữ nguyên mã `CN`, `DA`, `KS`, `AI`, `SC`, `HT`, `BC`, `QT` của đặc tả nguồn để dùng khi phân tích, thiết kế, lập trình và kiểm thử.
