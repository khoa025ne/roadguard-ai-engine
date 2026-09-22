# RoadGuard — Data Dictionary v1

> Thiết kế đích đồng bộ ngày 22/09/2026 theo [Incident/Segment](RoadGuard_Incident_Segment_Design_v1.md) và [AI/Edge](RoadGuard_AI_Segment_Edge_Design_v1.md). Các bảng/cột mới và thay đổi nullable dưới đây là thiết kế đề xuất, không phải xác nhận code hoặc migration đã có. Mốc bàn giao backend/mock AI ngày 18/09/2026 tại [ADR 003](../adr/003-backend-delivery-and-ai-boundary.md) là lịch sử; thiết kế đích bổ sung adapter AI ngoài qua hợp đồng có phiên bản. Research Validation vẫn bắt buộc trong phạm vi nghiên cứu; mock không chứng minh độ chính xác thực nghiệm.

Tài liệu này là từ điển dữ liệu mức logic cho RoadGuard. Nó được lập từ:

- [Domain Model](RoadGuard_Domain_Model_v1.md);
- [Domain Model entity list](RoadGuard_Domain_Model_v1.md);
- [Use Case](Dac_ta_UseCase_v2.md);
- [User Stories](User_Stories_Acceptance_Criteria_v2.md);
- [Incident/segment workflow](RoadGuard_Incident_Segment_Design_v1.md);
- đề cương nghiên cứu `RoadGuard_Contractor_Warranty_Inspection_phuonglhk.md`.

## 1. Phạm vi và cách đọc

Data Dictionary mô tả tên trường chuẩn, kiểu dữ liệu logic, khả năng rỗng, khóa/tham chiếu và định nghĩa nghiệp vụ. Bản này đã điều chỉnh theo stack được chọn: **SQL Server + C# + Entity Framework Core**. Đây vẫn là từ điển dữ liệu mức logic; DDL/migration vật lý sẽ được tạo sau khi chốt các điểm ở mục 6.

Ký hiệu nguồn:

| Mã | Ý nghĩa |
|---|---|
| `SRC` | Có căn cứ trực tiếp từ User Story/Use Case hoặc quy tắc đã nêu trong Domain Model. |
| `DEC` | Quyết định thiết kế đã chốt: audit log riêng, Warranty riêng, QualityCheck hai cấp, SupplementarySurveyRequest độc lập và đo vật lý khi quy tắc đo yêu cầu; nhánh kiểm chứng ban đầu được chọn drone hoặc thực địa. |
| `PROP` | Đề xuất cần xác nhận khi chốt schema/API; không được hiểu là yêu cầu nghiệp vụ đã được nguồn bắt buộc. |

## 2. Quy ước dữ liệu dùng chung

### 2.1 Kiểu dữ liệu logic

| Kiểu | Quy ước |
|---|---|
| `UUID` | Định danh logic; ánh xạ SQL Server thành `uniqueidentifier`, khuyến nghị GUID tuần tự/UUIDv7 để giảm phân mảnh clustered index. |
| `TEXT` | Chuỗi dài, nội dung tự do hoặc ghi chú. |
| `VARCHAR(n)` | Chuỗi có giới hạn hiển thị/tra cứu. |
| `ENUM` | Tập giá trị hữu hạn; trong C# dùng `enum`; mặc định lưu SQL Server bằng `tinyint` với enum có underlying type `byte`, hoặc `int` khi cần miền giá trị lớn hơn. |
| `BOOLEAN` | Đúng/sai; không dùng `NULL` nếu đã có giá trị mặc định. |
| `INTEGER` | Số nguyên đếm được. |
| `DECIMAL(p,s)` | Số đo/tiền cần độ chính xác; toàn hệ thống dùng VND và tiền dùng `decimal(19,2)`, không dùng SQL Server `money`. |
| `TIMESTAMPTZ` | Kiểu logic; ánh xạ SQL Server thành `datetimeoffset(7)`, lưu UTC. |
| `DATE` | Ngày lịch, không có giờ. |
| `JSONB` | JSON có cấu trúc; ánh xạ SQL Server thành `nvarchar(max)` kèm `ISJSON`/computed column khi cần truy vấn. |
| `GEOMETRY` | Kiểu không gian SQL Server (`geometry` hoặc `geography`), không phải PostGIS; `LineString` cho đoạn đường, `Point` cho vị trí. |
| `CHECKSUM` | Chuỗi checksum, khuyến nghị SHA-256 dạng hex. |
| `URI` | Địa chỉ tham chiếu object storage hoặc tài nguyên nội bộ; không coi là nội dung tệp. |

### 2.2 Trường nền tảng

Các aggregate/entity có vòng đời thông thường dùng các trường sau, trừ log append-only hoặc entity immutable:

| Trường | Kiểu | Null | Định nghĩa |
|---|---|---:|---|
| `id` | `UUID` | Không | Khóa chính ổn định, không đổi trong toàn bộ vòng đời. |
| `created_at` | `TIMESTAMPTZ` | Không | Thời điểm tạo bản ghi, do server ghi. |
| `created_by_user_id` | `UUID` | Có | Người tạo; `NULL` nếu bản ghi do hệ thống tạo. FK tới `User.id`. |
| `updated_at` | `TIMESTAMPTZ` | Không | Thời điểm cập nhật metadata gần nhất; không dùng để thay thế lịch sử nghiệp vụ. |
| `version_no` | `INTEGER` | Có | Số phiên bản tăng dần đối với entity `[VER]`; bắt đầu từ 1. |
| `status` | `ENUM` | Có | Trạng thái vòng đời của entity; chỉ dùng khi entity có state machine. |

`AuditLog`, `PasswordResetLog`, `AccountStatusChangeLog`, `RetentionDeletionLog`, `RepairEvidence` và snapshot version là append-only: không update-in-place nội dung nghiệp vụ; nếu cần sửa phải tạo bản ghi/phiên bản mới.

### 2.3 Quy tắc khóa và tham chiếu

- Tên FK dùng hậu tố `_id`; tên tham chiếu phiên bản dùng `_version_id`.
- FK tới aggregate khác là tham chiếu logic; invariant liên aggregate phải được kiểm tra ở application/domain service.
- Không dùng polymorphic FK cho dữ liệu nghiệp vụ chính. `AuditLog.entity_type/entity_id` và `Notification.source_entity_type/source_entity_id` là ngoại lệ có chủ đích.
- Tất cả thời điểm nghiệp vụ dùng `TIMESTAMPTZ`; ngày hiệu lực bảo hành dùng `DATE` nếu không cần giờ.
- Không lưu password, access token, refresh token dạng plaintext trong bất kỳ log nào.

### 2.4 Ánh xạ SQL Server và C# / EF Core

| Kiểu logic | SQL Server | C# / EF Core | Ghi chú |
|---|---|---|---|
| `UUID` | `uniqueidentifier` | `Guid` | Dùng GUID tuần tự/UUIDv7 do ứng dụng tạo; tránh GUID ngẫu nhiên làm clustered key nếu bảng lớn. |
| `TEXT` | `nvarchar(max)` | `string` | Chỉ dùng cho nội dung dài; không tạo index trực tiếp. |
| `VARCHAR(n)` | `nvarchar(n)` | `string` | Ưu tiên Unicode vì tên/ngữ liệu tiếng Việt. |
| `BOOLEAN` | `bit` | `bool` | Có default rõ ràng, không nullable nếu không có trạng thái thứ ba. |
| `INTEGER` | `int` | `int` | Số thứ tự, số lượng nguyên. |
| `ENUM` | `tinyint` hoặc `int` | `enum : byte` hoặc `enum` mặc định `int` | Khuyến nghị `enum : byte` + `tinyint` cho status/scope; gán số explicit, không đổi/reorder giá trị đã phát hành. |
| `DECIMAL(p,s)` | `decimal(19,2)` cho tiền; `decimal(p,s)` theo phép đo | `decimal` | VND; không dùng `float/double` cho tiền. |
| `TIMESTAMPTZ` | `datetimeoffset(7)` | `DateTimeOffset` | Lưu UTC (`+00:00`), API trả ISO-8601. |
| `DATE` | `date` | `DateOnly` | Ngày không có múi giờ. |
| `JSONB` | `nvarchar(max)` + `CHECK (ISJSON(...)=1)` | `JsonDocument`, `JsonElement` hoặc owned type | Snapshot audit cần schema version và giới hạn kích thước. |
| `GEOMETRY` | `geometry`/`geography` | NetTopologySuite `Point`, `LineString`, `Polygon` | EF Core SQL Server cần bật NetTopologySuite. |
| `CHECKSUM` | `char(64)` | `string` | SHA-256 hex lowercase. |
| `URI` | `nvarchar(2048)` | `string` | Chỉ metadata URI, không chứa file binary. |

### 2.5 Chuẩn không gian và SRID

SQL Server không sử dụng PostGIS; `SRID` vẫn là mã hệ quy chiếu được lưu trên đối tượng `geometry`/`geography`. Đề xuất cho RoadGuard:

| Mục đích | Kiểu SQL Server | SRID | Quyết định |
|---|---|---:|---|
| GPS/raw location, điểm ảnh, vị trí bay | `geography` | `4326` (WGS 84) | Chuẩn nhập liệu mặc định, tọa độ kinh/vĩ độ, khoảng cách trả theo mét. |
| Đoạn đường và phép đo kỹ thuật cần mặt phẳng | `geometry` | `32648` hoặc `32649` | Chọn UTM zone theo kinh tuyến khu vực dự án; không được trộn hai zone trong cùng phép đo. |
| Dữ liệu VN-2000 theo hồ sơ trắc địa | `geometry` | SRID VN-2000 đã được cơ quan trắc địa xác nhận | Chỉ dùng khi dự án cung cấp đúng mã EPSG/SRID; phải lưu trong cấu hình dự án. |

Quy tắc vận hành: dữ liệu GPS nhập vào `geography(4326)`; khi cần tính chiều dài/diện tích/chồng lấn kỹ thuật, chuyển đổi có kiểm soát sang CRS phẳng của dự án. Mỗi geometry phải có đúng SRID của cột; cấm ghi tọa độ không rõ hệ quy chiếu hoặc tự gán `0`.

Trong Data Dictionary, trường `GEOMETRY(...)` là kiểu logic; DDL SQL Server phải ghi rõ `geography`/`geometry` và SRID tương ứng. Tên “PostGIS” trong các bản cũ được thay bằng “SQL Server Spatial”.

## 3. Từ điển trường theo entity

### 3.1 Auth & Access

#### `User` — tài khoản nội bộ và Reporter

| Trường | Kiểu | Null | Khóa/Tham chiếu | Nguồn | Định nghĩa và ràng buộc |
|---|---|---:|---|---|---|
| `id` | UUID | Không | PK | SRC | Định danh tài khoản. |
| `username` | VARCHAR(100) | Không | UQ | SRC | Tên đăng nhập duy nhất. |
| `email` | VARCHAR(254) | Có | UQ khi có | PROP | Email nhận thông báo/khôi phục. |
| `display_name` | VARCHAR(200) | Không |  | SRC | Tên hiển thị. |
| `password_hash` | TEXT | Không |  | PROP | Hash mật khẩu; không bao giờ trả về API/log. |
| `role_code` | ENUM | Không | FK `Role.code` | SRC | Vai trò toàn hệ thống authoritative, một trong năm mã chuẩn của thiết kế đích. Chỉ Supervisor/Admin được đổi; thay đổi phát `UserRoleChanged`, ghi audit và thu hồi toàn bộ phiên/token đang hoạt động. |
| `reporter_type` | ENUM | Có |  | PROP | Citizen/InvestorRepresentative (`CITIZEN`, `INVESTOR_REPRESENTATIVE`); bắt buộc khi role REPORTER. |
| `status` | ENUM | Không |  | SRC | `ACTIVE`, `SUSPENDED`, `PENDING`; suspended chặn đăng nhập/reset. |
| `must_change_password` | BOOLEAN | Không |  | SRC | Đặt `true` sau reset bắt buộc đổi ở lần đăng nhập kế tiếp. |
| `last_login_at` | TIMESTAMPTZ | Có |  | PROP | Lần đăng nhập thành công gần nhất. |
| `suspended_at` | TIMESTAMPTZ | Có |  | SRC | Thời điểm ngừng tài khoản. |
| `created_at` | TIMESTAMPTZ | Không |  | SRC | Thời điểm tạo. |

#### `Role` — danh mục vai trò

| Trường | Kiểu | Null | Khóa/Tham chiếu | Nguồn | Định nghĩa |
|---|---|---:|---|---|---|
| `code` | VARCHAR(40) | Không | PK | SRC | `SUPERVISOR`, `PM`, `DRONE_OPERATOR`, `REPAIR_CREW`, `REPORTER`. Runtime hiện có bốn role; `Reporter = 5` là đề xuất thêm, giữ nguyên giá trị 1–4. |
| `name` | VARCHAR(100) | Không |  | SRC | Tên hiển thị vai trò. |
| `is_active` | BOOLEAN | Không |  | PROP | Không cho gán mới nếu false; không xóa lịch sử. |

#### `Session` / `RefreshToken` — phiên xác thực

| Entity | Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---|---:|---|---|
| `Session` | `id` | UUID | Không | PK | Phiên đăng nhập. |
| `Session` | `user_id` | UUID | Không | FK `User.id` | Chủ phiên. |
| `Session` | `issued_at` | TIMESTAMPTZ | Không |  | Thời điểm cấp. |
| `Session` | `device_metadata_json` | `nvarchar(max)` | Có | `CHECK (device_metadata_json IS NULL OR ISJSON(device_metadata_json) = 1)` | Metadata thiết bị tại thời điểm cấp phiên; write-once, không dùng làm tín hiệu authorization và phải qua application-level schema validation. |
| `Session` | `expires_at` | TIMESTAMPTZ | Không |  | Thời điểm hết hạn. |
| `Session` | `revoked_at` | TIMESTAMPTZ | Có |  | Thu hồi khi logout, reset password, suspend, phát hiện replay hoặc thay đổi `User.role_code`. |
| `RefreshToken` | `id` | UUID | Không | PK | Định danh token record. |
| `RefreshToken` | `session_id` | UUID | Không | FK `Session.id` | Token thuộc phiên. |
| `RefreshToken` | `token_hash` | TEXT | Không | UQ | Chỉ lưu hash, không lưu token plaintext. |
| `RefreshToken` | `expires_at` | TIMESTAMPTZ | Không |  | Hạn token. |
| `RefreshToken` | `revoked_at` | TIMESTAMPTZ | Có |  | Thời điểm thu hồi. |

Khi `Session.device_metadata_json` khác null, application-level schema validation phải chấp nhận duy nhất JSON object phiên bản 1 gồm `schema_version = 1` và các string field tùy chọn `device_id`, `platform`, `app_version`; từ chối unknown properties, non-object JSON, secret, password, access token và refresh token. Các giới hạn độ dài do options/schema cấu hình, không hard-code trong domain. Metadata được phân loại ít nhất là `INTERNAL`, có thể chứa PII tùy nguồn, không trả qua API nghiệp vụ/public, không ghi log và không được sửa sau khi tạo Session.

#### `PasswordResetLog` — nhật ký reset mật khẩu (giữ riêng)

