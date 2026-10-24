<!-- ck-design-kit · screen: ui-integration-spec · P5 H5 E5 S5 R5 V5 -->
# HƯỚNG DẪN TÍCH HỢP GIAO DIỆN ROADGUARD AI (UI INTEGRATION SPECIFICATION)

**Tác giả**: Antigravity Agent  
**Phiên bản**: 3.0 (Decoupled Client & OpenAPI Contract Driven)  
**Mục tiêu**: Đảm bảo Giao diện Web UI RoadGuard AI độc lập 100%, sẵn sàng tách rời hoặc gắn trực tiếp vào dự án tổng (ASP.NET Core Web API, React/Next.js, Vue hoặc Micro-frontend) mà không phải sửa đổi mã nguồn lõi của AI Engine.

---

## 1. Nguyên Tắc Độc Lập Kiến Trúc (Decoupled Architecture)

Giao diện Web RoadGuard AI tuân thủ nghiêm ngặt 3 nguyên tắc phân tách hệ thống:
1. **100% Giao tiếp qua HTTP REST API Contracts**: UI chỉ tương tác với máy chủ thông qua các điểm cuối `/api/*` đã được quy định trong hợp đồng. Tuyệt đối cấm giao diện truy cập tệp tin nội bộ, import mã Python hoặc can thiệp trực tiếp vào database/filesystem.
2. **Cấu hình Động qua Khách (Config Injection via `window.ROADGUARD_CONFIG`)**: Địa chỉ máy chủ API, đường dẫn tài nguyên tĩnh, chu kỳ polling và chế độ hiển thị có thể được truyền vào từ bên ngoài trước khi ứng dụng khởi chạy.
3. **Mô-đun Hóa Phong Cách & Thành Phần**: Toàn bộ CSS/JS được tách rời thành 4 tệp độc lập (`tokens.css`, `layout.css`, `components.css`, `api_client.js`), sẵn sàng import vào bất kỳ web bundler nào (Vite, Webpack, Turbopack) hoặc nhúng qua thẻ `<link>` và `<script>`.

---

## 2. Điểm Gắn Kết & Cấu Hình Khách (Mount Points & Client Configuration)

### 2.1. Cấu Hình Biến Môi Trường Toàn Cục

Trước khi tải tệp `api_client.js`, ứng dụng chủ (Host Application) có thể định nghĩa cấu hình tại thẻ `<head>`:

```html
<script>
  window.ROADGUARD_CONFIG = {
    // 1. Địa chỉ gốc của AI Engine (để trống nếu proxy cùng domain)
    API_BASE_URL: "http://localhost:8080",
    
    // 2. Đường dẫn phục vụ kết quả tĩnh (ảnh khung hình, crop, báo cáo)
    STATIC_BASE_URL: "http://localhost:8080",
    
    // 3. Chu kỳ thăm dò trạng thái tác vụ nền (milliseconds)
    POLLING_INTERVAL_MS: 1500,

    // 4. Chế độ tích hợp: 'STANDALONE' | 'EMBEDDED' | 'MICRO_FRONTEND'
    INTEGRATION_MODE: "STANDALONE",

    // 5. Header xác thực tùy chọn (JWT Bearer Token nếu backend yêu cầu)
    AUTH_HEADER: ""
  };
</script>
<script src="/static/js/api_client.js"></script>
```

### 2.2. Khởi Tạo Đối Tượng API Client Trong Mã JavaScript

Lớp `RoadGuardAPIClient` cung cấp giao diện Promise-based cho toàn bộ 20 endpoints:

```javascript
// Sử dụng cấu hình mặc định (tự động đọc từ window.ROADGUARD_CONFIG)
const client = new RoadGuardAPIClient();

// Hoặc khởi tạo với tham số riêng biệt:
const customClient = new RoadGuardAPIClient({
  API_BASE_URL: "https://ai.roadguard.vn",
  POLLING_INTERVAL_MS: 2000
});

// Ví dụ: Bắt đầu phân tích video
const res = await customClient.startAnalysis({
  video_path: "data/raw_videos/DJI_0057.MP4",
  model_name: "best.pt",
  conf_threshold: 0.25,
  sampling_rate_fps: 2,
  max_duration_seconds: 30,
  use_tiling: true
});
console.log("Mã tác vụ khởi tạo:", res.task_id);
```

