# TÀI LIỆU THIẾT KẾ GIAO DIỆN: ROADGUARD AI TEST BENCH (UI DESIGN SPECIFICATION)

**Tác giả**: Antigravity Agent  
**Ngôn ngữ thiết kế**: THỦY MỆNH (1-Hue Pure Navy / Metallic Slate)  
**Phiên bản**: 2.0 (Design-First Architecture, Modular & Embeddable)  
**Trạng thái**: Đã phê duyệt & Sẵn sàng tích hợp hệ thống tổng

---

## 1. Triết Lý Thiết Kế & Phong Thủy Thủy Mệnh

Giao diện hệ thống được xây dựng trên triết lý **Thủy Mệnh** kết hợp **Phong cách Công nghiệp Tối giản (Technical Precision UI)**:
- **Tương hợp (Chủ đạo)**: Sắc thái Xanh dương sâu / Navy (`#0A2540`), Đen đại dương (`#061826`), Accent xanh biển (`#1E88C7`). Đại diện cho dòng chảy thông tin, sự sâu sắc và năng lực xử lý thị giác máy tính bền bỉ.
- **Tương sinh (Kim sinh Thủy - Nền tảng & Viền)**: Trắng sứ (`#FFFFFF`), Xám bạc kim loại (`#F4F7FA`, `#E9EFF5`), Viền kim khí mảnh (`#D5DEE8`), Bạc kỹ thuật (`#AEB9C6`). Đem lại ánh sáng phản chiếu sắc nét, bảo trợ cho hành Thủy.
- **Tương khắc (Tuyệt đối kiêng kỵ)**: Cấm sử dụng màu Vàng đất, Nâu đất (`#EAB308`, `#78350F`, `#854D0E` - Thổ khắc Thủy).
- **Thoát khí (Hạn chế tối đa)**: Tránh dùng xanh lá cây làm màu chủ đạo (Mộc tiết khí Thủy).
- **Cảnh báo nguy cấp duy nhất ngoài hệ màu**: Đỏ kỹ thuật (`#E5484D` - Danger / Critical), sử dụng chuẩn xác cho mức độ hư hỏng mặt đường cấp bách hoặc lỗi hệ thống nghiêm trọng.

---

## 2. Bảng Design Tokens Chuẩn Hóa

### 2.1. Bảng Màu (Color Tokens)

```css
:root {
  /* Nền Tương Sinh (Kim -> Thủy) */
  --bg-app: #F4F7FA;          /* Nền tổng thể ứng dụng */
  --bg-surface: #FFFFFF;      /* Nền thẻ nội dung (Card surface) */
  --bg-subtle: #E9EFF5;       /* Nền khối thứ cấp / Input / Highlight nhẹ */
  --bg-dark: #061826;         /* Nền Header / Panel điều khiển tối */

  /* Chữ & Biểu Tượng */
  --text-main: #0A2540;       /* Chữ chính, tiêu đề, độ tương phản cao */
  --text-muted: #3D4F61;      /* Chữ phụ, mô tả, nhãn trường dữ liệu */
  --text-subtle: #7A8FA3;     /* Chữ chú thích, placeholder, timestamp */
  --text-inverse: #FFFFFF;    /* Chữ trên nền tối */

  /* Màu Nhấn & Trạng Thái */
  --primary: #1E88C7;         /* Accent xanh dương kỹ thuật */
  --primary-hover: #166ba0;   /* Trạng thái hover nút chính */
  --primary-light: #E1F0FA;   /* Vùng chọn / Active tab */
  
  --badge-bg: #D6E9F5;        /* Nền badge thông tin */
  --badge-text: #0A2540;      /* Chữ badge thông tin */

  --border-color: #D5DEE8;    /* Viền kỹ thuật 1px sắc nét */
  --border-focus: #1E88C7;    /* Viền khi focus input */
  --metallic: #AEB9C6;        /* Kim loại trang trí viền/icon */

  --danger: #E5484D;          /* Báo động khẩn cấp / Ổ gà nguy hiểm */
  --danger-bg: #FDEDEE;       /* Nền badge nguy hiểm */
  --danger-border: #F8B4B7;   /* Viền nguy hiểm */
}
```