| Trường | Kiểu | Null | Khóa/Tham chiếu | Nguồn | Định nghĩa |
|---|---|---:|---|---|---|
| `id` | UUID | Không | PK | DEC | Bản ghi append-only. |
| `target_user_id` | UUID | Không | FK `User.id` | DEC | Tài khoản được reset. |
| `performed_by_user_id` | UUID | Có | FK `User.id` | DEC | Người hoặc hệ thống thực hiện. |
| `occurred_at` | TIMESTAMPTZ | Không |  | DEC | Thời điểm xảy ra. |
| `reason` | TEXT | Có |  | DEC | Lý do reset. |
| `result` | ENUM | Không |  | DEC | `SUCCESS`, `FAILED`, `REJECTED`. |
| `source` | VARCHAR(80) | Không |  | DEC | Kênh/operation tạo log. |
| `correlation_id` | UUID | Có |  | DEC | Liên kết toàn bộ request/transaction. |

Không thêm `password`, `password_hash`, reset token hoặc secret vào entity này.

#### `AccountStatusChangeLog` — nhật ký thay đổi trạng thái tài khoản

| Trường | Kiểu | Null | Khóa/Tham chiếu | Nguồn | Định nghĩa |
|---|---|---:|---|---|---|
| `id` | UUID | Không | PK | DEC | Bản ghi append-only. |
| `target_user_id` | UUID | Không | FK `User.id` | DEC | Tài khoản bị thay đổi. |
| `changed_by_user_id` | UUID | Có | FK `User.id` | DEC | Người/hệ thống thay đổi. |
| `occurred_at` | TIMESTAMPTZ | Không |  | DEC | Thời điểm thay đổi. |
| `from_status` | ENUM | Không |  | DEC | Trạng thái trước. |
| `to_status` | ENUM | Không |  | DEC | Trạng thái sau; phải khác `from_status`. |
| `reason` | TEXT | Không |  | SRC/DEC | Lý do bắt buộc khi suspend/reopen. |
| `source` | VARCHAR(80) | Không |  | DEC | Operation/kênh nguồn. |
| `correlation_id` | UUID | Có |  | DEC | ID truy vết request. |
| `handover_reference` | UUID | Có |  | DEC | Tham chiếu danh sách bàn giao nếu có. |

#### `Notification` — thông báo trong hệ thống

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Định danh thông báo. |
| `recipient_user_id` | UUID | Không | FK `User.id` | Người nhận. |
| `source_entity_type` | VARCHAR(80) | Không | Polymorphic | Loại entity phát sinh sự kiện. |
| `source_entity_id` | UUID | Không | Polymorphic | Entity phát sinh. |
| `event_type` | VARCHAR(80) | Không |  | Loại sự kiện được phép thông báo. |
| `title` | VARCHAR(200) | Không |  | Tiêu đề. |
| `body` | TEXT | Không |  | Nội dung hiển thị. |
| `read_at` | TIMESTAMPTZ | Có |  | Thời điểm đã đọc. |

### 3.2 Project, Road & Warranty

#### `Project`

| Trường | Kiểu | Null | Khóa/Tham chiếu | Nguồn | Định nghĩa |
|---|---|---:|---|---|---|
| `id` | UUID | Không | PK | SRC | Định danh dự án. |
| `project_code` | VARCHAR(50) | Không | UQ | SRC | Mã dự án duy nhất. |
| `name` | VARCHAR(255) | Không |  | SRC | Tên công trình. |
| `description` | TEXT | Có |  | PROP | Mô tả/phạm vi. |
| `engineering_utm_srid` | INTEGER | Có | `32648` hoặc `32649` | DEC | SRID kỹ thuật của dự án; không có default và phải được cấu hình trước khi tạo RoadSectionVersion. |
| `status` | ENUM | Không |  | SRC | `PLANNING`, `ACTIVE`, `CLOSED`. Closed chặn tác nghiệp mới. |
| `start_date` | DATE | Có |  | PROP | Ngày bắt đầu. |
| `end_date` | DATE | Có |  | PROP | Ngày kết thúc thực tế. |
| `created_at` | TIMESTAMPTZ | Không |  | SRC | Thời điểm tạo. |

Reporter truy cập bằng quyền sở hữu IncidentReport và các sự kiện đã công bố; không cần ProjectMember và không có quyền xem toàn dự án. reporter_type chỉ phân loại người gửi, không cấp thêm quyền.

#### `ProjectMember`

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Bản ghi phân quyền dự án. |
| `project_id` | UUID | Không | FK `Project.id` | Dự án được gán. |
| `user_id` | UUID | Không | FK `User.id` | Người được gán. |
| `role_code` | ENUM | Không | FK `Role.code` | Vai trò authoritative trong dự án. Trong MVP, với vai trò tác nghiệp non-Supervisor phải bằng `User.role_code` hiện tại và phù hợp policy của thao tác. |
| `is_primary` | BOOLEAN | Không |  | Đánh dấu PM chính; mỗi dự án tối đa một bản ghi active. |
| `valid_from` | DATE | Không |  | Ngày hiệu lực. |
| `valid_to` | DATE | Có |  | Ngày hết hiệu lực. |
| `status` | ENUM | Không |  | `ACTIVE`, `ENDED`. |

Quy tắc authorization MVP: `User.role_code` là nguồn vai trò toàn hệ thống; `ProjectMember.role_code` là nguồn quyền trong project và phải khớp `User.role_code` đối với vai trò tác nghiệp non-Supervisor. Supervisor chỉ được miễn membership sau khi backend tải và xác nhận role hiện tại từ kho dữ liệu. Thay đổi role toàn hệ thống phát `UserRoleChanged` và thu hồi toàn bộ Session/RefreshToken trong cùng transaction; thay đổi, hết hạn hoặc kết thúc `ProjectMember` có hiệu lực ngay ở request kế tiếp vì backend kiểm tra membership phía server, không tin role/project claim của client. Mọi thay đổi phải ghi `AuditLog` append-only.

#### `RoadSection` và `RoadSectionVersion`

| Entity | Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---|---:|---|---|
| `RoadSection` | `id` | UUID | Không | PK | Định danh đoạn đường logic. |
| `RoadSection` | `project_id` | UUID | Không | FK `Project.id` | Dự án sở hữu đoạn. |
| `RoadSection` | `code` | VARCHAR(80) | Không | UQ trong project | Mã đoạn. |
| `RoadSection` | `name` | VARCHAR(255) | Có |  | Tên/nhãn đoạn. |
| `RoadSectionVersion` | `id` | UUID | Không | PK | Phiên bản bất biến. |
| `RoadSectionVersion` | `road_section_id` | UUID | Không | FK `RoadSection.id` | Đoạn logic gốc. |
| `RoadSectionVersion` | `version_no` | INTEGER | Không | UQ `(road_section_id, version_no)` | Số phiên bản tăng dần. |
| `RoadSectionVersion` | `is_current` | BOOLEAN | Không | UQ filtered theo `road_section_id` | Marker version hiện hành; transaction tạo/chuyển version bảo đảm đúng một marker. |
| `RoadSectionVersion` | `geometry` | GEOMETRY(LineString) | Không | SPATIAL | Hình học đoạn tại thời điểm version. |
| `RoadSectionVersion` | `geometry_status` | ENUM | Không |  | DRAFT hoặc CONFIRMED; hai điểm đầu/cuối chỉ là nháp nếu chưa mô tả tuyến thực. |
| `RoadSectionVersion` | `station_origin_m` | DECIMAL(14,3) | Không |  | Lý trình gốc; offsets tính dọc hình học mét, không nội suy đều lat/lon. |
| `RoadSectionVersion` | `effective_from` | TIMESTAMPTZ | Không |  | Thời điểm có hiệu lực. |
| `RoadSectionVersion` | `change_reason` | TEXT | Không |  | Lý do tạo version. |

Mọi `Survey` và `Defect` có vị trí phải tham chiếu `road_section_version_id`, không chỉ `road_section_id`.

Quyết định D-01 Option B: không tạo FK vòng `RoadSection.current_version_id`. Tạo RoadSection trước, sau đó tạo Version 1 với `is_current = true`; khi đổi hình học, tạo version bất biến mới và đổi marker trong cùng transaction. SQL filtered unique index chặn nhiều current version; application transaction không cho RoadSection tồn tại thiếu current version sau command thành công.

#### `HandoverDocument`

| Trường | Kiểu | Null | Khóa/Tham chiếu | Nguồn | Định nghĩa |
|---|---|---:|---|---|---|
| `id` | UUID | Không | PK | SRC | Hồ sơ bàn giao. |
| `project_id` | UUID | Không | FK `Project.id` | SRC | Dự án bàn giao. |
| `document_no` | VARCHAR(80) | Không | UQ trong project | SRC | Số biên bản/hồ sơ. |
| `handover_date` | DATE | Không |  | SRC | Ngày bàn giao/nghiệm thu. |
| `accepted_by_user_id` | UUID | Có | FK `User.id` | PROP | Người xác nhận trong hệ thống. |
| `file_id` | UUID | Có | FK `File.id` | SRC | Tệp hồ sơ. |
| `notes` | TEXT | Có |  | SRC | Ghi chú. |

`HandoverDocument` không có field `warranty_period`, `warranty_end_date` hoặc field đơn tương đương. Bảo hành nằm ở `Warranty`.

#### `Warranty` — aggregate độc lập

| Trường | Kiểu | Null | Khóa/Tham chiếu | Nguồn | Định nghĩa và ràng buộc |
|---|---|---:|---|---|---|
| `id` | UUID | Không | PK | DEC | Định danh giai đoạn bảo hành. |
| `project_id` | UUID | Không | FK `Project.id` | DEC | Dự án; một dự án có nhiều Warranty. |
| `road_section_id` | UUID | Có | FK `RoadSection.id` | DEC | Đoạn đường áp dụng; null nếu phạm vi toàn dự án. |
| `handover_document_id` | UUID | Có | FK `HandoverDocument.id` | PROP | Hồ sơ làm căn cứ. |
| `handover_date` | DATE | Không |  | SRC | Ngày bàn giao của giai đoạn. |
| `warranty_start_date` | DATE | Không |  | DEC | Ngày bắt đầu. |
| `warranty_end_date` | DATE | Không |  | SRC/DEC | Ngày kết thúc; phải >= ngày bắt đầu. |
| `retained_value` | DECIMAL(19,2) | Có |  | SRC | Giá trị giữ lại liên quan giai đoạn, tính bằng VND. |
| `scope` | ENUM | Không |  | DEC | `PROJECT`, `ROAD_SECTION`, `CONTRACT_ITEM`, `OTHER`. |
| `terms` | TEXT | Có |  | SRC | Điều khoản/phạm vi chi tiết. |
| `source_document_id` | UUID | Có | FK `File.id` | DEC | Tài liệu nguồn. |
| `status` | ENUM | Không |  | PROP | `PLANNED`, `ACTIVE`, `EXPIRED`, `SUSPENDED`. |

Ràng buộc: `warranty_end_date >= warranty_start_date`; không gộp nhiều giai đoạn vào một field hoặc một bản ghi HandoverDocument.

### 3.3 Survey & Quality

#### `SurveyPlan` và `SurveyPlanPostponement`

| Entity | Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---|---:|---|---|
| `SurveyPlan` | `id` | UUID | Không | PK | Kế hoạch khảo sát. |
| `SurveyPlan` | `project_id` | UUID | Không | FK `Project.id` | Dự án. |
| `SurveyPlan` | `road_section_id` | UUID | Không | FK `RoadSection.id` | Phạm vi đoạn. |
| `SurveyPlan` | `planned_start_at` | TIMESTAMPTZ | Không |  | Thời điểm dự kiến bắt đầu. |
| `SurveyPlan` | `planned_end_at` | TIMESTAMPTZ | Không |  | Thời điểm dự kiến kết thúc. |
| `SurveyPlan` | `survey_type` | ENUM | Không |  | `ORIGINAL`, `PERIODIC`, `SUPPLEMENTARY`. |
| `SurveyPlan` | `status` | ENUM | Không |  | `PLANNED`, `POSTPONED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`. |
| `SurveyPlanPostponement` | `id` | UUID | Không | PK | Lịch sử hoãn, append-only. |
| `SurveyPlanPostponement` | `survey_plan_id` | UUID | Không | FK `SurveyPlan.id` | Kế hoạch bị hoãn. |
| `SurveyPlanPostponement` | `postponed_at` | TIMESTAMPTZ | Không |  | Thời điểm hoãn. |
| `SurveyPlanPostponement` | `reason` | TEXT | Không |  | Lý do bắt buộc. |
| `SurveyPlanPostponement` | `new_planned_start_at` | TIMESTAMPTZ | Có |  | Mốc mới nếu đã xác định. |

#### `SurveyRequest` và `SurveyAssignment`

| Entity | Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---|---:|---|---|
| `SurveyRequest` | `id` | UUID | Không | PK | Yêu cầu khảo sát độc lập với kế hoạch. |
| `SurveyRequest` | `project_id` | UUID | Không | FK `Project.id` | Dự án. |
| `SurveyRequest` | `road_section_id` | UUID | Không | FK `RoadSection.id` | Phạm vi khảo sát. |
| `SurveyRequest` | `survey_plan_id` | UUID | Có | FK `SurveyPlan.id` | Kế hoạch nguồn nếu có. |
| `SurveyRequest` | `requested_by_user_id` | UUID | Không | FK `User.id` | Người tạo yêu cầu. |
| `SurveyRequest` | `incident_case_id` | UUID | Có | FK `IncidentCase.id` | Nguồn phản ánh tùy chọn; baseline/định kỳ không cần phản ánh. |
| `SurveyRequest` | `survey_type` | ENUM | Không |  | `ORIGINAL`, `PERIODIC`, `SUPPLEMENTARY`. |
| `SurveyRequest` | `status` | ENUM | Không |  | State machine theo US-05. |
| `SurveyRequest` | `requested_at` | TIMESTAMPTZ | Không |  | Thời điểm tạo. |
| `SurveyRequest` | `cancelled_at` | TIMESTAMPTZ | Có |  | Chỉ có nếu hủy hợp lệ trước server-confirm. |
| `SurveyRequest` | `cancellation_reason` | TEXT | Có |  | Lý do hủy. |
| `SurveyAssignment` | `id` | UUID | Không | PK | Một lần phân công/tiếp nhận. |
| `SurveyAssignment` | `survey_request_id` | UUID | Không | FK `SurveyRequest.id` | Yêu cầu được phân công. |
| `SurveyAssignment` | `operator_user_id` | UUID | Không | FK `User.id` | Drone Operator. |
| `SurveyAssignment` | `assigned_by_user_id` | UUID | Không | FK `User.id` | Người phân công. |
| `SurveyAssignment` | `assigned_at` | TIMESTAMPTZ | Không |  | Thời điểm phân công. |
| `SurveyAssignment` | `accepted_at` | TIMESTAMPTZ | Có |  | Thời điểm nhận. |
| `SurveyAssignment` | `rejected_at` | TIMESTAMPTZ | Có |  | Thời điểm từ chối. |
| `SurveyAssignment` | `rejection_reason` | TEXT | Có |  | Bắt buộc khi từ chối. |
| `SurveyAssignment` | `reassignment_reason` | TEXT | Có |  | Bắt buộc khi phân công lại. |
| `SurveyAssignment` | `ended_at` | TIMESTAMPTZ | Có |  | Kết thúc lần phân công. |

#### `Survey`, `Flight`, `DroneDevice`, `SurveyFile`

