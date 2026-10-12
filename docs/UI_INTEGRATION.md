# HƯỚNG DẪN TÍCH HỢP GIAO DIỆN: ROADGUARD AI (UI INTEGRATION SPECIFICATION)

**Tác giả**: Antigravity Agent  
**Phiên bản**: 2.0 (Decoupled Client & OpenAPI Contract Driven)  
**Mục tiêu**: Đảm bảo Giao diện Web UI độc lập 100%, sẵn sàng gắn vào dự án tổng (ASP.NET Core, Next.js, hoặc Micro-frontend) mà không can thiệp vào logic lõi của AI Engine.

---

## 1. Nguyên Tắc Độc Lập Kiến Trúc (Decoupled Architecture)

Giao diện Web RoadGuard AI tuân thủ nghiêm ngặt mô hình **Client-Server Decoupling**:
- **Không phụ thuộc nội bộ**: UI không gọi trực tiếp bất kỳ thư viện Python, file hệ thống hay hàm nội bộ nào của AI Engine.
- **100% Giao tiếp qua HTTP REST API Contracts**: Mọi tương tác nạp dữ liệu, kích hoạt pipeline, theo dõi tiến trình, duyệt kết quả và xuất bản đều đi qua các endpoints chuẩn hóa `/api/*`.
- **Độc lập cấu hình (Config Injection)**: UI tự động nhận diện cấu hình endpoint máy chủ qua đối tượng toàn cục `window.ROADGUARD_CONFIG` hoặc fallback về relative path `/api`.

---

## 2. Cấu Hình Khách (Client-Side Configuration)

Khi nhúng UI vào dự án tổng, người phát triển có thể thiết lập trước biến cấu hình tại thẻ `<head>` của trang hoặc file cấu hình môi trường:

```html
<script>
  window.ROADGUARD_CONFIG = {
    // URL gốc của AI Engine (để trống nếu cùng domain/proxy)
    API_BASE_URL: "http://localhost:8000",
    
    // Đường dẫn tĩnh phục vụ ảnh/kết quả
    STATIC_BASE_URL: "http://localhost:8000",
    
    // Tần suất thăm dò tiến trình tác vụ (milliseconds)
    POLLING_INTERVAL_MS: 1500,

    // Chế độ tích hợp: 'STANDALONE' | 'EMBEDDED' | 'IFRAME'
    INTEGRATION_MODE: "STANDALONE"
  };
</script>
```

---

## 3. Danh Mục Hợp Đồng API (API Contracts Specifications)

Toàn bộ 20 endpoints được cung cấp bởi `src/api/ui_server.py`:

### 3.1. Nhóm Khởi Tạo & Hệ Thống
| Phương thức | Đường dẫn | Tham số / Payload | Mô tả & Phản hồi |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | — | Trả về trang HTML chính (`index.html`). |
| `GET` | `/api/init-info` | — | Trả về danh sách model weights, video presets, video test, cấu hình GPU/CPU, danh sách tasks gần nhất. |

### 3.2. Nhóm Nạp Dữ Liệu Thực Địa (Ingestion)
| Phương thức | Đường dẫn | Tham số / Payload | Mô tả & Phản hồi |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/upload-video` | `file: UploadFile` | Tải video flycam (.mp4, .mov, .avi) lên thư mục lưu trữ tạm. |
| `POST` | `/api/upload-dataset` | `file: UploadFile` | Tải tập dữ liệu nén (.zip) chứa ảnh và nhãn. |
| `POST` | `/api/upload-folder` | `files: List[UploadFile]` | Tải danh sách ảnh từ một thư mục cục bộ. |

### 3.3. Nhóm Điều Khiển & Giám Sát Pipeline Tuyến Tính
| Phương thức | Đường dẫn | Tham số / Payload | Mô tả & Phản hồi |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/start-analysis` | `JSON`: `{ video_path, srt_path, model_name, conf_threshold, sampling_rate_fps, max_duration_seconds, use_tiling }` | Khởi động tác vụ phân tích video theo kiến trúc tuyến tính 7 stages. Trả về `{ task_id, status: 'QUEUED' }`. |
| `POST` | `/api/start-dataset-analysis` | `JSON`: `{ dataset_path, model_name, conf_threshold, use_tiling }` | Phân tích hàng loạt ảnh trong dataset. |
| `GET` | `/api/task-status/{task_id}` | `task_id` (Path) | Thăm dò trạng thái: `{ status: 'RUNNING'|'COMPLETED'|'FAILED', progress_percent, current_stage, message }`. |
| `GET` | `/api/task-results/{task_id}` | `task_id` (Path) | Lấy báo cáo chi tiết: `{ summary, detections, frames, crops, execution_time_seconds }`. |

