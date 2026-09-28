# ⚙️ ROADGUARD — ĐẶC TẢ TÍCH HỢP HỆ THỐNG DÀNH CHO ĐỘI BACKEND (ASP.NET CORE & SPATIAL)

> **Mã tài liệu:** `SPEC-BE-AI-01`  
> **Phiên bản:** v2.0 (Đồng bộ Data Dictionary v1 & Domain Model v1)  
> **Áp dụng cho:** Kỹ sư Backend (ASP.NET Core, EF Core, SQL Server Spatial), Kỹ sư Data/DevOps, Kỹ sư AI Engine.  
> **Tài liệu tham chiếu:** [RoadGuard_Data_Dictionary_v1.md](file:///c:/Users/ADMIN/Downloads/diagram/RoadGuard_Data_Dictionary_v1.md), [RoadGuard_Domain_Model_v1.md](file:///c:/Users/ADMIN/Downloads/diagram/RoadGuard_Domain_Model_v1.md), [Dac_ta_UseCase_v2.md](file:///c:/Users/ADMIN/Downloads/diagram/Dac_ta_UseCase_v2.md), [User_Stories_Acceptance_Criteria_v2.md](file:///c:/Users/ADMIN/Downloads/diagram/User_Stories_Acceptance_Criteria_v2.md).

---

## 1. TỔNG QUAN KIẾN TRÚC & PHÂN ĐỊNH RANH GIỚI HỆ THỐNG (ADR 003)

Hệ thống RoadGuard áp dụng kiến trúc hướng dịch vụ với ranh giới phân định nghiêm ngặt giữa **Backend Nghiệp Vụ** và **External AI Processing Service**:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                LỚP ỨNG DỤNG NGƯỜI DÙNG                                 │
│  ┌──────────────────────────────────────────┐  ┌────────────────────────────────────┐  │
│  │ Android App (Drone Operator/Repair Crew) │  │  Web Dashboard (PM / Supervisor)   │  │
│  └────────────────────┬─────────────────────┘  └─────────────────┬──────────────────┘  │
└───────────────────────┼──────────────────────────────────────────┼─────────────────────┘
                        │ (Upload MP4 + SRT)                       │ (Review Defect)
                        ▼                                          ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        HỆ THỐNG BACKEND ASP.NET CORE (C#)                              │
│                                                                                        │
│     ┌───────────────────────────────────────────────────────────────────────────┐      │
│     │                    ASP.NET Core Web API (Controllers)                     │      │
│     └─────────────────────┬───────────────────────────────┬─────────────────────┘      │
│                           │                               │                            │
│                           ▼                               ▼                            │
│     ┌───────────────────────────────────────────┐   ┌───────────────────────────┐      │
│     │  Survey & Processing Job Orchestrator     │   │  Object Storage           │      │
│     │  (Điều phối Job, phân khối Block)         │   │  (S3 / MinIO / Blob)      │      │
│     └─────────────────────┬─────────────────────┘   └───────────────────────────┘      │
│                           │                                                            │
│                           ▼                                                            │
│     ┌───────────────────────────────────────────┐   ┌───────────────────────────┐      │
│     │  Spatial Matching & Deduplication Service │──>│  SQL Server + Spatial     │      │
│     │  (So khớp không gian ST_DWithin)          │   │  (Geometry / Geography)   │      │
│     └───────────────────────────────────────────┘   └───────────────────────────┘      │
└───────────────────────────┬────────────────────────────────────────────────────────────┘
                            │ 1. Dispatch Job + ProcessingInputManifest
                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   EXTERNAL AI SERVICE ENGINE (PYTHON / GPU WORKER)                     │
│                                                                                        │
│     ┌───────────────────────────────────────────────────────────────────────────┐      │
│     │                   Message Queue / Background Dispatcher                   │      │
│     └─────────────────────────────────────┬─────────────────────────────────────┘      │
│                                           │                                            │
│                                           ▼                                            │
│     ┌───────────────────────────────────────────────────────────────────────────┐      │
│     │            AI Inference Worker (YOLOv11 + Dynamic Tiling 640x640)         │      │
│     ├─────────────────────────────────────┬─────────────────────────────────────┤      │
│     │  DJI SRT Parser & Realtime GSD      │  Intra-Flight ByteTrack Tracker     │      │
│     └─────────────────────────────────────┴─────────────────────────────────────┘      │
│                                           │                                            │
│                                           │ 2. HTTP Callback Payload AIDetection[]     │
│                                           └────────────────────────────────────►(API)  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Bảng phân định trách nhiệm cốt lõi (Core Boundaries)
| Nghiệp vụ / Tính năng | Bộ phận AI Service Engine (Python) | Bộ phận Backend ASP.NET Core (C#) |
|:---|:---:|:---:|
| **Xử lý Video & Viễn thám** | Trích xuất $2\text{ fps}$, parse SRT, tính GSD thời gian thực, lọc mờ Laplacian. | Lưu trữ file MP4/SRT nguyên bản, quản lý checksum, cấp Presigned URL có thời hạn. |
| **Nhận diện khuyết tật** | Cắt đa tile $640\times 640$, inference YOLOv11, NMS xuyên tile, ước lượng kích thước 2D (mm). | Nhận mảng `AIDetection` thô, lưu trữ bất biến (`immutable`), cấm chỉnh sửa. |
| **Theo dõi đa khung hình (Tracking)** | **Intra-flight Tracking:** Gom các frame liên tiếp của 1 lượt bay bằng ByteTrack $\rightarrow$ 1 quan sát duy nhất. | Không can thiệp vào tracking vi mô trong từng frame video. |
| **Phân vùng & Vùng đệm** | Phân loại `TargetBand` theo vector lý trình; gắn cờ `is_context_overlap = true` ở biên. | Phân chia `ProcessingBlock`, cấp khoảng `primary_offset` và `context_overlap`. |
| **Đối soát trùng lặp qua các chuyến bay** | **KHÔNG LÀM:** AI không truy vấn CSDL lịch sử của các đợt khảo sát trước. | **TRÁCH NHIỆM CHÍNH:** Chạy CSDL Spatial (`ST_DWithin`), sinh `DefectMatch`, đề xuất gộp cho PM. |
| **Vòng đời hư hỏng (`Defect`)** | Chỉ xuất kết quả thô `AIDetection`. | Khởi tạo `Defect (OPEN)`, ghi log xác minh `DefectVerificationLog`, chuyển `VERIFIED`. |

### 1.3 Sơ đồ kiến trúc phân chia trách nhiệm: AI Service Engine vs Backend Spatial

Sơ đồ thể hiện rõ luồng dữ liệu hai chiều và ranh giới nghiệp vụ giữa **AI Service Engine** (xử lý vi mô trong từng chuyến bay) và **Backend Core + Spatial** (xử lý vĩ mô toàn tuyến và đối soát lịch sử):

```text
┌──────────────────────────────────────────────┐                ┌──────────────────────────────────────────────┐
│          AI SERVICE ENGINE (PYTHON)          │                │        BACKEND ASP.NET CORE + SPATIAL        │
├──────────────────────────────────────────────┤                ├──────────────────────────────────────────────┤
│ 1. Intra-Flight Multi-Frame Tracking         │                │ 1. Nhận & Lưu AIDetection bất biến           │
│    - Dùng ByteTrack + Kalman Filter          │                │                                              │
│    - Gom các BBox của cùng 1 ổ gà            │                │ 2. Spatial Deduplication Service             │
│      xuất hiện trên 3-6 frame                │  ───Result──>  │    - Chạy PostGIS/SQL Spatial query          │
│    - Tính kích thước 2D và Georef            │                │    - So khớp bán kính (Radius ≤ 5-8m)        │
│                                              │                │    - Kiểm tra DefectType & TargetBand        │
│ 2. Xuất 1 cụm observation đại diện           │                │                                              │
│    kèm camera_pose và raw_payload            │                │ 3. Tạo bản ghi DefectMatch (AI Match)        │
│                                              │                │                                              │
│                                              │                │ 4. Đề xuất nhóm DefectObservation            │
│                                              │                │                                              │
│                                              │                │ 5. Giao diện PM quyết định gộp/tách          │
└──────────────────────────────────────────────┘                └──────────────────────────────────────────────┘
```

---

## 2. QUY TRÌNH PHÂN KHỐI PROCESSING BLOCK & SINH MANIFEST

Một khảo sát (`Survey`) có thể gồm nhiều video và nhiều lượt bay. Để tối ưu tài nguyên GPU và cô lập sự cố, Backend phân chia dữ liệu thành các khối xử lý (`ProcessingBlock`) độc lập.

```text
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. SurveyDataVersion (Đã kiểm tra Checksum & chuyển trạng thái SERVER_CONFIRMED)        │
└───────────────────────────────────────────┬─────────────────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. Phân đoạn RoadSegment theo phiên bản tim tuyến đường đã công bố (RoadSectionVersion) │
└───────────────────────────────────────────┬─────────────────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ 3. Tạo ProcessingBlock theo cặp định danh: (RoadSegment, TargetBand)                    │
├───────────────────────────────────────────┬─────────────────────────────────────────────┤
│  Block 1: Segment 1 | SURFACE   | Km0+000 - Km0+500 (Đệm Context Overlap 50m)           │
│  Block 2: Segment 1 | LEFT_EDGE | Km0+000 - Km0+500 (Dải biên mép đường bên trái)       │
│  Block 3: Segment 1 | RIGHT_EDGE| Km0+000 - Km0+500 (Dải biên mép đường bên phải)       │
│  Block 4: Segment 2 | SURFACE   | Km0+500 - Km1+000 (Đệm Context Overlap 50m)           │
└───────────────────────────────────────────┬─────────────────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. Đóng gói ProcessingInputManifest (Snapshot bất biến + Checksum SHA256)               │
└───────────────────────────────────────────┬─────────────────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ 5. Khởi tạo ProcessingJob (Status = QUEUED) ──► Dispatch sang AI Engine Worker          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Cấu trúc thực thể `ProcessingBlock` trong CSDL Backend
Theo Data Dictionary v1 (dòng 545-551):
```sql
CREATE TABLE processing_block (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    survey_data_version_id UNIQUEIDENTIFIER NOT NULL,
    block_no INT NOT NULL,
    segment_set_id UNIQUEIDENTIFIER NOT NULL,
    road_segment_id UNIQUEIDENTIFIER NOT NULL,
    target_band VARCHAR(20) NOT NULL, -- 'SURFACE', 'LEFT_EDGE', 'RIGHT_EDGE'
    range_metadata NVARCHAR(MAX) NOT NULL, -- JSONB: offsets, intervals, quality
    created_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT UQ_processing_block UNIQUE (survey_data_version_id, block_no)
);
```

### 2.2 Quy chuẩn `ProcessingInputManifest` gửi sang AI Engine
Backend đóng gói toàn bộ thông tin cần thiết vào JSON Manifest và gửi kèm trong bản tin gọi AI Worker:

```json
{
  "manifest_id": "c8a1b2c3-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
  "processing_job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "processing_block_id": "b3c7e4a1-1234-5678-abcd-000000000002",
  "contract_version": "v1.1.0",
  "road_section_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "road_segment_id": "c1d2e3f4-a5b6-7c8d-9e0f-1a2b3c4d5e6f",
  "target_band": "SURFACE",
  "road_width_m": 3.5,
  "road_centerline_wkt": "LINESTRING(106.660100 10.762500, 106.660500 10.763000)",
  
  "primary_range": {
    "start_station_m": 0.0,
    "end_station_m": 500.0
  },
  "context_overlap": {
    "overlap_start_m": 0.0,
    "overlap_end_m": 50.0
  },
  
  "video_intervals": [
    {
      "interval_id": "f5e4d3c2-b1a0-9f8e-7d6c-5b4a3a2a1a0a",
      "video_file_uri": "https://storage.roadguard.vn/surveys/2026/09/DJI_0057.MP4?token=exp1727500000",
      "video_file_checksum": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "srt_file_uri": "https://storage.roadguard.vn/surveys/2026/09/DJI_0057.SRT?token=exp1727500000",
      "start_time_ms": 12000,
      "end_time_ms": 94000
    }
  ],
  "model_config": {
    "model_version_id": "c3b9e4a1-1234-5678-abcd-000000000001",
    "confidence_threshold": 0.35,
    "iou_threshold": 0.45
  }
}
```

---

## 3. HỢP ĐỒNG DỮ LIỆU ĐẦU RA (AI $\rightarrow$ BACKEND) & LƯU TRỮ BẤT BIẾN

Khi AI Service hoàn tất phân tích, kết quả được đẩy về webhook của Backend ASP.NET Core qua endpoint:  
`POST /api/v1/internal/ai-worker/callback`

### 3.1 Cấu trúc Payload kết quả `AIDetection` (Data Contract)
```json
{
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "processing_block_id": "b3c7e4a1-1234-5678-abcd-000000000002",
  "model_version_id": "c3b9e4a1-1234-5678-abcd-000000000001",
  "status": "COMPLETED",
  "execution_time_seconds": 18.65,
  "total_detections": 1,
  "detections": [
    {
      "id": "e47ac10b-58cc-4372-a567-0e02b2c3d480",
      "defect_type_code": "pothole",
      "target_band": "SURFACE",
      "is_context_overlap": false,
      "confidence": 0.9125,
      "is_2d_estimate": true,
      "estimated_width": 340.5,
      "estimated_length": 0.42,
      "defect_location_method": "OBSERVED_FOOTPRINT",
      "geometry_wkt": "POINT(106.660172 10.762622)",
      "aircraft_location_wkt": "POINT(106.660168 10.762615)",
      "projected_station_m": 142.35,
      "location_uncertainty_m": 1.20,
      "camera_pose_json": {
        "altitude_m": 8.5,
        "gimbal_pitch_deg": -89.8,
        "gsd_mm_per_px": 0.90,
        "frame_index": 360,
        "timestamp_ms": 72000,
        "flight_heading_deg": 42.5,
        "is_forward_flight": true
      },
      "raw_payload": {
        "bbox_xywh_normalized": [0.485, 0.520, 0.082, 0.065],
        "polygon_normalized": [[0.485, 0.520], [0.510, 0.522], [0.525, 0.560], [0.490, 0.558]],
        "track_id": 4,
        "observation_frames_count": 5,
        "crop_image_artifact_uri": "artifacts/crops/job_9b1/det_e47.jpg"
      }
    }
  ]
}
```

### 3.2 Quy tắc lưu trữ bất biến (Immutable Invariant)
1. **Tuyệt đối không sửa bản ghi `AIDetection`:** Sau khi INSERT vào bảng `ai_detection`, bản ghi này trở thành lịch sử khoa học bất biến. Không bao giờ chạy lệnh `UPDATE` hay `DELETE` trên bảng này.
2. **Khởi tạo Defect ở trạng thái sơ bộ (`OPEN`):**
   - Với mỗi detection có `is_context_overlap == false`, Backend tự động tạo một bản ghi `Defect` với `status = 'OPEN'` (Preliminary Defect).
   - Tự động tạo bản ghi `DefectObservation` trỏ tới `ai_detection_id`.
   - **Tuyệt đối cấm Backend tự gán `status = 'VERIFIED'`** — Trạng thái Verified chỉ được phép xác lập khi PM phê duyệt hoặc hoàn thành đo đạc thực tế (`FieldInspectionTask`).

---

## 4. XỬ LÝ VÙNG ĐỆM BIÊN (CONTEXT OVERLAP STITCHING)

Để không làm đứt đoạn một vết nứt dài chạy xuyên qua ranh giới giữa 2 Segment:

```text
  AI Engine Worker             Backend Job Receiver          Spatial Segment Stitcher          SQL Server Spatial
         │                              │                                │                             │
         │── 1. Callback Block 1 ──────►│                                │                             │
         │   (Detection X: overlap=true)│                                │                             │
         │                              │── 2. Lưu AIDetection X ───────┼────────────────────────────►│ (Lưu thô, tạm
         │                              │   (Chờ Block 2 liền kề)        │                             │  chưa tạo Defect)
         │                              │                                │                             │
         │── 3. Callback Block 2 ──────►│                                │                             │
         │   (Detection Y: overlap=true)│                                │                             │
         │                              │── 4. Kích hoạt Stitcher ──────►│                             │
         │                              │                                │── 5. Truy vấn khoảng cách ─►│
         │                              │                                │      giữa Geom X và Geom Y  │
         │                              │                                │◄─ 6. Trả về: dist = 0.8m ───│
         │                              │                                │                             │
         │                              │                                │── 7. Tạo 1 Defect duy nhất ─►│ (Defect vắt qua
         │                              │                                │   • Tạo DefectSegment (1,2) │  2 segment)
         │                              │                                │   • Tạo 2 DefectObservation │
         │                              │                                │                             │
```

---

## 5. THUẬT TOÁN ĐỐI SOÁT TRÙNG LẶP CHUYẾN BAY (CROSS-FLIGHT SPATIAL MATCHER)

Theo nguyên tắc **US-09** và quyết định kiến trúc, **Backend đảm nhận toàn bộ việc so khớp giữa các chuyến bay/kỳ khảo sát**.

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Nhận AIDetection mới (Từ kết quả khảo sát lần bay kỳ này)                │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Chuyển đổi Point WGS84 sang đối tượng hình học không gian (GEOMETRY)    │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Truy vấn CSDL Spatial: Tìm các Defect cũ trong bán kính R ≤ 6.0m         │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
                      /──────────────────────────────\
                     <  Có Defect cũ nào cùng Class?  >
                      \──────────────────────────────/
                                     │
                    ┌────────────────┴────────────────┐
             KHÔNG  │                                 │ CÓ
                    ▼                                 ▼
   ┌─────────────────────────────────┐   /──────────────────────────────\
   │ Gợi ý hành động: NEW            │  <  Độ lệch Estimated Width?      >
   │ Tạo Defect mới (status = OPEN)  │   \──────────────────────────────/
   └─────────────────────────────────┘                │
                                     ┌────────────────┴────────────────┐
                       Chênh lệch ≤ 30%│                                 │ Chênh lệch > 30%
                                      ▼                                 ▼
         ┌─────────────────────────────────┐   ┌─────────────────────────────────┐
         │ Gợi ý hành động: DUPLICATE      │   │ Gợi ý hành động: UPDATE         │
         │ • Lỗi cũ chưa sửa               │   │ • Lỗi phát triển nặng hơn       │
         │ • Tạo bản ghi DefectMatch (AI)  │   │ • Tạo bản ghi DefectMatch       │
         │ • Đề xuất nhóm DefectObservation│   │ • Cảnh báo diễn biến xấu        │
         └────────────────┬────────────────┘   └────────────────┬────────────────┘
                          │                                     │
                          └──────────────────┬──────────────────┘
                                             │
                                             ▼
         ┌───────────────────────────────────────────────────────────────┐
         │ Màn hình Đối Soát trên Web Dashboard (Dành cho PM duyệt)      │
         ├───────────────────────────────┬───────────────────────────────┤
         │ [PM bấm Đồng ý gộp]           │ [PM bấm Tách riêng]           │
         │ DefectMergeDecision = 'MERGE' │ DefectMergeDecision = 'KEEP'  │
         └───────────────────────────────┴───────────────────────────────┘
```

### Câu lệnh mẫu truy vấn không gian trên SQL Server Spatial (T-SQL)
```sql
-- Tìm các hư hỏng đã tồn tại trong bán kính 6.0m cùng tuyến đường
DECLARE @NewGeom GEOMETRY = GEOMETRY::STGeomFromText(@GeometryWKT, 4326);

SELECT 
    d.id AS existing_defect_id,
    d.defect_type_code,
    d.estimated_width,
    d.status,
    @NewGeom.STDistance(d.geometry) * 111319.5 AS distance_meters -- Quy đổi độ sang mét
FROM defect d
WHERE d.road_section_version_id = @RoadSectionVersionId
  AND d.defect_type_code = @NewDefectTypeCode
  AND d.status IN ('OPEN', 'VERIFIED')
  AND @NewGeom.STDistance(d.geometry) * 111319.5 <= 6.0
ORDER BY distance_meters ASC;
```

---

## 6. CƠ CHẾ IDEMPOTENCY, THỬ LẠI & PHÂN LOẠI LỖI (RELIABILITY)

### 6.1 Khóa chống trùng lặp (Idempotency Key)
Để đảm bảo Backend có thể gọi lại mà không bị sinh detection trùng lặp khi mạng chập chờn:
$$\text{idempotency\_key} = \text{SHA256}(\text{ProcessingBlockId} + \text{ModelVersionId} + \text{ManifestChecksum})$$

- Nếu AI Service nhận lại request có cùng `idempotency_key`, AI Service trả lại ngay kết quả đã lưu trong Cache/DB mà không tốn GPU chạy lại.

### 6.2 Phân loại lỗi chuẩn mực giữa Backend & AI
Backend cần căn cứ vào mã lỗi trả về từ AI Service để đưa ra hành vi đúng:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│               LỖI PHÁT SINH TRONG QUÁ TRÌNH PHÂN TÍCH                   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
                      /─────────────────────────────\
                     <   Phân loại lỗi từ AI Worker  >
                      \─────────────────────────────/
                                     │
                    ┌────────────────┴────────────────┐
                    │                                 │
                    ▼                                 ▼
     ┌─────────────────────────────┐   ┌─────────────────────────────┐
     │    INFRASTRUCTURE_ERROR     │   │         DATA_ERROR          │
     ├─────────────────────────────┤   ├─────────────────────────────┤
     │ • GPU Out-of-Memory (OOM)   │   │ • File video MP4 hỏng       │
     │ • Worker Timeout            │   │ • Mất file phụ đề SRT       │
     │ • Mất kết nối mạng tạm thời │   │ • Tỷ lệ nhòe mờ > 30%       │
     ├─────────────────────────────┤   ├─────────────────────────────┤
     │ HÀNH VI CỦA BACKEND:        │   │ HÀNH VI CỦA BACKEND:        │
     │ ✅ CHO PHÉP THỬ LẠI (RETRY) │   │ ❌ TUYỆT ĐỐI KHÔNG RETRY!   │
     │ • Áp dụng Exponential       │   │ • Chuyển Job sang FAILED    │
     │   Backoff: 1m, 5m, 15m      │   │ • Gửi thông báo PM yêu cầu  │
     │ • Tối đa 3 lần thử lại      │   │   bay bổ sung (KS11)        │
     └─────────────────────────────┘   └─────────────────────────────┘
```

---

## 7. CÁC QUY TẮC RÀNG BUỘC BẤT BIẾN CỦA BACKEND (DOMAIN INVARIANTS)

1. **Không ghi đè dữ liệu lịch sử:** Thay đổi thuật toán hay nâng cấp phiên bản mô hình AI (`AIModelVersion`) **tuyệt đối không cascade update** lên các bản ghi `AIDetection` cũ. Mọi báo cáo lịch sử phải giữ nguyên phiên bản đã chạy tại thời điểm đó.
2. **Không tự động xác minh Defect:** Kết quả AI sinh ra chỉ là dữ liệu thô. Chỉ người dùng có vai trò `PM` hoặc kết quả đo thực địa từ `Repair Crew` mới được chuyển trạng thái `status = 'VERIFIED'`.
3. **Kiểm tra Checksum trước khi Dispatch:** Chỉ những video đã đạt `SERVER_CONFIRMED` và vượt qua kiểm tra mã băm SHA256 mới được đưa vào `ProcessingInputManifest`.
4. **Bảo mật dữ liệu (PII):** Payload gửi sang AI Worker chỉ chứa thông tin kỹ thuật hình ảnh và tọa độ tim tuyến. **Tuyệt đối không gửi thông tin người dùng, chi phí dự toán hay thông tin người dân phản ánh (Reporter PII)** sang dịch vụ AI.

---

## 8. USER STORIES DÀNH CHO ĐỘI BACKEND (ACCEPTANCE CRITERIA)

### US-06: Tiếp nhận dữ liệu, tạo Job và Dispatch Worker
> **Là một** Hệ thống Backend,  
> **Tôi muốn** xác thực tính toàn vẹn của tệp video/SRT, lưu trữ bền vững Manifest và điều phối Job phân tích bất đồng bộ,  
> **Để** đảm bảo hệ thống không bị nghẽn I/O và mọi tác vụ AI đều có khả năng tái hiện 100%.

```
Given: Drone Operator đã tải lên đầy đủ tệp MP4 và SRT của một lượt khảo sát
When: Backend nhận được yêu cầu xác nhận dữ liệu
Then:
  - Backend kiểm tra Checksum SHA256 của từng tệp và cập nhật SurveyDataVersion sang SERVER_CONFIRMED.
  - Tự động chia các ProcessingBlock dựa trên RoadSegment và TargetBand đã chọn.
  - Tạo bản ghi ProcessingInputManifest bất biến trong CSDL SQL Server.
  - Đẩy Job vào hàng đợi (Message Queue) và trả về HTTP 202 Accepted kèm JobId ngay lập tức (ngoài vòng đời request người dùng).
```

---

### US-08: Tiếp nhận kết quả AI và khởi tạo danh sách Preliminary Defect
> **Là một** Hệ thống Backend,  
> **Tôi muốn** tiếp nhận kết quả AIDetection bất biến từ AI Worker và tự động khởi tạo danh sách khuyết tật sơ bộ (OPEN),  
> **Để** Project Manager có đầy đủ bằng chứng hình ảnh và vị trí để tiến hành thẩm định.

```
Given: AI Worker đã hoàn thành phân tích một ProcessingBlock và gọi callback về Backend
When: Backend nhận payload kết quả AIDetection[]
Then:
  - Kiểm tra tính hợp lệ của JobId và Checksum đầu vào.
  - Lưu toàn bộ các bản ghi vào bảng ai_detection (đảm bảo tính bất biến, không trigger update).
  - Với các detection có is_context_overlap == false: Tự động tạo bản ghi defect với status = 'OPEN'.
  - Lưu đầy đủ thông tin: geometry WGS84, projected_station_m, camera_pose_json, và đường dẫn ảnh crop artifact.
  - Cập nhật trạng thái ProcessingJob sang COMPLETED và gửi thông báo Webhook/SignalR cho Web Dashboard của PM.
```

---

### US-09: Tự động đối soát không gian và gợi ý gộp khuyết tật trùng (Cross-Flight Matching)
> **Là một** Hệ thống Backend,  
> **Tôi muốn** tự động so khớp không gian giữa các phát hiện mới với các hư hỏng đã ghi nhận ở các kỳ trước,  
> **Để** gợi ý cho PM các trường hợp trùng lặp hoặc theo dõi mức độ phát triển của vết nứt theo thời gian.

```
Given: Một tập hợp AIDetection mới vừa được ghi nhận vào CSDL
When: Backend Spatial Matcher Service thực thi tác vụ hậu xử lý
Then:
  - Thực hiện không gian hóa (Spatial Query) tìm kiếm các Defect hiện có trong phạm vi bán kính ≤ 6.0m.
  - Nếu phát hiện trùng khớp về loại lỗi và vị trí: Tạo bản ghi DefectMatch với match_method = 'AI' và match_confidence tương ứng.
  - Sinh đề xuất liên kết DefectObservation hiển thị trên giao diện rà soát của PM.
  - Khi PM bấm "Gộp": Cập nhật DefectMergeDecision = 'MERGE', liên kết detection mới vào Defect cũ và ghi nhật ký kiểm chứng DefectVerificationLog (không xóa bản ghi detection nguồn).
```

---

# 📋 BẢNG CHECKLIST SẴN SÀNG TÍCH HỢP CHO ĐỘI BACKEND

- [ ] Đã tạo bảng CSDL: `processing_block`, `processing_job`, `processing_input_manifest`, `ai_detection`, `defect_observation`, `defect_match`.
- [ ] Cấu hình kiểu dữ liệu không gian `GEOMETRY` / `GEOGRAPHY` (SRID 4326) trên SQL Server Spatial.
- [ ] Xây dựng Endpoint nhận Callback: `POST /api/v1/internal/ai-worker/callback` có xác thực Token nội bộ.
- [ ] Viết Service tính khoảng cách `STDistance` để tự động phát hiện `DUPLICATE` trong bán kính $6.0\text{m}$.
- [ ] Đảm bảo cơ chế Transaction an toàn: Nhận callback $\rightarrow$ Ghi `ai_detection` $\rightarrow$ Khởi tạo `defect (OPEN)` $\rightarrow$ Commit toàn vẹn.