| Entity | Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---|---:|---|---|
| `Survey` | `id` | UUID | Không | PK | Aggregate khảo sát. |
| `Survey` | `survey_request_id` | UUID | Có | FK `SurveyRequest.id` | Yêu cầu nguồn. |
| `Survey` | `project_id` | UUID | Không | FK `Project.id` | Dự án. |
| `Survey` | `road_section_version_id` | UUID | Không | FK `RoadSectionVersion.id` | Hình học tại thời điểm khảo sát. |
| `Survey` | `survey_type` | ENUM | Không |  | `ORIGINAL`, `PERIODIC`, `SUPPLEMENTARY`. |
| `Survey` | `is_baseline_confirmed` | BOOLEAN | Không |  | Chỉ PM xác nhận sau khi vượt invariant cross-aggregate. |
| `Survey` | `baseline_confirmed_by_user_id` | UUID | Có | FK `User.id` | PM xác nhận baseline. |
| `Survey` | `baseline_confirmed_at` | TIMESTAMPTZ | Có |  | Thời điểm xác nhận. |
| `Survey` | `status` | ENUM | Không |  | `DRAFT`, `IN_PROGRESS`, `SUBMITTED`, `COMPLETED`, `CANCELLED`. |
| `Flight` | `id` | UUID | Không | PK | Một chuyến bay thuộc Survey. |
| `Flight` | `survey_id` | UUID | Không | FK `Survey.id` | Survey sở hữu. |
| `Flight` | `drone_device_id` | UUID | Có | FK `DroneDevice.id` | Thiết bị sử dụng. |
| `Flight` | `operator_user_id` | UUID | Không | FK `User.id` | Người vận hành. |
| `Flight` | `started_at` | TIMESTAMPTZ | Không |  | Bắt đầu bay. |
| `Flight` | `ended_at` | TIMESTAMPTZ | Có |  | Kết thúc bay. |
| `Flight` | `flight_no` | VARCHAR(80) | Không | UQ trong Survey | Mã chuyến. |
| `DroneDevice` | `id` | UUID | Không | PK | Thiết bị bay. |
| `DroneDevice` | `serial_no` | VARCHAR(120) | Không | UQ | Số serial. |
| `DroneDevice` | `model` | VARCHAR(120) | Có |  | Model thiết bị. |
| `DroneDevice` | `status` | ENUM | Không |  | `ACTIVE`, `MAINTENANCE`, `RETIRED`. |
| `DroneDevice` | `checklist_version` | VARCHAR(50) | Có |  | Phiên bản checklist. |
| `SurveyFile` | `id` | UUID | Không | PK | Tệp video/SRT thuộc Survey. |
| `SurveyFile` | `survey_id` | UUID | Không | FK `Survey.id` | Survey sở hữu. |
| `SurveyFile` | `flight_id` | UUID | Có | FK `Flight.id` | Chuyến bay nguồn. |
| `SurveyFile` | `file_id` | UUID | Không | FK `File.id` | Bản ghi tệp vật lý. |
| `SurveyFile` | `file_type` | ENUM | Không |  | `VIDEO`, `SRT`, `PHOTO`, `OTHER`. |
| `SurveyFile` | `capture_started_at` | TIMESTAMPTZ | Có |  | Thời điểm bắt đầu nội dung. |
| `SurveyFile` | `capture_ended_at` | TIMESTAMPTZ | Có |  | Thời điểm kết thúc nội dung. |
| `SurveyFile` | `sync_status` | ENUM | Không |  | `LOCAL`, `QUEUED`, `UPLOADING`, `SERVER_CONFIRMED`, `INVALID`. |
| `SurveyFile` | `checksum` | CHECKSUM | Không |  | Kiểm tra toàn vẹn. |

#### `QualityCheck` — kiểm tra hai cấp

| Trường | Kiểu | Null | Khóa/Tham chiếu | Nguồn | Định nghĩa và ràng buộc |
|---|---|---:|---|---|---|
| `id` | UUID | Không | PK | DEC | Aggregate kết quả kiểm tra. |
| `scope` | ENUM | Không |  | DEC | `SURVEY_FILE` hoặc `SURVEY_DATASET`. |
| `execution_stage` | ENUM | Không |  | DEC | `CLIENT_PRECHECK` (Drone App, sơ bộ) hoặc `SERVER_VALIDATION` (Backend, chính thức). |
| `survey_file_id` | UUID | Có | FK `SurveyFile.id` | DEC | Bắt buộc khi scope file; phải null khi dataset. |
| `survey_data_version_id` | UUID | Có | FK `SurveyDataVersion.id` | DEC | Bắt buộc khi scope dataset; phải null khi file. |
| `check_type` | ENUM | Không |  | SRC | `FORMAT`, `GEOLOCATION`, `TIME_SYNC`, `CLARITY`, `LIGHTING`, `COVERAGE`, `OVERLAP`, `COMPLETENESS`, `OTHER`. |
| `status` | ENUM | Không |  | SRC | `PENDING`, `PASSED`, `FAILED`, `WARNING`. |
| `measured_value` | JSONB | Có |  | PROP | Giá trị đo/chi tiết máy kiểm tra. |
| `threshold` | JSONB | Có |  | PROP | Ngưỡng áp dụng. |
| `message` | TEXT | Có |  | SRC | Mô tả kết quả/lỗi. |
| `checked_at` | TIMESTAMPTZ | Không |  | SRC | Thời điểm kiểm tra. |
| `checked_by` | ENUM | Không |  | DEC | `DRONE_APP` hoặc `BACKEND`; PM không phải tác nhân kiểm tra kỹ thuật. |
| `initiated_by_user_id` | UUID | Có | FK `User.id` | PROP | Drone Operator kích hoạt precheck; null khi Backend chạy tự động. |

DB phải enforce đúng một FK đích: `(scope = SURVEY_FILE AND survey_file_id IS NOT NULL AND survey_data_version_id IS NULL)` hoặc ngược lại. Kiểm tra dataset neo vào `SurveyDataVersion`, không lưu thêm `survey_id` trên QualityCheck. `CLIENT_PRECHECK` không được dùng để chuyển version sang `SERVER_CONFIRMED`; chỉ `SERVER_VALIDATION` do `BACKEND` thực hiện có hiệu lực xác nhận/chặn xử lý.

#### `SurveyDataVersion`

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Phiên bản gói dữ liệu khảo sát. |
| `survey_id` | UUID | Không | FK `Survey.id` | Survey nguồn. |
| `version_no` | INTEGER | Không | UQ `(survey_id, version_no)` | Số version. |
| `status` | ENUM | Không |  | `DRAFT`, `UPLOADING`, `SERVER_CONFIRMED`, `INVALID`, `SUPERSEDED`. |
| `integrity_status` | ENUM | Không |  | `PENDING`, `PASSED`, `FAILED`. |
| `confirmed_at` | TIMESTAMPTZ | Có |  | Chỉ set khi server xác nhận đủ tệp/checksum. |
| `confirmed_by` | ENUM | Có |  | Chỉ `BACKEND`; Drone Operator/PM không tự xác nhận version. |
| `source_manifest` | JSONB | Không |  | Danh sách file/checksum tạo version. |

#### `SupplementarySurveyRequest` — aggregate độc lập

| Trường | Kiểu | Null | Khóa/Tham chiếu | Nguồn | Định nghĩa |
|---|---|---:|---|---|---|
| `id` | UUID | Không | PK | DEC | Định danh lượt yêu cầu bổ sung. |
| `survey_id` | UUID | Không | FK `Survey.id` | DEC | Khảo sát phát sinh yêu cầu; là context, không ownership. |
| `survey_request_id` | UUID | Có | FK `SurveyRequest.id` | DEC | Yêu cầu gốc nếu có. |
| `requested_by_user_id` | UUID | Không | FK `User.id` | SRC | Người/PM yêu cầu. |
| `reason` | TEXT | Không |  | SRC | Lý do phải bay bổ sung. |
| `requested_scope` | JSONB | Không |  | SRC | Vùng/phạm vi cần bổ sung. |
| `round_no` | INTEGER | Không | UQ `(survey_id, round_no)` | DEC | Số lượt bổ sung; tăng dần. |
| `status` | ENUM | Không |  | SRC | `REQUESTED`, `APPROVED`, `ASSIGNED`, `IN_PROGRESS`, `SUBMITTED`, `REJECTED`, `CANCELLED`. |
| `approved_by_user_id` | UUID | Có | FK `User.id` | SRC | Người duyệt. |
| `approved_at` | TIMESTAMPTZ | Có |  | SRC | Thời điểm duyệt. |
| `source_preservation_note` | TEXT | Có |  | SRC | Cách giữ dữ liệu cũ/nguồn gốc. |

Mọi lượt bổ sung giữ liên kết tới Survey/context và không xóa/ghi đè SurveyFile hoặc SurveyDataVersion cũ.

#### Đo đạc thực tế sản phẩm và Research Validation

`FieldInspectionTask` và `FieldInspectionAssignment` quản lý nhánh kiểm tra trực tiếp hoặc đo vật lý bắt buộc theo loại lỗi/quy tắc đo. PM có thể kết luận từ bằng chứng drone đủ tin cậy; không buộc mọi lỗi có task thực địa. `FieldInspectionSession` và `GroundTruthMeasurement` được dùng chung cho xác minh lỗi và nghiên cứu; `purpose` cùng các ràng buộc FK phân tách hai mục đích. Dữ liệu nghiên cứu có thể nhập từ Excel/giấy nhưng phải có định danh và liên kết đầy đủ.

##### `FieldInspectionTask`

| Trường | Kiểu SQL Server | Null | Khóa/Tham chiếu | Nguồn | Định nghĩa |
|---|---|---:|---|---|---|
| `id` | `uniqueidentifier` | Không | PK | SRC/DEC | Nhiệm vụ PM giao Repair Crew kiểm tra IncidentCase hoặc đo Preliminary Defect; không cần tạo Survey giả. |
| `source_type` | ENUM | Không |  | PROP | INCIDENT_CASE hoặc DEFECT; đúng một FK nguồn tương ứng non-null. |
| `incident_case_id` | UUID | Có | FK `IncidentCase.id` | PROP | Nguồn phản ánh đã điều phối; bắt buộc khi source_type = INCIDENT_CASE. |
| `task_code` | `nvarchar(80)` | Không | UQ | DEC | Mã nhiệm vụ ổn định. |
| `project_id` | `uniqueidentifier` | Không | FK `Project.id` | SRC | Dự án của nhiệm vụ. |
| `defect_id` | `uniqueidentifier` | Có | FK `Defect.id` | PROP | Bắt buộc khi source_type = DEFECT; trỏ lỗi OPEN. Null khi nguồn INCIDENT_CASE. |
| `survey_id` | `uniqueidentifier` | Có | FK `Survey.id` | PROP | Chỉ điền khi có khảo sát nguồn thực; không bắt buộc cho nguồn phản ánh. |
| `road_section_version_id` | `uniqueidentifier` | Không | FK `RoadSectionVersion.id` | SRC | Phải khớp tuyến đã điều phối của IncidentCase hoặc Defect; chỉ giao task khi đã xác định project/tuyến. |
| `required_measurement_type` | `tinyint` | Có |  | PROP | Có khi quy tắc yêu cầu số đo vật lý; kiểm tra trực quan có thể null. |
| `measurement_scope` | `nvarchar(max)` | Không | `ISJSON = 1` | SRC | Vị trí/phạm vi và các điểm cần đo. |
| `instructions` | `nvarchar(1000)` | Có |  | SRC | Dụng cụ, phương pháp hoặc hướng dẫn hiện trường. |
| `missing_information` | `nvarchar(1000)` | Có |  | SRC | Thông tin PM cần xác minh thêm. |
| `due_at` | `datetimeoffset(7)` | Không |  | SRC | Hạn hoàn tất nhiệm vụ. |
| `status` | `tinyint` | Không |  | SRC | `NEW_ASSIGNED`, `ACCEPTED`, `REJECTED`, `IN_PROGRESS`, `SUPPLEMENT_REQUIRED`, `SUBMITTED`, `COMPLETED`. |
| `assigned_by_user_id` | `uniqueidentifier` | Không | FK `User.id` | SRC | PM tạo/giao nhiệm vụ. |
| `review_decision` | `tinyint` | Có |  | SRC/DEC | `DEFECT_CONFIRMED`, `NO_DEFECT`; chỉ có khi `COMPLETED`. |
| `reviewed_by_user_id` | `uniqueidentifier` | Có | FK `User.id` | SRC | PM đánh giá kết quả. |
| `reviewed_at` | `datetimeoffset(7)` | Có |  | SRC | Thời điểm đánh giá cuối. |
| `review_reason` | `nvarchar(1000)` | Có |  | SRC | Bắt buộc khi `NO_DEFECT`; nhận xét khi xác nhận. |

##### `FieldInspectionAssignment`

| Trường | Kiểu SQL Server | Null | Khóa/Tham chiếu | Nguồn | Định nghĩa |
|---|---|---:|---|---|---|
| `id` | `uniqueidentifier` | Không | PK | DEC | Một lượt giao/bàn giao nhiệm vụ đo. |
| `field_inspection_task_id` | `uniqueidentifier` | Không | FK `FieldInspectionTask.id` | SRC | Nhiệm vụ được giao. |
| `assigned_to_user_id` | `uniqueidentifier` | Không | FK `User.id` | SRC | Đội trưởng Repair Crew nhận việc. |
| `assigned_by_user_id` | `uniqueidentifier` | Không | FK `User.id` | SRC | PM giao hoặc điều chuyển. |
| `assigned_at` | `datetimeoffset(7)` | Không |  | SRC | Thời điểm giao. |
| `ended_at` | `datetimeoffset(7)` | Có |  | SRC | Thời điểm lượt giao hết hiệu lực. |
| `status` | `tinyint` | Không |  | SRC | `ACTIVE`, `REJECTED`, `ENDED`. |
| `reason` | `nvarchar(1000)` | Có |  | SRC | Bắt buộc khi từ chối hoặc điều chuyển. |

Mỗi task chỉ có tối đa một assignment `ACTIVE`. Repair Crew chỉ được chuyển assignment sang `REJECTED` trước khi task được nhận; sau khi nhận, PM kết thúc assignment cũ và tạo assignment mới.

##### `FieldInspectionSession`

| Trường | Kiểu SQL Server | Null | Khóa/Tham chiếu | Nguồn | Định nghĩa |
|---|---|---:|---|---|---|
| `id` | `uniqueidentifier` | Không | PK | SRC/DEC | Định danh một phiên đo thực địa. |
| `purpose` | `tinyint` | Không |  | SRC/DEC | `DEFECT_VERIFICATION` hoặc `RESEARCH_VALIDATION`. |
| `field_inspection_task_id` | `uniqueidentifier` | Có | FK `FieldInspectionTask.id` | SRC/DEC | Bắt buộc với `DEFECT_VERIFICATION`; phải null với `RESEARCH_VALIDATION`. |
| `project_id` | `uniqueidentifier` | Không | FK `Project.id` | SRC/Research | Dự án. |
| `road_section_version_id` | `uniqueidentifier` | Không | FK `RoadSectionVersion.id` | SRC/Research | Hình học tại thời điểm đo. |
| `survey_id` | `uniqueidentifier` | Có | FK `Survey.id` | SRC/Research | Theo Survey nguồn thật của task; nullable cho kiểm tra trực tiếp từ IncidentCase và nghiên cứu. |
| `session_code` | `nvarchar(80)` | Không | UQ | SRC/Research | Mã phiên/đợt đo. |
| `inspector_user_id` | `uniqueidentifier` | Có | FK `User.id` | SRC/Research | Bắt buộc là Repair Crew đang được giao khi xác minh; có thể null khi import nghiên cứu. |
| `inspector_name` | `nvarchar(200)` | Không |  | SRC/Research | Tên người đo tại thời điểm thực hiện. |
| `conducted_at` | `datetimeoffset(7)` | Không |  | SRC/Research | Thời điểm đo. |
| `weather_condition` | `nvarchar(100)` | Có |  | SRC/Research | Điều kiện khô/mưa và bối cảnh hiện trường. |
| `method` | `nvarchar(200)` | Không |  | SRC/Research | Quy trình/thước đo sử dụng. |
| `status` | `tinyint` | Không |  | SRC/Research | `DRAFT`, `COMPLETED`, `IMPORTED`, `LOCKED`. |
| `evidence_file_id` | `uniqueidentifier` | Có | FK `File.id` | SRC/Research | Biên bản/ảnh tổng của phiên. |