### 2.2. Phông Chữ (Typography Tokens)

Sử dụng 3 phông chữ chuẩn Google Fonts với phân định trách nhiệm rõ ràng:
1. **Nội dung & Giao tiếp (`Be Vietnam Pro`)**:
   - `font-family: 'Be Vietnam Pro', sans-serif;`
   - Dùng cho: Tiêu đề lớn, văn bản mô tả, lý luận KTV, nội dung phân tích.
2. **Nhãn Kỹ Thuật, Mã Số & Chỉ Số Đo Đạc (`Azeret Mono`)**:
   - `font-family: 'Azeret Mono', monospace;`
   - Thuộc tính: Viết HOA (`text-transform: uppercase`), cỡ chữ 11-13px.
   - Dùng cho: Mã khuyết tật (`DET_0116`), Tọa độ GPS (`10.762622N`), Kích thước (`1198.1 MM`), Thời gian (`00:23.02`), Bbox (`[X1, Y1, X2, Y2]`).
3. **Thành Phần UI Nhỏ & Nút Bấm (`Inter`)**:
   - `font-family: 'Inter', sans-serif;`
   - Dùng cho: Nút bấm, menu tab, nhãn input form, tooltip, bảng dữ liệu.

### 2.3. Quy Chuẩn Hình Học (Geometry & Spacing Tokens)

- **Bo góc (Border Radius)**:
  - Thẻ / Card / Container: `border-radius: 12px;`
  - Nút bấm / Input / Dropdown / Badge: `border-radius: 4px;`
  - Cửa sổ Modal / Drawer: `border-radius: 12px;`
- **Bóng đổ (Shadow)**:
  - `box-shadow: none !important;` (Triệt để loại bỏ bóng đổ generic dạng `shadow-lg`, `shadow-2xl`).
  - Độ sâu không gian được phân định hoàn toàn bằng màu nền tương phản (`#FFFFFF` trên `#F4F7FA`) và đường viền kỹ thuật `1px solid #D5DEE8`.
- **Độ dày viền (Border Width)**: Chuẩn duy nhất `1px solid var(--border-color)`.

---

## 3. Kiến Trúc Màn Hình & Phân Cấp Giao Diện

Hệ thống được tổ chức thành **3 vùng không gian chính** trong bố cục 2 cột đáp ứng (Responsive 2-Column Industrial Layout):

```
+-----------------------------------------------------------------------------------+
|  HEADER: Logo RoadGuard AI | Trạng Thái Hệ Thống | Thông Số GPU/CPU | Quick Switch |
+------------------------------------+----------------------------------------------+
|  CỘT TRÁI (380px)                   |  CỘT PHẢI (Không Gian Kết Quả & Thẩm Định)  |
|  [Card 1] NGUỒN DỮ LIỆU            |  [Thanh Metrics Tổng Hợp 5 Chỉ Số]           |
|   - Video Flycam / Dataset ZIP     |   * Tổng Khuyết Tật | Ổ Gà | Vết Nứt | Khẩn Cấp  |
|   - Nạp Phụ Đề Telemetry SRT       +----------------------------------------------+
|                                    |  [HỆ THỐNG TABS ĐIỀU HƯỚNG 4 KHÔNG GIAN]     |
|  [Card 2] CẤU HÌNH PIPELINE        |   [Tab 1] Khung Hình Trực Quan (Frame Viewer)|
|   - Model weights & Tiling 640x640 |   [Tab 2] Bộ Sưu Tập Cận Cảnh (Crops Grid)   |
|   - FPS trích xuất & Thời lượng    |   [Tab 3] Studio Thẩm Định KTV Tầng 2        |
|   - Nút Hành Động [Chạy Pipeline]  |   [Tab 4] Bảng Thống Kê & Xuất Báo Cáo GIS   |
|   - Tiến Trình Tuyến Tính 7 Stages |                                              |
|                                    |  [Khu Vực Xuất Bản: Tải PDF | JSON | GeoJSON] |
|  [Card 3] LỊCH SỬ NHIỆM VỤ GẦN ĐÂY |                                              |
+------------------------------------+----------------------------------------------+
```