### 3.4. Nhóm Truy Xuất Ảnh & Tài Nguyên Kết Quả
| Phương thức | Đường dẫn | Tham số / Payload | Mô tả & Phản hồi |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/frames/{task_id}/{filename}` | `task_id`, `filename` | Trả về tệp ảnh khung hình flycam đã vẽ bounding box (`image/jpeg`). |
| `GET` | `/api/crops/{task_id}/{filename}` | `task_id`, `filename` | Trả về tệp ảnh cận cảnh khuyết tật đã trích xuất (`image/jpeg`). |
| `GET` | `/api/download/{task_id}/{filename}`| `task_id`, `filename` | Tải về các tệp báo cáo kỹ thuật: `inspection_report.pdf`, `inspection_report.json`, `inspection_layer.geojson`. |

### 3.5. Nhóm Phân Hệ Thẩm Định KTV Tầng 2 & Đóng Gói Dữ Liệu (Curation)
| Phương thức | Đường dẫn | Tham số / Payload | Mô tả & Phản hồi |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/curation/filter-and-tag` | `JSON`: `{ task_id, items }` | AI AutoTagger tự động phân loại và tính điểm sơ bộ. |
| `POST` | `/api/curation/inspect-overview-context`| `JSON`: `{ task_id, items }` | VLM KTV phân tích bối cảnh toàn cảnh mặt đường xung quanh crop. |
| `POST` | `/api/curation/assess-cracks` | `JSON`: `{ task_id, items }` | Đánh giá độ nghiêm trọng và hình thái học vết nứt. |
| `POST` | `/api/curation/update-item` | `JSON`: `{ task_id, item_id, verdict, label, notes }` | KTV cập nhật thủ công trạng thái (VERIFIED / REJECTED). |
| `POST` | `/api/curation/save-all` | `JSON`: `{ task_id, curated_items }` | Lưu toàn bộ trạng thái curation vào tệp kết quả. |
| `GET` | `/api/curation/results/{task_id}` | `task_id` (Path) | Đọc lại kết quả thẩm định đã lưu của task. |
| `POST` | `/api/curation/export-dataset` | `JSON`: `{ task_id, curated_items, export_name, export_unique_only }` | Đóng gói các khuyết tật đã duyệt thành tập dữ liệu YOLO chuẩn (ảnh + nhãn + data.yaml + zip). |
| `GET` | `/api/curation/download/{filename}` | `filename` (Path) | Tải tệp zip dataset đã xuất bản. |

---

## 4. Kịch Bản Tích Hợp Vào Dự Án Tổng

### Kịch Bản 1: Tích hợp với Backend ASP.NET Core (Khuyến Nghị Cho Dự Án)
Trong kiến trúc tổng thể, Backend ASP.NET Core đảm nhiệm xác thực người dùng (Auth), quản trị dự án khảo sát và lưu trữ database SQL Server / PostgreSQL. AI Engine chạy độc lập dưới dạng service phân tích thị giác máy tính:
1. **Phục vụ Static Web UI qua ASP.NET Core**:
   Đặt mã nguồn `src/api/web/` vào thư mục `wwwroot/roadguard-ui` của dự án ASP.NET Core.
2. **Reverse Proxy Yarp hoặc Controller Proxy**:
   Chuyển tiếp mọi yêu cầu `/api/roadguard/*` từ ASP.NET Core sang AI Engine Python tại cổng 8000:
   ```csharp
   // Program.cs (ASP.NET Core)
   app.MapReverseProxy();
   // Cấu hình Yarp route: /ai-engine/{**catch-all} -> http://localhost:8000/api/{**catch-all}
   ```
3. **Cấu hình Client-side**:
   Gán `window.ROADGUARD_CONFIG.API_BASE_URL = "/ai-engine"` trong layout của ASP.NET Core.

### Kịch Bản 2: Nhúng vào Dashboard Frontend React / Next.js / Vue
1. Đóng gói UI thành một **Web Component** hoặc nhúng dạng **Iframe cách ly** với `postMessage` protocol:
   ```html
   <iframe 
     id="roadguardFrame" 
     src="http://ai-engine-host:8000/" 
     style="width: 100%; height: 100vh; border: none;"
   ></iframe>
   ```
2. Giao tiếp hai chiều an toàn giữa hệ thống cha và AI Test Bench:
   ```javascript
   // Hệ thống cha gửi thông điệp chọn video khảo sát
   const frame = document.getElementById('roadguardFrame').contentWindow;
   frame.postMessage({
     type: 'LOAD_INSPECTION_TASK',
     taskId: 'task_survey_highway_01'
   }, '*');
   ```

### Kịch Bản 3: Micro-frontend Độc Lập Với Nginx
Cấu hình Nginx phục vụ tĩnh toàn bộ `src/api/web/` và reverse proxy các cuộc gọi `/api` về FastAPI server:
```nginx
server {
    listen 80;
    server_name roadguard.local;

    location / {
        root /var/www/roadguard-ui;
        index index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 5. Danh Mục Kiểm Tra Hợp Chuẩn (Integration Checklist)

- [x] **Không rò rỉ mã nguồn lõi**: UI không trực tiếp phụ thuộc vào thư viện nội bộ.
- [x] **CORS Support**: `ui_server.py` đã cấu hình `CORSMiddleware(allow_origins=["*"])` sẵn sàng cho cross-origin requests.
- [x] **Xử lý ngắt kết nối an toàn**: Client tự động hiển thị thông báo lỗi thân thiện khi API server không phản hồi thay vì làm sập trang.
- [x] **Tương thích thiết bị**: Thiết kế linh hoạt tự co giãn từ màn hình Desktop kỹ thuật (1920x1080) đến Laptop giám sát (1366x768).