##### `GroundTruthMeasurement`

| Trường | Kiểu SQL Server | Null | Khóa/Tham chiếu | Nguồn | Định nghĩa |
|---|---|---:|---|---|---|
| `id` | `uniqueidentifier` | Không | PK | SRC/Research | Định danh phép đo vật lý. |
| `field_inspection_session_id` | `uniqueidentifier` | Không | FK `FieldInspectionSession.id` | SRC/Research | Phiên đo. |
| `sample_id` | `nvarchar(100)` | Không | UQ trong session | SRC/Research | Mã mẫu duy nhất, dùng để ghép paired data. |
| `road_section_version_id` | `uniqueidentifier` | Không | FK `RoadSectionVersion.id` | SRC/Research | Đoạn đường tương ứng. |
| `survey_id` | `uniqueidentifier` | Có | FK `Survey.id` | SRC/Research | Survey dùng đối chiếu. |
| `defect_id` | `uniqueidentifier` | Có | FK `Defect.id` | SRC/Research | Bắt buộc với task nguồn DEFECT, trỏ đúng lỗi nguồn; nullable khi task nguồn INCIDENT_CASE chưa có lỗi và khi nghiên cứu. |
| `measurement_type` | `tinyint` | Không |  | SRC/Research | `DEPRESSION_DEPTH`, `SLAB_FAULTING_HEIGHT`, `SHOULDER_EROSION_EXTENT`. |
| `value` | `decimal(19,6)` | Không |  | SRC/Research | Giá trị đo gốc, không làm tròn mất độ chính xác. |
| `unit` | `nvarchar(20)` | Không |  | SRC/Research | Đơn vị, khuyến nghị `mm` cho độ sâu/chiều cao. |
| `location` | `geography` | Không | SRID 4326 | SRC/Research | Tọa độ điểm đo ngoài hiện trường. |
| `instrument_name` | `nvarchar(150)` | Không |  | SRC/Research | Tên dụng cụ, ví dụ straightedge/depth gauge. |
| `instrument_reference` | `nvarchar(150)` | Có |  | SRC/Research | Serial/calibration reference nếu có. |
| `measurement_method` | `nvarchar(500)` | Không |  | SRC/Research | Cách đặt thước, điểm chuẩn và quy trình đo. |
| `measured_by` | `nvarchar(200)` | Không |  | SRC/Research | Người thực hiện thực tế. |
| `measured_at` | `datetimeoffset(7)` | Không |  | SRC/Research | Thời điểm phép đo. |
| `evidence_file_id` | `uniqueidentifier` | Có | FK `File.id` | SRC/Research | Ảnh/biên bản chứng minh; nếu thiếu phải có lý do trong `notes`. |
| `notes` | `nvarchar(max)` | Có |  | SRC/Research | Ghi chú, lý do thiếu bằng chứng, outlier hoặc điều kiện đặc biệt. |

##### `DerivedMeasurement`

| Trường | Kiểu SQL Server | Null | Khóa/Tham chiếu | Nguồn | Định nghĩa |
|---|---|---:|---|---|---|
| `id` | `uniqueidentifier` | Không | PK | Research | Định danh số đo từ hệ thống. |
| `survey_data_version_id` | `uniqueidentifier` | Không | FK `SurveyDataVersion.id` | Research | Phiên bản dữ liệu dùng tính toán. |
| `road_section_version_id` | `uniqueidentifier` | Không | FK `RoadSectionVersion.id` | Research | Hình học tương ứng. |
| `defect_id` | `uniqueidentifier` | Có | FK `Defect.id` | Research | Lỗi được ghép nếu có. |
| `sample_id` | `nvarchar(100)` | Không | Logic ref | Research | Mã sample phải khớp `GroundTruthMeasurement.sample_id`. |
| `measurement_type` | `tinyint` | Không |  | Research | Cùng miền giá trị với ground truth. |
| `value` | `decimal(19,6)` | Không |  | Research | Số đo do DSM/surface model/pipeline tạo. |
| `unit` | `nvarchar(20)` | Không |  | Research | Đơn vị chuẩn hóa. |
| `uncertainty_estimate` | `decimal(19,6)` | Có |  | Research | Ước lượng uncertainty của phép đo nếu pipeline cung cấp. |
| `source_type` | `tinyint` | Không |  | Research | `SURFACE_MODEL`, `DSM`, `MANUAL_DERIVED`, `OTHER`. |
| `algorithm_version` | `nvarchar(100)` | Có |  | Research | Phiên bản pipeline/model. |
| `computed_at` | `datetimeoffset(7)` | Không |  | Research | Thời điểm tính. |
| `status` | `tinyint` | Không |  | Research | `DRAFT`, `PUBLISHED`, `SUPERSEDED`. |

##### `MeasurementValidationRun` và `MeasurementValidationSample`

| Entity | Trường | Kiểu SQL Server | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---|---:|---|---|
| `MeasurementValidationRun` | `id` | `uniqueidentifier` | Không | PK | Một lần phân tích validation. |
| `MeasurementValidationRun` | `run_code` | `nvarchar(100)` | Không | UQ | Mã thí nghiệm/lần chạy. |
| `MeasurementValidationRun` | `measurement_type` | `tinyint` | Không |  | Loại phép đo được đánh giá. |
| `MeasurementValidationRun` | `method_name` | `nvarchar(200)` | Không |  | Phương pháp/model. |
| `MeasurementValidationRun` | `algorithm_version` | `nvarchar(100)` | Có |  | Version pipeline. |
| `MeasurementValidationRun` | `sample_count` | `int` | Không |  | Số mẫu hợp lệ. |
| `MeasurementValidationRun` | `bias` | `decimal(19,6)` | Có |  | Sai số trung bình có dấu. |
| `MeasurementValidationRun` | `mae` | `decimal(19,6)` | Có |  | Mean Absolute Error. |
| `MeasurementValidationRun` | `rmse` | `decimal(19,6)` | Có |  | Root Mean Square Error. |
| `MeasurementValidationRun` | `uncertainty_value` | `decimal(19,6)` | Có |  | Giá trị uncertainty được báo cáo. |
| `MeasurementValidationRun` | `uncertainty_method` | `nvarchar(500)` | Có |  | Phương pháp/giả định tính uncertainty. |
| `MeasurementValidationRun` | `status` | `tinyint` | Không |  | `DRAFT`, `COMPLETED`, `PUBLISHED`. |
| `MeasurementValidationSample` | `id` | `uniqueidentifier` | Không | PK | Một cặp mẫu trong run. |
| `MeasurementValidationSample` | `validation_run_id` | `uniqueidentifier` | Không | FK `MeasurementValidationRun.id` | Run sở hữu. |
| `MeasurementValidationSample` | `ground_truth_measurement_id` | `uniqueidentifier` | Không | FK `GroundTruthMeasurement.id` | Số đo vật lý. |
| `MeasurementValidationSample` | `derived_measurement_id` | `uniqueidentifier` | Không | FK `DerivedMeasurement.id` | Số đo drone/surface model. |
| `MeasurementValidationSample` | `signed_error` | `decimal(19,6)` | Không |  | `derived - ground_truth`. |
| `MeasurementValidationSample` | `absolute_error` | `decimal(19,6)` | Không |  | Trị tuyệt đối sai số. |
| `MeasurementValidationSample` | `inclusion_status` | `tinyint` | Không |  | `INCLUDED`, `EXCLUDED`, `OUTLIER`. |
| `MeasurementValidationSample` | `exclusion_reason` | `nvarchar(500)` | Có |  | Bắt buộc khi loại mẫu. |

Các entity research này là immutable/append-only sau khi khóa phiên hoặc công bố kết quả; không tự tạo Defect và không kết luận thuộc/ngoài Warranty.

### 3.4 Processing và AI

#### `ProcessingBlock`, `ProcessingJob`, `ProcessingAttempt`

| Entity | Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---|---:|---|---|
| `ProcessingBlock` | `id` | UUID | Không | PK | Khối backend chia từ một data version. |
| `ProcessingBlock` | `survey_data_version_id` | UUID | Không | FK `SurveyDataVersion.id` | Dataset đã xác nhận; block không trộn dataset. |
| `ProcessingBlock` | `block_no` | INTEGER | Không | UQ trong version | Số thứ tự khối. |
| `ProcessingBlock` | `segment_set_id` | UUID | Không | FK `RoadSegmentSet.id` | Bộ segment snapshot lúc tạo block. |
| `ProcessingBlock` | `road_segment_id` | UUID | Không | FK `RoadSegment.id` | Segment chính; context overlap lưu riêng trong manifest. |
| `ProcessingBlock` | `target_band` | ENUM | Không |  | SURFACE, LEFT_EDGE, RIGHT_EDGE. |
| `ProcessingBlock` | `range_metadata` | JSONB | Không |  | Primary/context offsets, interval IDs, observed footprint và quality; context overlap có thể dùng chung frame lân cận. |
| `ProcessingJob` | `id` | UUID | Không | PK | Tác vụ xử lý AI cho một block. |
| `ProcessingJob` | `processing_block_id` | UUID | Không | FK `ProcessingBlock.id` | Block nguồn. |
| `ProcessingJob` | `model_version_id` | UUID | Không | FK `AIModelVersion.id` | Model chạy tác vụ; đổi model tạo job mới. |
| `ProcessingJob` | `processing_input_manifest_id` | UUID | Có | FK `ProcessingInputManifest.id`, UQ | Manifest immutable; phải tồn tại trước dispatch, tránh payload thay đổi giữa retry. |
| `ProcessingJob` | `idempotency_key` | VARCHAR(160) | Không | UQ fingerprint | BackendJobId + input/model/config; payload khác cùng key bị từ chối. |
| `ProcessingJob` | `context_overlap_metadata` | JSONB | Có |  | Phạm vi context xử lý ngoài segment chính, nguồn interval/không lặp frame. |
| `ProcessingJob` | `result_provenance` | JSONB | Có |  | Input checksum, attempt, AI job ID, output checksum, model/config và mapping về segment/band; immutable mỗi result. |
| `ProcessingJob` | `deduplication_key` | VARCHAR(160) | Có | UQ theo input/detection | Khóa chống job/detection lặp khi retry hoặc nhận result muộn. |
| `ProcessingJob` | `status` | ENUM | Không |  | `QUEUED`, `RUNNING`, `RETRYABLE_FAILURE`, `DATA_FAILURE`, `COMPLETED`, `CANCELLED`. |
| `ProcessingJob` | `started_at` | TIMESTAMPTZ | Có |  | Bắt đầu xử lý. |
| `ProcessingJob` | `completed_at` | TIMESTAMPTZ | Có |  | Kết thúc. |
| `ProcessingJob` | `error_code` | VARCHAR(80) | Có |  | Mã lỗi chuẩn hóa. |
| `ProcessingJob` | `error_message` | TEXT | Có |  | Chi tiết lỗi không chứa secret. |
| `ProcessingAttempt` | `id` | UUID | Không | PK | Một lần thử; append-only. |
| `ProcessingAttempt` | `processing_job_id` | UUID | Không | FK `ProcessingJob.id` | Job nguồn. |
| `ProcessingAttempt` | `attempt_no` | INTEGER | Không | UQ trong job | Số lần thử. |
| `ProcessingAttempt` | `started_at` | TIMESTAMPTZ | Không |  | Bắt đầu. |
| `ProcessingAttempt` | `ended_at` | TIMESTAMPTZ | Có |  | Kết thúc. |
| `ProcessingAttempt` | `error_type` | ENUM | Có |  | `INFRASTRUCTURE`, `DATA`, `NONE`. Chỉ lỗi hạ tầng được retry. |
| `ProcessingAttempt` | `worker_reference` | VARCHAR(120) | Có |  | ID worker/queue. |

#### `AIModelVersion`

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Phiên bản model. |
| `model_name` | VARCHAR(120) | Không |  | Tên model. |
| `version_label` | VARCHAR(80) | Không | UQ | Nhãn version. |
| `artifact_uri` | URI | Không |  | Vị trí artifact. |
| `metrics` | JSONB | Có |  | Chỉ số đánh giá. |
| `operating_thresholds` | JSONB | Có |  | Ngưỡng vận hành. |
| `status` | ENUM | Không |  | `DRAFT`, `RELEASED`, `RETIRED`. |
| `released_at` | TIMESTAMPTZ | Có |  | Thời điểm phát hành. |
| `released_by_user_id` | UUID | Có | FK `User.id` | Người phát hành. |

#### `AIDetection`

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Kết quả AI thô, immutable. |
| `processing_job_id` | UUID | Không | FK `ProcessingJob.id` | Job tạo kết quả. |
| `model_version_id` | UUID | Không | FK `AIModelVersion.id` | Model bất biến đã dùng. |
| `road_section_version_id` | UUID | Có | FK `RoadSectionVersion.id` | Hình học tham chiếu. |
| `geometry` | GEOMETRY(Point/Polygon) | Có | SPATIAL | Vị trí lỗi chỉ khi có căn cứ; null/unknown nếu không định vị được. |
| `aircraft_location` | GEOMETRY(Point) | Có | SPATIAL WGS84 | GPS thiết bị tại timestamp, không phải vị trí lỗi. |
| `projected_station_m` | DECIMAL(14,3) | Có |  | Lý trình chiếu lên tuyến, method/confidence lưu riêng. |
| `defect_location_method` | ENUM | Không |  | UNKNOWN, PROJECTED_STATION, OBSERVED_FOOTPRINT, PM_CONFIRMED; không tự lấy aircraft GPS. |
| `location_uncertainty_m` | DECIMAL(14,3) | Có |  | Sai số/độ tin cậy khi biết. |
| `camera_pose_json` | JSONB | Có |  | Pose/calibration/footprint nếu có; null nghĩa unknown. |
| `defect_type_code` | VARCHAR(80) | Có | FK `DefectType.code` | Loại lỗi dự kiến. |
| `confidence` | DECIMAL(6,5) | Không | 0..1 | Độ tin cậy AI. |
| `estimated_width` | DECIMAL(12,3) | Có |  | Ước lượng 2D. |
| `estimated_length` | DECIMAL(12,3) | Có |  | Ước lượng 2D. |
| `raw_payload` | JSONB | Không |  | Payload gốc; không chỉnh sửa. |

#### `Defect`, `DefectVerificationLog`, `DefectMergeDecision`, `DefectMatch`