---

## 4. Chi Tiết Từng Màn Hình / Không Gian Chức Năng

### 4.1. Màn Hình 1: Nguồn Dữ Liệu & Nạp Video (Data Source & Ingestion)
- **Vị trí file hiện tại**: `src/api/web/index.html:325-455`, `src/api/ui_server.py:192-259`.
- **Cấu trúc**:
  - Chuyển đổi linh hoạt giữa 2 chế độ: `Video Flycam (.mp4, .mov)` và `Dataset Nghiên Cứu (.zip, folder)`.
  - Hỗ trợ 3 phương thức cung cấp video:
    1. Chọn video thực địa có sẵn trong máy chủ (`DJI_0057.MP4`, `DJI_0059.MP4`, v.v.).
    2. Tải tệp mới trực tiếp từ máy trạm với drag & drop thanh lịch.
    3. Nhập đường dẫn tệp tuyệt đối trên ổ cứng máy chủ.
  - Vùng nạp tệp viễn thám SRT (`flight_telemetry.srt`): Tự động trích xuất vĩ độ, kinh độ, độ cao bay và tính toán GSD theo thời gian thực.
- **Trạng thái**:
  - `Empty`: Hiển thị placeholder kéo thả video nét đứt `1px dashed #D5DEE8`, nhãn chữ `Azeret Mono`.
  - `Loading`: Thanh đo % tải tệp lên server với spinner tối giản.
  - `Error`: Banner viền đỏ `#E5484D`, thông báo lỗi rõ ràng (sai định dạng, tệp rỗng).

### 4.2. Màn Hình 2: Cấu Hình Pipeline Tuyến Tính 7 Giai Đoạn (Pipeline Config & Execution)
- **Vị trí file hiện tại**: `src/api/web/index.html:457-550`, `src/api/ui_server.py:314-535`.
- **Cấu trúc**:
  - Bộ chọn trọng số mô hình: Danh sách các checkpoint trong thư mục `weights/`.
  - Tham số bay & đo đạc: Tần suất lấy mẫu FPS (`1 - 5 FPS`), Thời lượng (`0 = Toàn bộ video`), Ngưỡng tin cậy (`Confidence: 0.10 - 0.90`).
  - Tùy chọn Tiling 640x640: Kỹ thuật chia nhỏ khung hình độ phân giải cao có gối đầu 20%.
  - Nút kích hoạt chính: Nút phẳng màu xanh `#1E88C7`, hover `#166BA0`, chữ trắng, bo góc 4px.
  - **Khối Giám Sát Tiến Trình Tuyến Tính (Progress Tracker)**:
    - Hiển thị tuần tự trạng thái 7 stages: `01_segment` $\rightarrow$ `02_detect` $\rightarrow$ `03_filter` $\rightarrow$ `04_dedup` $\rightarrow$ `05_measure` $\rightarrow$ `06_inspect` $\rightarrow$ `07_report`.
    - Trạng thái trực quan: Chờ (`Pending` - xám `#AEB9C6`), Đang chạy (`Running` - xanh `#1E88C7` nhấp nháy nhẹ), Hoàn thành (`Done` - viền xanh lục bảo), Thất bại (`Failed` - đỏ `#E5484D`).

### 4.3. Màn Hình 3: Giám Sát Khung Hình Kỹ Thuật (Interactive Frame Viewer Tab)
- **Vị trí file hiện tại**: `src/api/web/index.html:561-591`, `src/api/ui_server.py:260-269`.
- **Cấu trúc**:
  - Khung chiếu ảnh độ phân giải cao hiển thị bounding box annotated.
  - Thanh trượt dòng thời gian (Time scrubber): Chọn nhanh khung hình theo giây và frame index.
  - Bảng thông số viễn thám khung hình: Timestamp, Frame ID, GPS Latitude/Longitude, Độ cao tương đối.
  - Bộ danh sách khuyết tật xuất hiện trong khung hình hiện tại: Click vào khuyết tật tự động highlight trên ảnh.
- **Trạng thái**:
  - `Empty`: Trạng thái chưa chạy phân tích: Hiển thị minh họa sơ đồ khung hình vector, hướng dẫn chọn nguồn và nhấn bắt đầu.
  - `Loading`: Skeleton nạp ảnh mượt mà.