---

## 3. Danh Mục Hợp Đồng API (API Contracts Specifications)

Toàn bộ 20 endpoints được cung cấp bởi `src/api/ui_server.py`:

### 3.1. Nhóm Khởi Tạo & Thông Tin Hệ Thống
| Phương Thức | Tuyến Tuyến API | Tham Số Payload | Kiểu Trả Về | Mô Tả Chức Năng |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/` | Không | `text/html` | Trả về trang giao diện chính SPA (`index.html`). |
| `GET` | `/api/init-info` | Không | `JSON` | Danh sách mô hình `.pt`, video mẫu, preset dataset, tình trạng GPU/CPU. |

### 3.2. Nhóm Nạp Dữ Liệu Khảo Sát (Ingestion)
| Phương Thức | Tuyến Tuyến API | Tham Số Payload | Kiểu Trả Về | Mô Tả Chức Năng |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/upload-video` | `FormData: { file }` | `JSON` | Tải video flycam lên máy chủ. Trả về `{ path, filename, size_mb }`. |
| `POST` | `/api/upload-dataset` | `FormData: { file }` | `JSON` | Tải tập dữ liệu nén `.zip`. Tự động giải nén và quét đệ quy. |
| `POST` | `/api/upload-folder` | `FormData: { files[] }` | `JSON` | Tải hàng loạt ảnh từ một thư mục cục bộ của máy người dùng. |

### 3.3. Nhóm Điều Khiển & Giám Sát Pipeline AI
| Phương Thức | Tuyến Tuyến API | Tham Số Payload | Kiểu Trả Về | Mô Tả Chức Năng |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/start-analysis` | `JSON`: `{ video_path, model_name, conf_threshold, sampling_rate_fps, max_duration_seconds, use_tiling }` | `JSON` | Đưa video vào hàng đợi phân tích qua pipeline 7 stages. Trả về `{ task_id, status }`. |
| `POST` | `/api/start-dataset-analysis` | `JSON`: `{ dataset_path, model_name, conf_threshold, use_tiling }` | `JSON` | Bắt đầu quét hàng loạt ảnh trong dataset. |
| `GET` | `/api/task-status/{task_id}` | `task_id` (URL param) | `JSON` | Thăm dò tiến trình: `{ status, progress, stage, message }`. |
| `GET` | `/api/task-results/{task_id}` | `task_id` (URL param) | `JSON` | Nhận toàn bộ kết quả phân tích: `{ summary, frames, crops, all_defects }`. |

### 3.4. Nhóm Phục Vụ Hình Ảnh & Báo Cáo
| Phương Thức | Tuyến Tuyến API | Tham Số Payload | Kiểu Trả Về | Mô Tả Chức Năng |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/frames/{task_id}/{filename}` | `task_id, filename` | `image/jpeg` | Trả về tệp ảnh khung hình flycam có vẽ neon bounding box. |
| `GET` | `/api/crops/{task_id}/{filename}` | `task_id, filename` | `image/jpeg` | Trả về ảnh cắt cận cảnh vết nứt hoặc ổ gà. |
| `GET` | `/api/download/{task_id}/{filename}` | `task_id, filename` | `application/*` | Tải về báo cáo kỹ thuật `report.json`, `layer.geojson`. |