| Entity | Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---|---:|---|---|
| `Defect` | `id` | UUID | Không | PK | Lỗi nghiệp vụ; `OPEN` là Preliminary Defect, `VERIFIED` là hư hỏng được PM xác nhận trước sửa (DefectVerified), từ bằng chứng drone hoặc thực địa đạt điều kiện; khác IncidentCase Verified sau sửa. |
| `Defect` | `project_id` | UUID | Không | FK `Project.id` | Dự án. |
| `Defect` | `road_section_version_id` | UUID | Không | FK `RoadSectionVersion.id` | Version hình học tại kỳ phát hiện. |
| `Defect` | `source_ai_detection_id` | UUID | Có | FK `AIDetection.id` | Phát hiện AI nguồn nếu có. |
| `Defect` | `defect_type_code` | VARCHAR(80) | Không | FK `DefectType.code` | Loại lỗi. |
| `Defect` | `cause_category_code` | VARCHAR(80) | Có | FK `CauseCategory.code` | Nhóm nguyên nhân. |
| `Defect` | `severity` | ENUM | Không |  | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. |
| `Defect` | `status` | ENUM | Không |  | `OPEN`, `VERIFIED`, `REJECTED`, `RESOLVED`; `VERIFIED` mang nghĩa **DefectVerified trước sửa** và không phải IncidentCase Verified sau sửa. |
| `Defect` | `geometry` | GEOMETRY(Point/Line/Polygon) | Có | SPATIAL | Vị trí lỗi có căn cứ; unknown/ước lượng không được giả bằng GPS drone. |
| `Defect` | `reported_at` | TIMESTAMPTZ | Không |  | Thời điểm ghi nhận. |
| `DefectVerificationLog` | `id` | UUID | Không | PK | Lịch sử quyết định PM, append-only. |
| `DefectVerificationLog` | `defect_id` | UUID | Có | FK `Defect.id` | Đích khi log quyết định trên Preliminary Defect/hư hỏng. |
| `DefectVerificationLog` | `ai_detection_id` | UUID | Có | FK `AIDetection.id` | Đích khi PM loại/giữ chờ một phát hiện AI trước khi tạo Defect. |
| `DefectVerificationLog` | `source_type` | ENUM | Không |  | DRONE_REVIEW hoặc FIELD_INSPECTION; nguồn quyết định. |
| `DefectVerificationLog` | `survey_data_version_id` | UUID | Có | FK `SurveyDataVersion.id` | Bắt buộc khi DRONE_REVIEW; version đã xác nhận. |
| `DefectVerificationLog` | `evidence_snapshot` | JSONB | Không |  | File/checksum, frame/time hoặc session/measurement IDs và kết luận PM; chỉ nguồn trong phạm vi. |
| `DefectVerificationLog` | `action` | ENUM | Không |  | `PRELIMINARY_KEEP`, `ADJUST`, `CONFIRM`, `REJECT`, `MERGE`. |
| `DefectVerificationLog` | `before_snapshot` | JSONB | Có |  | Giá trị trước quyết định. |
| `DefectVerificationLog` | `after_snapshot` | JSONB | Có |  | Giá trị sau quyết định. |
| `DefectVerificationLog` | `severity_rule_version_id` | UUID | Có | FK `SeverityRuleVersion.id` | Rule version tại thời điểm tính severity. |
| `DefectVerificationLog` | `field_inspection_task_id` | UUID | Có | FK `FieldInspectionTask.id` | Bắt buộc khi source_type = FIELD_INSPECTION; có thể null với DRONE_REVIEW đủ bằng chứng. CONFIRM/REJECT đều cần nguồn và evidence_snapshot. |
| `DefectVerificationLog` | `verified_by_user_id` | UUID | Không | FK `User.id` | PM thực hiện. |
| `DefectVerificationLog` | `reason` | TEXT | Không |  | Lý do bắt buộc. |
| `DefectMergeDecision` | `id` | UUID | Không | PK | Quyết định gộp/giữ riêng. |
| `DefectMergeDecision` | `source_defect_id` | UUID | Không | FK `Defect.id` | Lỗi nguồn. |
| `DefectMergeDecision` | `target_defect_id` | UUID | Có | FK `Defect.id` | Lỗi đích khi gộp. |
| `DefectMergeDecision` | `decision` | ENUM | Không |  | `MERGE`, `KEEP_SEPARATE`. |
| `DefectMergeDecision` | `decided_by_user_id` | UUID | Không | FK `User.id` | Người quyết định. |
| `DefectMatch` | `id` | UUID | Không | PK | Liên kết đối sánh hai kỳ. |
| `DefectMatch` | `defect_id_a` | UUID | Không | FK `Defect.id` | Lỗi kỳ A. |
| `DefectMatch` | `defect_id_b` | UUID | Không | FK `Defect.id` | Lỗi kỳ B. |
| `DefectMatch` | `match_confidence` | DECIMAL(6,5) | Không | 0..1 | Độ tin cậy đối sánh. |
| `DefectMatch` | `match_method` | ENUM | Không |  | `AI`, `RULE`, `MANUAL`. |
| `DefectMatch` | `reviewed_by_user_id` | UUID | Có | FK `User.id` | Người duyệt đối sánh. |

### 3.5 Danh mục và huấn luyện AI

| Entity | Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---|---:|---|---|
| `DefectType` | `code` | VARCHAR(80) | Không | PK | Mã loại lỗi. |
| `DefectType` | `name` | VARCHAR(150) | Không |  | Tên loại lỗi. |
| `DefectType` | `description` | TEXT | Có |  | Định nghĩa. |
| `DefectType` | `is_active` | BOOLEAN | Không |  | Ngừng dùng không xóa lịch sử. |
| `CauseCategory` | `code` | VARCHAR(80) | Không | PK | Mã nhóm nguyên nhân. |
| `CauseCategory` | `name` | VARCHAR(150) | Không |  | Tên nhóm. |
| `CauseCategory` | `is_active` | BOOLEAN | Không |  | Trạng thái sử dụng. |
| `SeverityRuleVersion` | `id` | UUID | Không | PK | Phiên bản rule phân mức. |
| `SeverityRuleVersion` | `standard_code` | VARCHAR(80) | Không |  | Chuẩn áp dụng. |
| `SeverityRuleVersion` | `road_type_code` | VARCHAR(80) | Không |  | Loại mặt đường. |
| `SeverityRuleVersion` | `version_no` | INTEGER | Không | UQ theo scope | Số phiên bản. |
| `SeverityRuleVersion` | `rule_definition` | JSONB | Không |  | Công thức/ngưỡng. |
| `SeverityRuleVersion` | `effective_from` | DATE | Không |  | Ngày hiệu lực. |
| `SeverityRuleVersion` | `effective_to` | DATE | Có |  | Ngày hết hiệu lực. |
| `TrainingLabelApproval` | `id` | UUID | Không | PK | Quyết định duyệt nhãn. |
| `TrainingLabelApproval` | `defect_id` | UUID | Không | FK `Defect.id` | Lỗi/nhãn được duyệt. |
| `TrainingLabelApproval` | `label_payload` | JSONB | Không |  | Nhãn dùng huấn luyện. |
| `TrainingLabelApproval` | `status` | ENUM | Không |  | `PENDING`, `APPROVED`, `REJECTED`. |
| `TrainingLabelApproval` | `approved_by_user_id` | UUID | Có | FK `User.id` | PM duyệt. |
| `TrainingLabelApproval` | `approved_at` | TIMESTAMPTZ | Có |  | Thời điểm duyệt. |
| `TrainingDatasetExport` | `id` | UUID | Không | PK | Lần xuất dataset huấn luyện. |
| `TrainingDatasetExport` | `requested_by_user_id` | UUID | Không | FK `User.id` | Người yêu cầu. |
| `TrainingDatasetExport` | `filter_snapshot` | JSONB | Không |  | Bộ lọc tại thời điểm xuất. |
| `TrainingDatasetExport` | `file_id` | UUID | Có | FK `File.id` | File xuất. |
| `TrainingDatasetExport` | `status` | ENUM | Không |  | `REQUESTED`, `GENERATING`, `COMPLETED`, `FAILED`. |

### 3.6 Repair

| Entity | Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---|---:|---|---|
| `RepairBatch` | `id` | UUID | Không | PK | Đợt sửa logic. |
| `RepairBatch` | `project_id` | UUID | Không | FK `Project.id` | Dự án. |
| `RepairBatch` | `current_version_id` | UUID | Có | FK `RepairBatchVersion.id` | Version hiện hành. |
| `RepairBatch` | `status` | ENUM | Không |  | Trạng thái tổng hợp đợt. |
| `RepairBatchVersion` | `id` | UUID | Không | PK | Version trình duyệt, immutable sau khi trình. |
| `RepairBatchVersion` | `repair_batch_id` | UUID | Không | FK `RepairBatch.id` | Đợt gốc. |
| `RepairBatchVersion` | `version_no` | INTEGER | Không | UQ trong batch | Số version. |
| `RepairBatchVersion` | `status` | ENUM | Không |  | `DRAFT`, `PENDING_APPROVAL`, `REVISION_REQUIRED`, `APPROVED`, `REJECTED`. |
| `RepairBatchVersion` | `estimated_total_cost` | DECIMAL(19,2) | Không |  | Tổng dự toán snapshot bằng tổng `RepairItem.estimated_cost` trong version, tính bằng VND; không nhập thủ công. |
| `RepairBatchVersion` | `submitted_at` | TIMESTAMPTZ | Có |  | Thời điểm trình. |
| `RepairBatchVersion` | `approved_at` | TIMESTAMPTZ | Có |  | Thời điểm duyệt. |
| `RepairItem` | `id` | UUID | Không | PK | Lỗi trong một version; version mới copy item mới. |
| `RepairItem` | `repair_batch_version_id` | UUID | Không | FK `RepairBatchVersion.id` | Version sở hữu. |
| `RepairItem` | `defect_id` | UUID | Không | FK `Defect.id` | Chỉ Defect VERIFIED được PM xác nhận; task COMPLETED/DEFECT_CONFIRMED bắt buộc khi quy tắc yêu cầu đo vật lý. |
| `RepairItem` | `repair_method_summary` | TEXT | Không |  | Phương án sửa tổng quát PM nhập; không phải quy trình thi công/BOM. |
| `RepairItem` | `estimated_cost` | DECIMAL(19,2) | Không |  | Chi phí dự toán, tính bằng VND. |
| `RepairItem` | `status` | ENUM | Không |  | Trạng thái theo lỗi. |
| `RepairApprovalDecision` | `id` | UUID | Không | PK | Quyết định duyệt/trả theo item. |
| `RepairApprovalDecision` | `repair_batch_version_id` | UUID | Không | FK `RepairBatchVersion.id` | Version được xét. |
| `RepairApprovalDecision` | `repair_item_id` | UUID | Không | FK `RepairItem.id` | Item được xét. |
| `RepairApprovalDecision` | `decision` | ENUM | Không |  | `APPROVED`, `REJECTED`, `REVISION_REQUIRED`. |
| `RepairApprovalDecision` | `decided_by_user_id` | UUID | Không | FK `User.id` | Supervisor. |
| `RepairApprovalDecision` | `reason` | TEXT | Có |  | Bắt buộc khi trả. |
| `RepairAssignment` | `id` | UUID | Không | PK | Phân công đội trưởng. |
| `RepairAssignment` | `repair_batch_version_id` | UUID | Không | FK `RepairBatchVersion.id` | Chỉ version APPROVED/current. |
| `RepairAssignment` | `crew_lead_user_id` | UUID | Không | FK `User.id` | Đội trưởng. |
| `RepairAssignment` | `assigned_by_user_id` | UUID | Không | FK `User.id` | PM phân công. |
| `RepairAssignment` | `assigned_at` | TIMESTAMPTZ | Không |  | Thời điểm giao. |
| `RepairAssignment` | `ended_at` | TIMESTAMPTZ | Có |  | Thời điểm bàn giao/kết thúc. |
| `RepairAssignment` | `handover_reason` | TEXT | Có |  | Bắt buộc khi đổi đội trưởng. |
| `RepairProgress` | `id` | UUID | Không | PK | Bản ghi tiến độ append-only. |
| `RepairProgress` | `repair_item_id` | UUID | Không | FK `RepairItem.id` | Lỗi đang thi công. |
| `RepairProgress` | `status` | ENUM | Không |  | `NOT_STARTED`, `IN_PROGRESS`, `SUBMITTED`, `REVISION_REQUIRED`, `COMPLETED`. |
| `RepairProgress` | `actual_cost` | DECIMAL(19,2) | Có |  | Chi phí thực tế, tính bằng VND. |
| `RepairProgress` | `recorded_by_user_id` | UUID | Không | FK `User.id` | Người ghi. |
| `RepairProgress` | `recorded_at` | TIMESTAMPTZ | Không |  | Thời điểm ghi. |
| `RepairEvidence` | `id` | UUID | Không | PK | Bằng chứng ảnh/tệp theo lỗi. |
| `RepairEvidence` | `repair_item_id` | UUID | Không | FK `RepairItem.id` | Lỗi được chứng minh. |
| `RepairEvidence` | `file_id` | UUID | Không | FK `File.id` | Tệp bằng chứng. |
| `RepairEvidence` | `evidence_stage` | ENUM | Không |  | `BEFORE`, `DURING`, `AFTER`. |
| `RepairEvidence` | `captured_at` | TIMESTAMPTZ | Không |  | Thời điểm chụp. |
| `RepairEvidence` | `location` | GEOMETRY(Point) | Có | SPATIAL | Vị trí chụp. |
| `RepairEvidence` | `note` | TEXT | Có |  | Ghi chú. |
| `UnplannedDefectReport` | `id` | UUID | Không | PK | Báo cáo lỗi ngoài phạm vi. |
| `UnplannedDefectReport` | `project_id` | UUID | Không | FK `Project.id` | Dự án. |
| `UnplannedDefectReport` | `repair_batch_id` | UUID | Có | FK `RepairBatch.id` | Đợt liên quan để tham chiếu, không tự thêm item. |
| `UnplannedDefectReport` | `reported_by_user_id` | UUID | Không | FK `User.id` | Người báo cáo. |
| `UnplannedDefectReport` | `description` | TEXT | Không |  | Mô tả lỗi phát sinh. |
| `UnplannedDefectReport` | `status` | ENUM | Không |  | `REPORTED`, `UNDER_REVIEW`, `ACCEPTED`, `REJECTED`. |
| `RepairInspectionResult` | `id` | UUID | Không | PK | Kết quả nghiệm thu theo item. |
| `RepairInspectionResult` | `repair_item_id` | UUID | Không | FK `RepairItem.id` | Item được kiểm tra. |
| `RepairInspectionResult` | `result` | ENUM | Không |  | `PASSED`, `FAILED`. |
| `RepairInspectionResult` | `inspected_by_user_id` | UUID | Không | FK `User.id` | PM/Supervisor. |
| `RepairInspectionResult` | `inspected_at` | TIMESTAMPTZ | Không |  | Thời điểm kiểm tra. |
| `RepairInspectionResult` | `reason` | TEXT | Có |  | Bắt buộc khi FAILED. |

Ràng buộc `UD-06` theo thiết kế mới: PM nhập `RepairItem.repair_method_summary` (phương án tổng quát) và `estimated_cost`; không quản lý BOM, vật liệu, khối lượng/đơn giá chi tiết hay giai đoạn thi công. `estimated_cost >= 0`, `actual_cost >= 0` khi có; `(repair_batch_version_id, defect_id)` là duy nhất. Backend tính và lưu `estimated_total_cost` khi tạo/trình version.

### 3.7 File, Evidence, Audit và Export

#### `File`

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Bản ghi metadata tệp. |
| `storage_uri` | URI | Không | UQ | Vị trí object storage. |
| `original_name` | VARCHAR(255) | Không |  | Tên tệp gốc. |
| `mime_type` | VARCHAR(120) | Không |  | MIME type. |
| `size_bytes` | INTEGER | Không |  | Kích thước. |
| `checksum` | CHECKSUM | Không |  | SHA-256. |
| `uploaded_by_user_id` | UUID | Có | FK `User.id` | Người tải lên. |
| `uploaded_at` | TIMESTAMPTZ | Không |  | Thời điểm tải. |
| `retention_until` | DATE | Có |  | Hạn lưu trữ tính theo chính sách. |