### 4.4. Màn Hình 4: Bộ Sưu Tập Cận Cảnh Khuyết Tật (Crops Gallery Tab)
- **Vị trí file hiện tại**: `src/api/web/index.html:592-636`, `src/api/ui_server.py:270-313`.
- **Cấu trúc**:
  - Lưới ảnh thẻ (Card Grid) các vết cắt cận cảnh được tự động crop từ full-frame.
  - Bộ lọc tức thì: Tất cả / Chỉ Ổ gà (`Pothole`) / Chỉ Vết nứt (`Crack`) / Mức độ Nguy hiểm (`Critical`).
  - Thẻ khuyết tật chuẩn Thủy Mệnh: Ảnh crop sắc nét, nhãn phân loại, độ tin cậy %, kích thước vật lý (mm, m), badge mức độ nghiêm trọng.
  - Modal phóng to chi tiết khi người dùng click vào ảnh crop.

### 4.5. Màn Hình 5: Studio Thẩm Định & Gán Nhãn KTV Tầng 2 (Curation Studio Tab)
- **Vị trí file hiện tại**: `src/api/web/index.html:637-737`, `src/api/ui_server.py:634-974`.
- **Cấu trúc**:
  - Bảng làm việc của chuyên gia thẩm định đường bộ:
    - Công cụ AutoTagger AI: Tự động phân loại rác ngoại cảnh, bóng râm, khe co giãn.
    - Công cụ VLM Context Inspector: Gọi mô hình thị giác phân tích bối cảnh toàn cảnh mặt đường xung quanh vết cắt.
    - Công cụ Crack Severity Assessor: Đánh giá độ nguy hiểm vết nứt theo bề rộng và hình thái học.
  - Khối phán quyết KTV thủ công: Nút [Xác Nhận Hợp Lệ] (xanh `#1E88C7`), [Loại Bỏ Báo Động Giả] (xám `#3D4F61`), [Sửa Nhãn].
  - Modal Xuất Bản Tập Dữ Liệu (Dataset Export Modal): Đóng gói dữ liệu khuyết tật đã duyệt thành chuẩn YOLO (Train/Val split, nhãn txt, `data.yaml`, tải tệp zip).

### 4.6. Màn Hình 6: Bảng Thống Kê Chi Tiết & Tải Báo Cáo (Table View & Report Publishing)
- **Vị trí file hiện tại**: `src/api/web/index.html:738-800`, `src/api/ui_server.py:536-580`.
- **Cấu trúc**:
  - Bảng dữ liệu kỹ thuật: Mã khuyết tật, Khung hình, Thời điểm, Phân loại, Độ tin cậy, Bề rộng ước tính (mm), Chiều dài (m), Mức độ FHWA, Trạng thái KTV, Tọa độ GPS.
  - Tính năng tìm kiếm theo ID và sắp xếp đa cột.
  - Thanh công cụ tải xuống báo cáo hoàn chỉnh:
    - 📑 **[Tải Báo Cáo Kỹ Thuật PDF]**: Tệp PDF chuẩn công nghiệp theo design tokens Thủy Mệnh.
    - 📄 **[Tải Báo Cáo Dữ Liệu JSON]**: Định dạng REST chuẩn cho Backend ASP.NET Core.
    - 🗺️ **[Tải Lớp GIS GeoJSON]**: Sẵn sàng hiển thị trên QGIS hoặc ArcGIS.

### 4.7. Màn Hình 7: Lịch Sử Nhiệm Vụ & Chuyển Đổi Nhanh (Task Switcher)
- **Vị trí file hiện tại**: `src/api/web/index.html:420-455`, `src/api/ui_server.py:100-190`.
- **Cấu trúc**:
  - Danh sách các nhiệm vụ kiểm thử trước đó lưu trong `results/web_runs/`.
  - Xem nhanh số lượng phát hiện, thời gian chạy, và nhấp để nạp lại toàn bộ kết quả phân tích mà không cần tính toán lại.

---

## 5. Thư Viện Thành Phần Dùng Chung (Shared Components)