### 3.5. Nhóm Thẩm Định KTV AI (Curation & Benchmarking)
| Phương Thức | Tuyến Tuyến API | Tham Số Payload | Kiểu Trả Về | Mô Tả Chức Năng |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/curation/filter-and-tag` | `JSON`: `{ task_id, items }` | `JSON` | KTV AI tự động lọc bóng râm và gán nhãn chi tiết cho crops đã chọn. |
| `POST` | `/api/curation/inspect-overview-context` | `JSON`: `{ task_id, items, batch_size }` | `JSON` | KTV AI đọc bối cảnh toàn khung hình (Dual-View Context). |
| `POST` | `/api/curation/assess-cracks` | `JSON`: `{ task_id, items }` | `JSON` | Đánh giá độ nghiêm trọng, độ mở và hình thái học vết nứt. |
| `POST` | `/api/curation/update-item` | `JSON`: `{ task_id, item_index, updated_item }` | `JSON` | Kỹ sư cập nhật thủ công nhận định khuyết tật (Human-In-The-Loop). |
| `POST` | `/api/curation/save-all` | `JSON`: `{ task_id, curated_items }` | `JSON` | Lưu lại toàn bộ trạng thái thẩm định vào tệp kết quả trên đĩa. |
| `GET` | `/api/curation/results/{task_id}` | `task_id` (URL param) | `JSON` | Tải lại danh sách khuyết tật đã được thẩm định trước đó. |
| `POST` | `/api/curation/export-dataset` | `JSON`: `{ task_id, curated_items, export_unique_only }` | `JSON` | Đóng gói tập dữ liệu YOLO chuẩn (ảnh + nhãn + data.yaml) thành file ZIP. |
| `GET` | `/api/curation/download/{filename}` | `filename` (URL param) | `application/zip` | Tải tệp ZIP dataset đã đóng gói. |

---

## 4. Kịch Bản Tích Hợp Vào Dự Án Tổng

### Kịch Bản 1: Tích Hợp Vào Backend ASP.NET Core (Khuyến Nghị Cho Dự Án)

Trong kiến trúc tổng thể, Backend ASP.NET Core đảm nhiệm xác thực người dùng (Auth), quản trị dự án khảo sát và lưu trữ database SQL Server / PostgreSQL. AI Engine chạy độc lập dưới dạng service phân tích thị giác máy tính:
1. **Phục vụ Static Web UI qua ASP.NET Core**:
   Đặt mã nguồn `src/api/web/` vào thư mục `wwwroot/roadguard-ui` của dự án ASP.NET Core.
2. **Reverse Proxy YARP hoặc Controller Proxy**:
   Chuyển tiếp mọi yêu cầu `/api/roadguard/*` từ ASP.NET Core sang AI Engine Python tại cổng 8080:
   ```csharp
   // Program.cs (ASP.NET Core)
   app.MapReverseProxy();
   ```
   Cấu hình trong `appsettings.json`:
   ```json
   {
     "ReverseProxy": {
       "Routes": {
         "roadguard-ai": {
           "ClusterId": "ai-cluster",
           "Match": { "Path": "/api/roadguard/{**catch-all}" },
           "Transforms": [{ "PathPattern": "/api/{**catch-all}" }]
         }
       },
       "Clusters": {
         "ai-cluster": {
           "Destinations": {
             "ai-service": { "Address": "http://127.0.0.1:8080" }
           }
         }
       }
     }
   }
   ```

### Kịch Bản 2: Tích Hợp Vào Ứng Dụng React / Next.js Dạng Iframe hoặc Web Component

Khi nhúng vào Dashboard quản lý hạ tầng giao thông đô thị viết bằng React/Next.js:
```tsx
import React from 'react';

export const RoadGuardAIBench: React.FC = () => {
  return (
    <div className="w-full h-full border border-slate-200 rounded-lg overflow-hidden">
      <iframe
        src="http://localhost:8080"
        title="RoadGuard AI Test Bench"
        className="w-full h-[920px] border-none"
        allow="camera; microphone; display-capture"
      />
    </div>
  );
};
```

### Kịch Bản 3: Gọi Trực Tiếp Qua Micro-Service API Client (Headless Mode)

Bất kỳ service bên ngoài nào cũng có thể điều khiển toàn bộ pipeline bằng cách gọi REST API tương ứng mà không cần mở giao diện Web, nhận về kết quả dạng JSON và GeoJSON chuẩn GIS.