#### `Evidence`

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Bản ghi liên kết bằng chứng. |
| `file_id` | UUID | Không | FK `File.id` | Tệp vật lý. |
| `defect_id` | UUID | Có | FK `Defect.id` | Đích lỗi nếu có. |
| `repair_item_id` | UUID | Có | FK `RepairItem.id` | Đích item nếu có. |
| `handover_document_id` | UUID | Có | FK `HandoverDocument.id` | Đích hồ sơ bàn giao nếu có. |
| `evidence_type` | ENUM | Không |  | Loại bằng chứng. |
| `note` | TEXT | Có |  | Ghi chú. |

CHECK bắt buộc đúng một trong các FK nghiệp vụ đích là non-null; mở rộng thêm đích phải cập nhật constraint/schema.

#### `AuditLog` — event sink chung

| Trường | Kiểu | Null | Khóa/Tham chiếu | Nguồn | Định nghĩa |
|---|---|---:|---|---|---|
| `id` | UUID | Không | PK | SRC | Event audit append-only. |
| `actor_user_id` | UUID | Có | FK `User.id` | SRC | Người gây ra sự kiện; null nếu hệ thống. |
| `occurred_at` | TIMESTAMPTZ | Không |  | SRC | Thời điểm sự kiện. |
| `event_type` | VARCHAR(100) | Không |  | SRC | Tên domain event/operation. |
| `entity_type` | VARCHAR(100) | Không |  | SRC | Loại aggregate/entity đích. |
| `entity_id` | UUID | Không | Polymorphic | SRC | ID entity đích. |
| `before_snapshot` | JSONB | Có |  | SRC | Trạng thái trước. |
| `after_snapshot` | JSONB | Có |  | SRC | Trạng thái sau. |
| `reason` | TEXT | Có |  | SRC | Lý do/ghi chú. |
| `source` | VARCHAR(80) | Không |  | SRC | API, mobile, worker, admin... |
| `correlation_id` | UUID | Có |  | SRC | Truy vết request. |

`AuditLog` không thay thế `PasswordResetLog` hoặc `AccountStatusChangeLog`; không lưu secret.

#### `ReportExport`

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Lần xuất báo cáo. |
| `requested_by_user_id` | UUID | Không | FK `User.id` | Người xuất. |
| `project_id` | UUID | Có | FK `Project.id` | Phạm vi dự án. |
| `filter_snapshot` | JSONB | Không |  | Bộ lọc đã áp dụng. |
| `data_version_snapshot` | JSONB | Không |  | Version dữ liệu dùng để xuất. |
| `format` | ENUM | Không |  | `PDF`, `ZIP`, `CSV`, `OTHER`. |
| `status` | ENUM | Không |  | `REQUESTED`, `GENERATING`, `COMPLETED`, `FAILED`. |
| `file_id` | UUID | Có | FK `File.id` | Tệp kết quả. |
| `error_message` | TEXT | Có |  | Lỗi tạo tệp. |

### 3.8 Administration & Retention

| Entity | Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---|---:|---|---|
| `ReminderRule` | `id` | UUID | Không | PK | Cấu hình nhắc việc. |
| `ReminderRule` | `rule_type` | ENUM | Không |  | `SURVEY_DUE`, `WARRANTY_EXPIRY`. |
| `ReminderRule` | `days_before` | INTEGER | Không |  | Số ngày nhắc trước hạn. |
| `ReminderRule` | `is_active` | BOOLEAN | Không |  | Trạng thái cấu hình. |
| `ReminderRule` | `configured_by_user_id` | UUID | Không | FK `User.id` | Admin cấu hình. |
| `DataRetentionRequest` | `id` | UUID | Không | PK | Yêu cầu xóa dữ liệu hết hạn. |
| `DataRetentionRequest` | `scope_snapshot` | JSONB | Không |  | Phạm vi hồ sơ yêu cầu xóa. |
| `DataRetentionRequest` | `requested_by_user_id` | UUID | Không | FK `User.id` | PM lập yêu cầu. |
| `DataRetentionRequest` | `status` | ENUM | Không |  | `DRAFT`, `PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `EXECUTED`, `BLOCKED`. |
| `DataRetentionRequest` | `retention_basis` | TEXT | Không |  | Căn cứ hết hạn bảo hành + thời hạn lưu trữ. |
| `DataRetentionRequest` | `reviewed_by_user_id` | UUID | Có | FK `User.id` | Supervisor xem xét. |
| `DataRetentionRequest` | `review_reason` | TEXT | Có |  | Lý do duyệt/từ chối/block. |
| `LegalHold` | `id` | UUID | Không | PK | Lệnh giữ hồ sơ. |
| `LegalHold` | `scope_snapshot` | JSONB | Không |  | Phạm vi bị giữ. |
| `LegalHold` | `reason` | TEXT | Không |  | Căn cứ tranh chấp/pháp lý. |
| `LegalHold` | `status` | ENUM | Không |  | `ACTIVE`, `RELEASED`. |
| `LegalHold` | `placed_by_user_id` | UUID | Không | FK `User.id` | Người thiết lập. |
| `LegalHold` | `released_by_user_id` | UUID | Có | FK `User.id` | Người gỡ giữ. |
| `RetentionDeletionLog` | `id` | UUID | Không | PK | Biên bản xóa append-only. |
| `RetentionDeletionLog` | `retention_request_id` | UUID | Không | FK `DataRetentionRequest.id` | Yêu cầu được thực thi. |
| `RetentionDeletionLog` | `approved_by_user_id` | UUID | Không | FK `User.id` | Supervisor phê duyệt. |
| `RetentionDeletionLog` | `executed_at` | TIMESTAMPTZ | Không |  | Thời điểm xóa. |
| `RetentionDeletionLog` | `result` | ENUM | Không |  | `SUCCESS`, `PARTIAL`, `FAILED`. |
| `RetentionDeletionLog` | `deleted_scope_snapshot` | JSONB | Không |  | Phạm vi thực tế đã xóa. |
| `RetentionDeletionLog` | `error_message` | TEXT | Có |  | Lỗi nếu có. |

### 3.2a Tiếp nhận phản ánh và hồ sơ sự cố

#### `IncidentCase` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Hồ sơ được tạo khi gửi phản ánh; nhiều phản ánh có thể được PM liên kết cùng hồ sơ. |
| `project_id` | UUID | Có | FK `Project.id` | Null khi New chưa điều phối; phải có trước Assigned và giao tác nghiệp. |
| `road_section_version_id` | UUID | Có | FK `RoadSectionVersion.id` | Tuyến xác nhận khi điều phối; không tự gán sai tuyến. |
| `assigned_pm_user_id` | UUID | Có | FK `User.id` | PM phụ trách; bắt buộc từ Assigned. |
| `status` | ENUM | Không |  | NEW, ASSIGNED, OPEN, FIXED, RETEST, VERIFIED, CLOSED. |
| `closure_reason` | ENUM | Có |  | REPAIRED, NO_DEFECT, DUPLICATE, OUT_OF_SCOPE; bắt buộc khi Closed. |
| `closure_note` | TEXT | Có |  | Lý do PM nhập khi đóng không sửa; Supervisor đóng sau sửa đạt. |
| `related_case_id` | UUID | Có | FK `IncidentCase.id` | Hồ sơ chính khi trùng hoặc hồ sơ cũ khi tái phát; không tự trỏ chính nó. |
| `related_case_type` | ENUM | Có |  | DUPLICATE hoặc RECURRENCE, đi cùng related_case_id. |
| `closed_at` | TIMESTAMPTZ | Có |  | Thời điểm đóng. |
| `closed_by_user_id` | UUID | Có | FK `User.id` | PM đóng không sửa; Supervisor xác nhận đóng sau sửa. |

#### `IncidentReport` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Nguồn gửi gốc; không gộp xóa nội dung khi trùng. |
| `reporter_user_id` | UUID | Không | FK `User.id` | Reporter đăng nhập, quyền xem theo owner. |
| `incident_case_id` | UUID | Không | FK `IncidentCase.id` | Gửi tạo case New; nhiều report có thể liên kết case chính sau phân loại. |
| `project_id` | UUID | Có | FK `Project.id` | Chưa biết dự án vẫn tiếp nhận; khi định tuyến phải khớp case. |
| `reporter_type` | ENUM | Không |  | Snapshot CITIZEN hoặc INVESTOR_REPRESENTATIVE, không tăng quyền. |
| `description` | TEXT | Không |  | Nội dung người gửi. |
| `submitted_at` | TIMESTAMPTZ | Không |  | Thời điểm server nhận; báo cáo đã gửi cần ít nhất một ReportPhoto hợp lệ. |

#### `ReportPhoto` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Ảnh và tọa độ riêng; mỗi hiệu chỉnh tạo revision mới. |
| `incident_report_id` | UUID | Không | FK `IncidentReport.id` | Phản ánh sở hữu. |
| `file_id` | UUID | Không | FK `File.id` | Ảnh gốc đã xác nhận checksum. |
| `location` | GEOMETRY(Point) | Không |  | Vị trí lỗi do Reporter xác nhận; WGS84, lat [-90,90], lon [-180,180]. |
| `coordinate_source` | ENUM | Không |  | DEVICE_CAPTURE, EXIF, MANUAL; Manual không có độ chính xác tự đặt. |
| `original_location` | GEOMETRY(Point) | Có |  | Giữ tọa độ gốc thiết bị/EXIF nếu có, tách vị trí lỗi đã chọn. |
| `original_coordinate_source` | ENUM | Có |  | Nguồn tọa độ gốc, không ghi đè khi sửa. |
| `captured_at` | TIMESTAMPTZ | Có |  | Thời điểm chụp nếu có, không dùng thời điểm upload thay thế. |
| `submitted_at` | TIMESTAMPTZ | Không |  | Thời điểm nhận ảnh. |
| `accuracy_m` | DECIMAL(12,3) | Có |  | Độ chính xác thiết bị báo, >=0; null nếu không có/nhập tay. |
| `supersedes_photo_id` | UUID | Có | FK `ReportPhoto.id` | Revision trước cùng report/file; ảnh gốc và lịch sử giữ nguyên. |
| `confirmed_by_user_id` | UUID | Không | FK `User.id` | Người xác nhận hiệu chỉnh, được audit. |
| `confirmed_at` | TIMESTAMPTZ | Không |  | Thời điểm xác nhận vị trí. |

#### `ReportStatusEvent` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Sự kiện công khai append-only, tách lịch sử nội bộ. |
| `incident_report_id` | UUID | Không | FK `IncidentReport.id` | Chỉ owner được đọc. |
| `incident_case_id` | UUID | Không | FK `IncidentCase.id` | Case thực tế tại thời điểm sự kiện, giữ nguồn sau gộp. |
| `event_code` | ENUM | Không |  | SUBMITTED, RECEIVING, ACCEPTED, VERIFYING, DEFECT_FOUND, NO_DEFECT, AWAITING_REPAIR, REPAIRING, RETESTING, REPAIRED, DUPLICATE, OUT_OF_SCOPE. |
| `public_message` | TEXT | Không |  | Nội dung được phép công bố; NO_DEFECT cần lý do PM, không lộ chi phí/PII nội bộ. |
| `published_by_user_id` | UUID | Có | FK `User.id` | PM công bố kết luận/kết quả; null chỉ sự kiện hệ thống như SUBMITTED. |
| `occurred_at` | TIMESTAMPTZ | Không |  | Thời điểm sự kiện thực; không tạo tiến độ giả. |

#### `ReportStatusEventPhoto` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Liên kết ảnh sau sửa được PM chọn công bố. |
| `report_status_event_id` | UUID | Không | FK `ReportStatusEvent.id` | Sự kiện REPAIRED đã được phép công bố. |
| `repair_evidence_id` | UUID | Không | FK `RepairEvidence.id` | Chỉ AFTER, server xác nhận, đúng Defect/phạm vi report; UQ cùng event. |
| `caption` | TEXT | Có |  | Chú thích công khai, không ảnh nội bộ tùy ý. |

#### `IncidentCaseHistory` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Append-only cả chuyển trạng thái và đổi người phụ trách. |
| `incident_case_id` | UUID | Không | FK `IncidentCase.id` | Hồ sơ nguồn. |
| `from_status` | ENUM | Có |  | Null tại tạo mới; giữ cùng status nếu chỉ đổi PM. |
| `to_status` | ENUM | Không |  | Trạng thái sau sự kiện. |
| `from_pm_user_id` | UUID | Có | FK `User.id` | PM trước. |
| `to_pm_user_id` | UUID | Có | FK `User.id` | PM sau. |
| `actor_user_id` | UUID | Có | FK `User.id` | Người/hệ thống gây sự kiện. |
| `reason` | TEXT | Không |  | Lý do và kết luận; chi tiết nội bộ không tự trả Reporter. |
| `evidence_snapshot` | JSONB | Có |  | ID/checksum review, phê duyệt, repair item hoặc kết quả nghiệm thu liên quan. |
| `occurred_at` | TIMESTAMPTZ | Không |  | UTC, không chỉnh sửa lịch sử. |

#### `IncidentCaseDefect` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Liên kết hồ sơ và lỗi, giữ một Defect dù có nhiều phản ánh. |
| `incident_case_id` | UUID | Không | FK `IncidentCase.id` | Hồ sơ; UQ cặp case/defect. |
| `defect_id` | UUID | Không | FK `Defect.id` | Lỗi được PM liên kết, không tự tạo VERIFIED từ report. |
| `is_required` | BOOLEAN | Không |  | Lỗi bắt buộc xử lý trước khi case Fixed/Verified. |
| `linked_at` | TIMESTAMPTZ | Không |  | Thời điểm liên kết. |

### 3.2b Phân đoạn tuyến có phiên bản

#### `RoadSegmentSet` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Bộ phân đoạn có phiên bản, đề xuất tên canonical; SegmentSetId trong manifest trỏ đây. |
| `road_section_version_id` | UUID | Không | FK `RoadSectionVersion.id` | Một phiên bản tuyến xác nhận. |
| `version_no` | INTEGER | Không |  | UQ (road_section_version_id, version_no). |
| `status` | ENUM | Không |  | DRAFT, PUBLISHED, SUPERSEDED; nội dung bộ đã công bố bất biến. |
| `target_length_m` | DECIMAL(14,3) | Không |  | >0, cho phép 100/250/500/1000m hoặc giá trị hợp lệ khác, trộn độ dài sau sửa. |
| `published_at` | TIMESTAMPTZ | Có |  | Thời điểm công bố. |
| `published_by_user_id` | UUID | Có | FK `User.id` | PM có quyền dự án; geometry tuyến được xác nhận riêng. |

#### `RoadSegment` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | ID bất biến thuộc bộ; không dùng code để thay FK. |
| `segment_set_id` | UUID | Không | FK `RoadSegmentSet.id` | Bộ sở hữu. |
| `road_section_version_id` | UUID | Không | FK `RoadSectionVersion.id` | Phải bằng version của bộ. |
| `code` | VARCHAR(80) | Không |  | UQ trong bộ. |
| `sequence` | INTEGER | Không |  | Thứ tự theo chiều tăng lý trình, UQ trong bộ. |
| `start_offset_m` | DECIMAL(14,3) | Không |  | Khoảng cách dọc tuyến từ đầu, >=0. |
| `end_offset_m` | DECIMAL(14,3) | Không |  | > start_offset_m, không vượt chiều dài tuyến. |
| `geometry` | GEOMETRY(LineString) | Không |  | Cắt từ tuyến, đầu/cuối suy ra, SRID kỹ thuật đã biết. |
| `length_m` | DECIMAL(14,3) | Không |  | EndOffset-StartOffset, chiều dài dọc geometry. |

#### `RoadSegmentMapping` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Ánh xạ trước/sau append-only khi chia/gộp/chỉnh biên. |
| `source_segment_id` | UUID | Không | FK `RoadSegment.id` | Segment bộ cũ. |
| `target_segment_id` | UUID | Không | FK `RoadSegment.id` | Segment bộ mới; UQ cặp source/target/mapping_version. |
| `mapping_version` | INTEGER | Không |  | Phiên bản quy tắc ánh xạ. |
| `source_start_offset_m` | DECIMAL(14,3) | Không |  | Đầu khoảng giao trong hệ offset tuyến cũ. |
| `source_end_offset_m` | DECIMAL(14,3) | Không |  | Cuối khoảng giao. |
| `target_start_offset_m` | DECIMAL(14,3) | Không |  | Đầu khoảng tương ứng tuyến mới. |
| `target_end_offset_m` | DECIMAL(14,3) | Không |  | Cuối khoảng tương ứng. |
| `method` | VARCHAR(100) | Không |  | SAME_GEOMETRY_OVERLAP hoặc mapping tuyến mới được kiểm chứng riêng. |
| `provenance` | JSONB | Không |  | Nguồn, người/thời điểm xác nhận, confidence; không ghi đè job/result cũ. |

### 3.3a Phạm vi khảo sát và video theo vùng quan sát

#### `SurveyWorkItem` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Một segment trong một yêu cầu khảo sát, có thể nhiều lượt/video. |
| `survey_request_id` | UUID | Không | FK `SurveyRequest.id` | Nhiệm vụ giao Operator, baseline/định kỳ vẫn độc lập incident. |
| `road_segment_id` | UUID | Không | FK `RoadSegment.id` | Segment trong bộ PUBLISHED; giữ nguyên sau giao. |
| `due_at` | TIMESTAMPTZ | Không |  | Hạn của phạm vi. |
| `requirements` | JSONB | Không |  | Chất lượng, planned flight corridor và bản đồ; không bắt drone nằm trên tim tuyến. |

#### `SurveyCoverageRequirement` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Một vùng quan sát bắt buộc của work item; ít nhất một dòng khi giao. |
| `survey_work_item_id` | UUID | Không | FK `SurveyWorkItem.id` | Work item có một hoặc nhiều band. |
| `target_band` | ENUM | Không |  | SURFACE, LEFT_EDGE, RIGHT_EDGE; trái/phải theo chiều tăng lý trình. |
| `carriageway_code` | VARCHAR(80) | Có |  | Phần đường khi cần phân biệt; PM xác nhận mép mục tiêu. |
| `quality_requirements` | JSONB | Không |  | Tiêu chí nhìn thấy vùng; UQ (work_item, target_band, carriageway). |

#### `SurveyCoverageResult` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Đánh giá riêng cho mỗi band/dataset, có lịch sử. |
| `coverage_requirement_id` | UUID | Không | FK `SurveyCoverageRequirement.id` | Vùng yêu cầu. |
| `survey_data_version_id` | UUID | Không | FK `SurveyDataVersion.id` | Dataset của Survey thuộc đúng SurveyRequest. |
| `assessment_no` | INTEGER | Không |  | UQ (requirement, dataset, assessment_no); append-only. |
| `status` | ENUM | Không |  | SUFFICIENT, PARTIAL, INSUFFICIENT, UNKNOWN; không suy từ AI COMPLETED. |
| `coverage_details` | JSONB | Không |  | Khoảng nhìn thấy/thiếu, mờ/che khuất/GPS và nguồn bằng chứng. |
| `assessed_at` | TIMESTAMPTZ | Không |  | Thời điểm đánh giá. |

#### `SurveyVideoInterval` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Ánh xạ bất biến video gốc -> band/segment/dataset. |
| `coverage_requirement_id` | UUID | Không | FK `SurveyCoverageRequirement.id` | Segment+band tác nghiệp; một video có nhiều dòng ánh xạ. |
| `survey_data_version_id` | UUID | Không | FK `SurveyDataVersion.id` | Dataset xác nhận chứa file nguồn. |
| `survey_file_id` | UUID | Không | FK `SurveyFile.id` | VIDEO gốc của đúng Survey/lượt bay; checksum qua File/SurveyFile. |
| `start_time_ms` | INTEGER | Không |  | >=0 theo video gốc. |
| `end_time_ms` | INTEGER | Không |  | > start, <= duration, có thể nhiều khoảng rời cho cùng band. |
| `station_start_m` | DECIMAL(14,3) | Có |  | Lý trình dự kiến khi có căn cứ. |
| `station_end_m` | DECIMAL(14,3) | Có |  | Không nối giả qua mất GPS. |
| `positioning_method` | VARCHAR(100) | Không |  | Telemetry/time match, footprint hoặc PM review; thiếu thì UNKNOWN. |
| `positioning_confidence` | DECIMAL(6,5) | Có |  | 0..1 khi đánh giá được. |
| `source_metadata` | JSONB | Không |  | Raw aircraft GPS+timestamp+accuracy, telemetry File/checksum, đồng bộ thời gian; projected station+cross-track riêng; pose/calibration/observed ROI nullable; phân biệt nguồn thiếu. |
| `supersedes_interval_id` | UUID | Có | FK `SurveyVideoInterval.id` | Hiệu chỉnh tạo ánh xạ mới, job cũ giữ ID cũ. |

### 3.4a Manifest AI và liên kết quan sát

#### `ProcessingInputManifest` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Snapshot bất biến của input AI, không tạo hệ job song song. |
| `processing_job_id` | UUID | Không | FK `ProcessingJob.id` | UQ, một manifest cho job; phải có trước dispatch. |
| `contract_version` | VARCHAR(40) | Không |  | Phiên bản hợp đồng. |
| `checksum` | CHECKSUM | Không |  | Fingerprint nội dung không gồm URL tạm thời. |
| `survey_data_version_id` | UUID | Không | FK `SurveyDataVersion.id` | Dataset SERVER_CONFIRMED, khớp block. |
| `road_section_version_id` | UUID | Không | FK `RoadSectionVersion.id` | Tuyến snapshot. |
| `segment_set_id` | UUID | Không | FK `RoadSegmentSet.id` | Bộ snapshot, không tự chuyển khi chia lại. |
| `road_segment_id` | UUID | Không | FK `RoadSegment.id` | Phạm vi chính của block, khớp bộ/tuyến. |
| `target_band` | ENUM | Không |  | SURFACE, LEFT_EDGE, RIGHT_EDGE. |
| `model_version_id` | UUID | Không | FK `AIModelVersion.id` | Model bất biến khớp job. |
| `preprocessing_version` | VARCHAR(80) | Không |  | Version tiền xử lý/cấu hình; thay đổi tạo job mới. |
| `manifest_payload` | JSONB | Không |  | Project/Survey/CorrelationId, CRS/đơn vị, primary+context offsets, interval IDs/File/checksum, telemetry/time alignment, pose thiếu nêu rõ, requested defect types, quality; không có PII/chi phí. |
| `created_at` | TIMESTAMPTZ | Không |  | Được lưu bền vững trước worker dispatch. |

#### `DefectObservation` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Nhóm quan sát vào cùng lỗi, giữ raw detection. |
| `defect_id` | UUID | Không | FK `Defect.id` | Một lỗi có nhiều quan sát qua frame/block/lượt bay. |
| `ai_detection_id` | UUID | Không | FK `AIDetection.id` | UQ: một quan sát chỉ thuộc một lỗi hiện hành; sửa nhóm lưu audit. |
| `linked_by_user_id` | UUID | Không | FK `User.id` | PM xác nhận nhóm; gần tọa độ không tự là cùng lỗi. |
| `linked_at` | TIMESTAMPTZ | Không |  | Thời điểm, không xóa nguồn result. |

#### `DefectSegment` — thiết kế đích

| Trường | Kiểu | Null | Khóa/Tham chiếu | Định nghĩa |
|---|---|---:|---|---|
| `id` | UUID | Không | PK | Một lỗi liên quan nhiều segment, không nhân đôi sửa chữa. |
| `defect_id` | UUID | Không | FK `Defect.id` | Lỗi nguồn; UQ (defect, segment, mapping_version). |
| `road_segment_id` | UUID | Không | FK `RoadSegment.id` | Segment của bộ được ánh xạ. |
| `mapping_version` | INTEGER | Không |  | Ánh xạ mới không ghi đè bản cũ. |
| `is_primary` | BOOLEAN | Không |  | Tối đa một segment chính mỗi lỗi/bộ/version mapping; có thể chưa chọn nếu mơ hồ. |
| `location_status` | ENUM | Không |  | CONFIRMED, ESTIMATED, UNKNOWN; candidate không tự thành confirmed. |
| `provenance` | JSONB | Không |  | Station/geometry, confidence, source observation IDs và quy tắc/PM xác nhận. |

Quy tắc mới dùng chung: gửi report tạo case New, chưa biết project vẫn nhận; Assigned cần PM/project. Case và report lịch sử độc lập; report trùng theo case chính, lịch sử case cũ giữ nguyên. ReportStatusEvent là view công khai do sự kiện thật tạo, không ánh xạ máy móc từ status Open. REPAIRED cần case VERIFIED, mọi lỗi bắt buộc đạt nghiệm thu, ảnh AFTER phù hợp và PM công bố; Fixed chưa đủ. NO_DEFECT cần lý do PM, khác DUPLICATE/OUT_OF_SCOPE. Chỉ Supervisor đóng case đã sửa sau Verified; Crew không tự Verified/Closed. Retest thất bại quay Open; từ chối đề xuất sửa không tự đóng case.

Bộ segment công bố phải phủ tuyến không hở/chồng: [start,end), segment cuối chứa điểm cuối. Chia/gộp/kéo biên tạo bộ mới và RoadSegmentMapping; đổi geometry tạo RoadSectionVersion mới. Không gán phát hiện chỉ biết segment cũ cho tất cả segment con. Job/manifest/interval/repair lịch sử giữ phiên bản gốc. RouteCapture trước tuyến chuẩn là mở rộng riêng chưa có trong runtime; không bỏ FK của khảo sát chuẩn để giả hỗ trợ.

Một SurveyWorkItem có nhiều band và nhiều video/lượt; SurveyVideoInterval trỏ đúng dataset/file/Survey/Request và band của work item. Nguồn GPS, station chiếu và vị trí lỗi tách biệt; pose/định vị thiếu để unknown. Bay lệch chủ đích không tự là GPS sai. Coverage đo phần đường thực nhìn thấy, mỗi band/dataset riêng; không dùng thành công upload/AI để suy ra đủ phủ hoặc NO_DEFECT. ProcessingInputManifest snapshot interval IDs đã xác nhận; tải lại URL hết hạn giữ File/checksum/input identity. Mỗi block có context overlap; nhóm quan sát cần xét loại, bên, lý trình và bằng chứng, không chỉ khoảng cách.

## 4. Enum và trạng thái chuẩn

Đây là bộ giá trị logic đề xuất cho API/database. Tên hiển thị tiếng Việt có thể đặt ở lớp i18n, không dùng làm giá trị lưu trữ. Với C#, các enum trạng thái/scope nên khai báo `enum : byte` và gán số cố định; EF Core lưu thành SQL Server `tinyint`. Nếu có enum cần hơn 255 giá trị thì dùng `enum` mặc định `int` và SQL Server `int`.

Ví dụ:

```csharp
public enum QualityCheckScope : byte
{
    Unknown = 0,
    SurveyFile = 1,
    SurveyDataset = 2
}