1. **Button (Nút Hành Động)**:
   - Primary: Nền `#1E88C7`, chữ `#FFFFFF`, viền không, bo góc `4px`, padding `8px 16px`, font `Inter` 13px weight 600. Hover: `#166BA0`.
   - Secondary / Ghost: Nền `#FFFFFF`, chữ `#0A2540`, viền `1px solid #D5DEE8`, bo góc `4px`. Hover: nền `#F4F7FA`.
   - Danger: Nền `#E5484D`, chữ `#FFFFFF`, bo góc `4px`.
2. **Badge (Huy Hiệu Trạng Thái)**:
   - Kỹ thuật / Mã số: Nền `#D6E9F5`, chữ `#0A2540`, viền `1px solid #1E88C7`, bo `4px`, font `Azeret Mono` 11px.
   - Severity CRITICAL: Nền `#E5484D`, chữ `#FFFFFF`, font `Azeret Mono`.
   - Severity MEDIUM: Nền `#E9EFF5`, chữ `#0A2540`, viền `1px solid #D5DEE8`.
   - Severity LOW: Nền `#D6E9F5`, chữ `#0A2540`.
3. **Card (Thẻ Khối Nội Dung)**:
   - Nền `#FFFFFF`, viền `1px solid #D5DEE8`, bo góc `12px`, padding `16px 20px`, `box-shadow: none`.
   - Card Title: Chữ `#0A2540`, font `Be Vietnam Pro` weight 700, 15px.
4. **Data Table (Bảng Dữ Liệu)**:
   - Header `<th>`: Nền `#F4F7FA`, chữ `#3D4F61`, font `Azeret Mono` 11px IN HOA, padding `10px 14px`, viền đáy `1px solid #D5DEE8`.
   - Dòng dữ liệu `<td>`: Padding `10px 14px`, viền đáy `1px solid #E9EFF5`, hover nền `#F4F7FA`.
5. **Toast Notification (Thông Báo Tức Thời)**:
   - Nền `#061826`, chữ `#FFFFFF`, viền trái `4px solid #1E88C7`, bo góc `4px`, không shadow generic.

---

## 6. Tiêu Chuẩn Kiểm Thử Anti-AI-Slop 10/10

Mọi màn hình và thành phần giao diện bắt buộc vượt qua 10 điều kiện nghiêm ngặt:
1. ❌ **Cấm gradient tím-xanh mọi hình thức**: Chỉ sử dụng nền phẳng (#FFFFFF, #F4F7FA, #061826) hoặc dải màu đơn sắc navy.
2. ❌ **Cấm gradient text**: Toàn bộ chữ dùng màu đặc chuẩn token (`#0A2540`, `#3D4F61`, `#FFFFFF`).
3. ❌ **Cấm glassmorphism tràn lan**: Không sử dụng `backdrop-filter: blur()`, các thẻ có nền đục rõ ràng.
4. ❌ **Cấm emoji làm biểu tượng**: Thay thế toàn bộ bằng SVG kỹ thuật đơn sắc hoặc nhãn chữ kỹ thuật `[MÃ]`.
5. ❌ **Cấm rounded-2xl + shadow đồng loạt**: Thẻ chuẩn bo 12px, nút chuẩn bo 4px, `box-shadow: none`.
6. ❌ **Cấm layout SaaS generic**: Bố cục thiết kế tập trung vào công cụ kỹ thuật kiểm định đường bộ thực tế.
7. ❌ **Cấm số liệu hoặc testimonial bịa**: Chỉ hiển thị dữ liệu đo đạc thực tế từ video và mô hình.
8. ❌ **Cấm ảnh stock generic**: Toàn bộ ảnh là khung hình và ảnh trích xuất từ flycam thực tế.
9. ❌ **Cấm màu ngoài palette Thủy Mệnh**: 100% màu tuân thủ token (trừ đỏ `#E5484D` cho khẩn cấp).
10. ❌ **Chuẩn hóa văn phong tiếng Việt kỹ thuật**: Cấm lối viết dịch máy "được...bởi", cấm chuỗi "của" liên hoàn, cấm giọng chatbot xưng hô thừa thãi.