public enum QualityCheckStatus : byte
{
    Unknown = 0,
    Pending = 1,
    Passed = 2,
    Failed = 3,
    Warning = 4
}
```

Không đổi hoặc sắp xếp lại số đã phát hành. Runtime hiện có Supervisor=1, ProjectManager=2, DroneOperator=3, RepairCrew=4; Reporter=5 là đề xuất chưa triển khai. Các enum mới là hợp đồng thiết kế; phải kiểm tra schema, validation/API/client trước triển khai, không suy ra migration đã có.

| Nhóm | Giá trị |
|---|---|
| Role (thiết kế đích) | `SUPERVISOR`=1, `PM`=2, `DRONE_OPERATOR`=3, `REPAIR_CREW`=4, `REPORTER`=5 (đề xuất) |
| Reporter type | `CITIZEN`, `INVESTOR_REPRESENTATIVE` |
| Incident case status | `NEW`, `ASSIGNED`, `OPEN`, `FIXED`, `RETEST`, `VERIFIED`, `CLOSED` (hiển thị New → Assigned → Open → Fixed → Retest → Verified → Closed) |
| Incident closure reason | `REPAIRED`, `NO_DEFECT`, `DUPLICATE`, `OUT_OF_SCOPE` |
| Report public event | `SUBMITTED`, `RECEIVING`, `ACCEPTED`, `VERIFYING`, `DEFECT_FOUND`, `NO_DEFECT`, `AWAITING_REPAIR`, `REPAIRING`, `RETESTING`, `REPAIRED`, `DUPLICATE`, `OUT_OF_SCOPE` |
| Target band | `SURFACE`, `LEFT_EDGE`, `RIGHT_EDGE` (Surface/LeftEdge/RightEdge) |
| Coverage | `SUFFICIENT`, `PARTIAL`, `INSUFFICIENT`, `UNKNOWN` |
| Segment set | `DRAFT`, `PUBLISHED`, `SUPERSEDED` |
| Field task source | `INCIDENT_CASE`, `DEFECT` |
| Verification source | `DRONE_REVIEW`, `FIELD_INSPECTION` |
| User status | `ACTIVE`, `SUSPENDED`, `PENDING` |
| Project status | `PLANNING`, `ACTIVE`, `CLOSED` |
| Survey request status | `NEW_ASSIGNED`, `ACCEPTED`, `REJECTED`, `REASSIGNED`, `IN_PROGRESS`, `SUBMITTED`, `SUPPLEMENT_REQUIRED`, `COMPLETED`, `CANCELLED`, `POSTPONED` |
| Quality check status | `PENDING`, `PASSED`, `FAILED`, `WARNING` |
| Quality check scope | `SURVEY_FILE`, `SURVEY_DATASET` |
| Quality check execution stage | `CLIENT_PRECHECK`, `SERVER_VALIDATION` |
| Quality check actor | `DRONE_APP`, `BACKEND` |
| Measurement type | `DEPRESSION_DEPTH`, `SLAB_FAULTING_HEIGHT`, `SHOULDER_EROSION_EXTENT` |
| Field inspection task status | `NEW_ASSIGNED`, `ACCEPTED`, `REJECTED`, `IN_PROGRESS`, `SUPPLEMENT_REQUIRED`, `SUBMITTED`, `COMPLETED` |
| Field inspection assignment status | `ACTIVE`, `REJECTED`, `ENDED` |
| Field inspection source | `INCIDENT_CASE`, `DEFECT` |
| Defect location method | `UNKNOWN`, `PROJECTED_STATION`, `OBSERVED_FOOTPRINT`, `PM_CONFIRMED` |
| Field inspection purpose | `DEFECT_VERIFICATION`, `RESEARCH_VALIDATION` |
| Field inspection review decision | `DEFECT_CONFIRMED`, `NO_DEFECT` |
| Derived measurement source | `SURFACE_MODEL`, `DSM`, `MANUAL_DERIVED`, `OTHER` |
| Measurement validation sample | `INCLUDED`, `EXCLUDED`, `OUTLIER` |
| Research record status | `DRAFT`, `COMPLETED`, `IMPORTED`, `LOCKED`, `PUBLISHED`, `SUPERSEDED` |
| Processing status | `QUEUED`, `RUNNING`, `RETRYABLE_FAILURE`, `DATA_FAILURE`, `COMPLETED`, `CANCELLED` |
| Defect status (pre-repair) | `OPEN`, `VERIFIED` (DefectVerified), `REJECTED`, `RESOLVED` |
| Incident case lifecycle (post-repair Verified) | `NEW`, `ASSIGNED`, `OPEN`, `FIXED`, `RETEST`, `VERIFIED`, `CLOSED` |
| Repair batch version | `DRAFT`, `PENDING_APPROVAL`, `REVISION_REQUIRED`, `APPROVED`, `REJECTED` |
| Retention status | `DRAFT`, `PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `EXECUTED`, `BLOCKED` |

Không tự ý đổi tên enum ở API sau khi triển khai; nếu cần đổi nhãn hiển thị, chỉ đổi bản dịch.

## 5. Ràng buộc dữ liệu quan trọng

1. `Project.project_code` duy nhất.
2. Một `Project` chỉ có tối đa một `ProjectMember` PM chính đang active tại một thời điểm.
3. `Warranty` có thể có nhiều bản ghi trên cùng `project_id`; thời gian/phạm vi nằm trên từng bản ghi.
4. `HandoverDocument` không có field đơn đại diện cho toàn bộ bảo hành.
5. `QualityCheck` phải có đúng một đích theo `scope`; `CLIENT_PRECHECK` phải do `DRONE_APP`, `SERVER_VALIDATION` phải do `BACKEND`, và chỉ cặp thứ hai có quyền xác nhận/chặn xử lý.
6. `SupplementarySurveyRequest` là aggregate độc lập; nhiều lượt được phân biệt bằng `round_no` trong cùng `survey_id`.
7. `SurveyDataVersion.status = SERVER_CONFIRMED` chỉ do Backend/System Worker thiết lập sau khi đủ file, checksum hợp lệ và các `SERVER_VALIDATION` bắt buộc đạt; kiểm tra của Drone App chỉ là precheck, PM chỉ quyết định bay bổ sung.
8. Versioned entity không update-in-place nội dung đã trình/xác nhận; tạo version mới.
9. `Evidence` phải có đúng một FK nghiệp vụ đích; file gốc không bị ghi đè.
10. Mọi log audit append-only; không lưu password, token, secret hoặc dữ liệu xác thực plaintext.
11. Mỗi `GroundTruthMeasurement` phải có `sample_id` duy nhất trong session, measurement type, value, unit, instrument, observer, time, location và bằng chứng hoặc lý do thiếu.
12. Mỗi `MeasurementValidationSample` phải ghép đúng một ground truth với một derived measurement cùng `sample_id` và cùng measurement type; không ghép theo thứ tự nhập liệu.
13. `MeasurementValidationRun.sample_count` chỉ đếm mẫu `INCLUDED`; mẫu `OUTLIER`/`EXCLUDED` phải giữ nguyên và có lý do.
14. PM chọn drone hoặc thực địa; số đo vật lý vẫn bắt buộc khi loại lỗi/quy tắc yêu cầu hoặc bằng chứng chưa đủ. Mỗi task có tối đa một FieldInspectionAssignment ACTIVE.
15. Session DEFECT_VERIFICATION cần task và Crew được giao; survey_id chỉ theo nguồn thật. Task DEFECT cần defect_id; task INCIDENT_CASE có thể chưa có Defect/Survey. RESEARCH_VALIDATION để task null và không tự kết luận nghiệp vụ.
16. DefectVerificationLog có đúng một đích ai_detection_id hoặc defect_id. PM CONFIRM/REJECT cần source_type và evidence_snapshot; FIELD_INSPECTION cần task hoàn tất, DRONE_REVIEW cần dataset đã xác nhận và bằng chứng gốc. Nếu bắt buộc đo, chỉ VERIFIED sau task COMPLETED/DEFECT_CONFIRMED và số đo đã gửi/khóa.
17. Chỉ tạo RepairItem cho Defect VERIFIED, đủ mọi điều kiện đo áp dụng; chặn OPEN/REJECTED và các yêu cầu bằng chứng/đo còn thiếu. Giao sửa chỉ từ version hiện hành được Supervisor duyệt.
18. Research Validation Track không tự tạo/chuyển trạng thái `Defect`, không tự chuyển `Warranty` và không thay thế quyết định PM trong workflow TN01–TN06, TN12/AI13.
19. PM nhập repair_method_summary và estimated_cost; hệ thống tính estimated_total_cost từ item. Nội dung và chi phí được snapshot theo version duyệt; không có BOM/giai đoạn thi công.
20. `FieldInspectionTask.source_type` phải có đúng một trong `incident_case_id`/`defect_id`; task INCIDENT_CASE được phép null `survey_id` và `defect_id`, task DEFECT phải có `defect_id` và chỉ có survey nếu nguồn thật. Không tạo Survey giả.

## 6. Chính sách bảo mật, PII và lưu trữ — đề xuất để review

Các chính sách dưới đây là đề xuất kỹ thuật, không tự kết luận nghĩa vụ pháp lý. Cần đối chiếu với chính sách an toàn thông tin và thời hạn lưu trữ hợp đồng của tổ chức trước khi ban hành chính thức.

### 6.1 Phân loại dữ liệu

| Mức | Dữ liệu RoadGuard | Quy tắc tối thiểu |
|---|---|---|
| `PUBLIC` | Mã loại lỗi/nguyên nhân đã công bố, tài liệu không nhạy cảm | Có thể hiển thị sau khi kiểm tra phạm vi. |
| `INTERNAL` | Mã dự án, trạng thái xử lý, metadata thiết bị | Chỉ người dùng đã đăng nhập và có quyền dự án. |
| `CONFIDENTIAL` | Bản đồ đoạn đường, ảnh/video khảo sát, chi phí, Warranty, Repair | Mã hóa khi truyền/lưu; kiểm soát theo project và vai trò; không public URL. |
| `RESTRICTED` | `password_hash`, token hash, PII, audit snapshot có thông tin cá nhân, legal hold | Chỉ service/role tối thiểu; che/mã hóa; cấm ghi log ứng dụng; truy cập phải có audit. |

### 6.2 Identity, secret và quyền truy cập

1. Dùng ASP.NET Core Identity/PasswordHasher hoặc thư viện chuẩn; không tự viết thuật toán hash mật khẩu. Không lưu password, reset token, refresh token plaintext.
2. Secret kết nối SQL Server, khóa mã hóa và credential object storage để ở Secret Manager/Azure Key Vault/Windows Certificate Store; không để trong source code, `appsettings.json` commit vào repository hoặc `AuditLog`.
3. SQL Server dùng tài khoản ứng dụng riêng, quyền tối thiểu theo schema; migration/deployment dùng tài khoản khác. Không cấp `db_owner` cho runtime.
4. API kiểm tra quyền theo `ProjectMember`; các truy vấn dashboard/export phải lọc project ở server. Có thể bổ sung SQL Server Row-Level Security khi cần lớp phòng vệ thứ hai.
5. Dùng TLS cho API và kết nối SQL Server; bật encryption in transit và kiểm tra certificate, không dùng `TrustServerCertificate=true` ở production.

### 6.3 Bảo vệ PII và snapshot audit

1. PII tối thiểu gồm `email`, `display_name`, IP/device metadata nếu thu thập. Chỉ lưu khi có mục đích; đặt `pii_purpose`/retention theo chính sách nội bộ nếu cần.
2. `AuditLog.before_snapshot`, `after_snapshot`, `source_manifest` và filter snapshot dùng allow-list field. Redact các khóa có tên `password`, `token`, `secret`, `authorization`, `cookie`, `connectionString` và dữ liệu nhạy cảm không phục vụ truy vết.
3. SQL Server bật TDE cho database và mã hóa backup; TDE không thay thế kiểm soát quyền hoặc mã hóa field. Với PII cần chống cả DBA đọc trực tiếp, cân nhắc Always Encrypted cho các cột cụ thể sau PoC.
4. Audit log append-only ở tầng ứng dụng và DB: role runtime không được `UPDATE/DELETE`; sửa sai bằng correction event, không ghi đè. Có thể partition theo `occurred_at` và lưu checksum/hash chain nếu yêu cầu chống sửa đổi mạnh hơn.

### 6.4 File/object storage

1. Bucket/container private; API cấp URL tải ngắn hạn (SAS/presigned URL) theo quyền project, không lưu public URL.
2. Khi upload: kiểm tra kích thước/MIME thực tế, quét malware, tính SHA-256, lưu checksum vào `File`, và ghi nhận kết quả kiểm tra. Không tin `original_name` hoặc MIME do client gửi.
3. Tệp gốc của khảo sát, bằng chứng sửa chữa và hồ sơ bàn giao là immutable về nội dung; bản chỉnh sửa tạo `File`/version mới.
4. Bản sao backup phải mã hóa và kiểm tra restore định kỳ. Khi có `LegalHold`, khóa xóa cả metadata và object tương ứng.

### 6.5 Retention, xóa và phục hồi

1. Giữ hồ sơ nghiệp vụ tối thiểu đến hết thời hạn Warranty cộng 5 năm theo User Story; `retention_until` phải tính từ Warranty phù hợp và lưu căn cứ trong `DataRetentionRequest.retention_basis`.
2. `AuditLog`, `PasswordResetLog`, `AccountStatusChangeLog` và `RetentionDeletionLog` đề xuất giữ tối thiểu bằng thời hạn hồ sơ liên quan, hoặc lâu hơn theo chính sách compliance; không tự đặt thời hạn pháp lý nếu chưa được phê duyệt.
3. Job retention chạy ở chế độ **dry-run** trước; tạo `DataRetentionRequest`, kiểm tra `LegalHold`, yêu cầu Supervisor phê duyệt, sau đó mới xóa đúng snapshot phạm vi. Không cascade xóa ngoài phạm vi được duyệt.
4. Xóa phải ghi `RetentionDeletionLog` với request, người duyệt, thời điểm, phạm vi và kết quả. Backup có lifecycle riêng; phải ghi rõ thời điểm bản sao hết hạn, không tuyên bố đã xóa hoàn toàn nếu backup còn tồn tại.
5. Có quy trình khôi phục và kiểm tra tính toàn vẹn; khôi phục dữ liệu không được làm mất audit history hoặc tạo bản ghi trùng.

### 6.6 Logging và vận hành

- Log ứng dụng chỉ ghi `correlation_id`, event code, entity id và kết quả; không ghi request body chứa PII/secret.
- Alert khi có nhiều lần reset thất bại, truy cập ngoài project, tải file bất thường, thay đổi quyền, hoặc xóa bị block bởi LegalHold.
- Đồng bộ thời gian máy chủ bằng NTP; tất cả `datetimeoffset` lưu UTC để điều tra sự kiện nhất quán.

### 6.7 Các lựa chọn kỹ thuật đã chốt theo yêu cầu hiện tại

| Hạng mục | Quyết định |
|---|---|
| Database | SQL Server; dùng SQL Server Spatial, không dùng PostGIS. |
| Ngôn ngữ/ORM | C# + Entity Framework Core. |
| Enum | C# enum; ưu tiên underlying `byte` + SQL Server `tinyint` cho status/scope; `int` khi cần. |
| Tiền tệ | Chỉ VND; tiền dùng `decimal(19,2)`; không cần `currency_code` trong từng entity. |
| Thời gian | `DateTimeOffset`/`datetimeoffset(7)`, lưu UTC. |
| SRID mặc định | GPS `geography(4326)`; geometry kỹ thuật dùng UTM `32648` hoặc `32649` theo khu vực; VN-2000 chỉ khi có mã được xác nhận. |

### 6.8 Tài liệu kỹ thuật nên dùng khi triển khai

- [SQL Server spatial data types overview](https://learn.microsoft.com/en-us/sql/relational-databases/spatial/spatial-data-types-overview)
- [EF Core value conversions](https://learn.microsoft.com/en-us/ef/core/modeling/value-conversions)
- [EF Core SQL Server provider](https://learn.microsoft.com/en-us/ef/core/providers/sql-server/)
- [ASP.NET Core Data Protection](https://learn.microsoft.com/en-us/aspnet/core/security/data-protection/introduction)
- [ASP.NET Core logging](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/logging/)

## 7. Ma trận truy vết

| Chủ đề | Entity/field chính | Nguồn |
|---|---|---|
| Audit và log riêng | `PasswordResetLog`, `AccountStatusChangeLog`, `AuditLog.*` | `UD-01`, CN10, QT01, QT09 |
| Nhiều giai đoạn bảo hành | `Warranty.*`, không có warranty field trong `HandoverDocument` | `UD-02`, DA04-DA05, QT05, QT11-QT13 |
| QualityCheck hai cấp và đúng tác nhân | `QualityCheck.scope`, `execution_stage`, `checked_by`, `survey_file_id`, `survey_data_version_id` | `UD-03`, KS08-KS10, US-06, US-07 |
| Yêu cầu khảo sát bổ sung | `SupplementarySurveyRequest.*`, `round_no`, `survey_id` | `UD-04`, KS11-KS12, US-07 |
| Version hình học | `RoadSectionVersion`, `road_section_version_id` | US-03 mục 3 |
| Hủy yêu cầu khảo sát | `SurveyDataVersion.status` | US-05 mục 5 |
| Retry xử lý | `ProcessingAttempt.error_type` | US-07, US-18 |
| Đo vật lý bắt buộc theo điều kiện; Research Validation độc lập | `FieldInspectionTask`, `FieldInspectionAssignment`, `FieldInspectionSession.purpose` | `UD-05`, AI13, TN01–TN06, TN12, US-20 |
| Xác minh hư hỏng chính thức | `Defect.status`, `DefectVerificationLog.field_inspection_task_id`, `GroundTruthMeasurement.defect_id` | `UD-05`, AI04-AI07, TN05, US-08, US-20 |
| Giữ lịch sử sửa chữa | `RepairBatchVersion`, `RepairItem`, `RepairEvidence` | US-11 đến US-14 |
| Rút gọn chi phí sửa chữa | `RepairItem.estimated_cost`, `RepairBatchVersion.estimated_total_cost` | `UD-06`, SC02-SC03, US-11 |
| Ground truth nghiên cứu | `FieldInspectionSession`, `GroundTruthMeasurement` | Đề cương, RS01-RS03 |
| Đối chiếu measurement uncertainty | `DerivedMeasurement`, `MeasurementValidationRun`, `MeasurementValidationSample` | Đề cương, RS04-RS06 |

## 8. Trạng thái tài liệu

Đây là bản Data Dictionary logic v1 để review. Các trường gắn `PROP` là đề xuất triển khai, cần xác nhận trước khi đóng băng DDL. Các quyết định `DEC` là yêu cầu thiết kế đã chốt và phải được giữ nguyên khi chuyển sang ERD, API contract và migration. Workflow TN01–TN06, TN12/AI13 được giữ cho nhánh thực địa/đo bắt buộc theo điều kiện. Kiểm chứng drone đủ bằng chứng và nguồn phản ánh trực tiếp là thiết kế mở rộng; Research Validation vẫn độc lập, không tự kết luận nghiệp vụ.
