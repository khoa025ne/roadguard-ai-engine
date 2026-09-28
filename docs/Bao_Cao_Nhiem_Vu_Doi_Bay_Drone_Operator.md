# 🚁 ROADGUARD — BÁO CÁO NHIỆM VỤ & QUY CHUẨN THAO TÁC ĐỘI BAY (DRONE OPERATOR)

> **Mã tài liệu:** `SOP-DRONE-01`  
> **Phiên bản:** v2.0 (Đồng bộ kiến trúc RoadGuard 2026)  
> **Áp dụng cho:** Kỹ thuật viên vận hành Flycam (Drone Operator), Đội trưởng khảo sát hiện trường, Quản lý dự án (PM).  
> **Tài liệu tham chiếu:** [Dac_ta_UseCase_v2.md](file:///c:/Users/ADMIN/Downloads/diagram/Dac_ta_UseCase_v2.md), [RoadGuard_Domain_Model_v1.md](file:///c:/Users/ADMIN/Downloads/diagram/RoadGuard_Domain_Model_v1.md), [User_Stories_Acceptance_Criteria_v2.md](file:///c:/Users/ADMIN/Downloads/diagram/User_Stories_Acceptance_Criteria_v2.md).

---

## 1. TỔNG QUAN VAI TRÒ & PHẠM VI TRÁCH NHIỆM (ROLE & SCOPE)

### 1.1 Vị trí của Drone Operator trong hệ thống RoadGuard
Trong hệ sinh thái RoadGuard, **Drone Operator** là mắt xích đầu tiên quyết định tính sống còn của dữ liệu. Trách nhiệm cốt lõi là thu thập hình ảnh viễn thám và dữ liệu tọa độ thời gian thực của các tuyến đường bê-tông nông thôn với độ sắc nét cao nhất, đảm bảo mô hình AI nhận diện chính xác các vết nứt chỉ từ $1.5\text{mm} - 2.0\text{mm}$.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        HIỆN TRƯỜNG KHẢO SÁT (DRONE OPERATOR)                           │
│                                                                                        │
│  ┌───────────────────────────┐         ┌───────────────────────────┐                   │
│  │ 1. Nhận lệnh bay trên App │────────►│ 2. Khảo sát & Test drone  │                   │
│  └───────────────────────────┘         └─────────────┬─────────────┘                   │
│                                                      │                                 │
│                                                      ▼                                 │
│  ┌───────────────────────────┐         ┌───────────────────────────┐                   │
│  │ 4. Cắm thẻ nhớ OTG vào ĐT │◄────────│ 3. Bay quay 2.7K + SRT    │                   │
│  └─────────────┬─────────────┘         └───────────────────────────┘                   │
│                │                                                                       │
│                ▼                                                                       │
│  ┌───────────────────────────┐          (Không đạt)    ┌───────────────────────────┐   │
│  │ 5. Chạy Quality Gate      │────────────────────────►│ 7. Bay bổ sung tại chỗ    │   │
│  │    (Lọc mờ, GPS, Độ cao)  │                         └─────────────┬─────────────┘   │
│  └─────────────┬─────────────┘                                       │                 │
│                │ (Đạt chuẩn)                                         │ (Bay bù xong)   │
│                ▼                                                     ▼                 │
│  ┌───────────────────────────┐                         ┌───────────────────────────┐   │
│  │ 6. Tải dữ liệu lên Server │                         │ Nạp thẻ nhớ kiểm tra lại  │   │
│  └─────────────┬─────────────┘                         └───────────────────────────┘   │
└────────────────┼───────────────────────────────────────────────────────────────────────┘
                 │ (Upload hoàn tất)
                 ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        HỆ THỐNG TRUNG TÂM (SERVER & AI)                                │
│                                                                                        │
│  ┌───────────────────────────┐         ┌───────────────────────────┐                   │
│  │ Backend kiểm tra Checksum │────────►│ AI Worker bóc tách nứt/gà │                   │
│  │ Gán SERVER_CONFIRMED      │         │ Đo đạc 2D kích thước (mm) │                   │
│  └───────────────────────────┘         └─────────────┬─────────────┘                   │
│                                                      │                                 │
│                                                      ▼                                 │
│                                        ┌───────────────────────────┐                   │
│                                        │ PM thẩm định trên Web Dash│                   │
│                                        └───────────────────────────┘                   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Ranh giới trách nhiệm (System Boundaries)
- **THUỘC phạm vi của Đội bay:**
  - Tự chuẩn bị thiết bị bay (DJI Mini 2 SE hoặc tương đương), pin, phụ kiện an toàn.
  - Tự lập lịch bay, điều khiển bay bằng ứng dụng bay chuyên dụng (DJI Fly).
  - Sử dụng ứng dụng **RoadGuard Android App** để nhận việc, kiểm tra chất lượng video tại hiện trường (Offline/Online) và tải dữ liệu lên máy chủ.
  - Thực hiện bay bổ sung kịp thời khi nhận được yêu cầu (`SupplementarySurveyRequest`).
- **KHÔNG THUỘC phạm vi:**
  - Ứng dụng RoadGuard **KHÔNG trực tiếp điều khiển hay can thiệp vào tín hiệu lái của Flycam**.
  - Đội bay không tự ý kết luận tuyến đường "không có lỗi" (`NoDefect`) — quyết định thuộc về PM.

### 1.3 Sơ đồ quy trình phối hợp: Đội Bay Hiện Trường vs Hệ Thống Trung Tâm

```text
┌──────────────────────────────────────────────┐                ┌──────────────────────────────────────────────┐
│  ĐỘI BAY (DRONE OPERATOR) — THAO TÁC HIỆN TRƯỜNG │            │     HỆ THỐNG TRUNG TÂM (AI SERVICE + BACKEND)│
├──────────────────────────────────────────────┤                ├──────────────────────────────────────────────┤
│ 1. Bay & Thu hình hiện trường (SOP)          │                │ 1. Tiếp nhận & Phân khối                     │
│    - Độ cao H = 8m - 10m (Gimbal -90°)       │                │    - Xác thực Checksum toàn vẹn              │
│    - Vận tốc bay đều 1.0 - 1.5 m/s           │                │    - Chia ProcessingBlock (Segment, Band)    │
│    - Quay video 2.7K MP4 + Bật SRT           │                │                                              │
│                                              │  ──Dữ liệu──>  │ 2. AI Engine phân tích đa Tile 640x640       │
│ 2. Sao chép & Kiểm định tại chỗ              │   (MP4 + SRT)  │    - Bóc tách vết nứt, ổ gà, nứt mép lề      │
│    - Cắm thẻ nhớ OTG vào điện thoại Android  │                │    - Tracking ByteTrack & Đo đạc 2D (mm)     │
│    - Chạy Quality Gate lọc mờ Laplacian ≥100 │                │                                              │
│    - Kiểm tra GPS & Độ cao H ≤ 20m           │  ◄──Yêu cầu──  │ 3. Hậu xử lý & Thẩm định PM                  │
│                                              │   bay bổ sung  │    - So khớp không gian (Radius ≤ 5-8m)      │
│ 3. Tải dữ liệu lên máy chủ                   │   (nếu thiếu)  │    - Lập danh mục hư hỏng sơ bộ (OPEN)       │
│    - Tải nguyên vẹn cặp tệp MP4 + SRT        │                │    - PM thẩm định phê duyệt                  │
│    - Chờ phản hồi SERVER_CONFIRMED           │                │                                              │
└──────────────────────────────────────────────┘                └──────────────────────────────────────────────┘
```

### 1.4 Dữ liệu của Đội bay được AI và Backend xử lý như thế nào?

Nhằm giúp Đội bay hiểu rõ tại sao thông số bay (độ cao, tốc độ, góc gimbal) lại quan trọng đến từng milimet, sơ đồ dưới đây mô tả cách AI Engine và Backend bóc tách video thô của phi công:

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

## 2. QUY CHUẨN THIẾT BỊ & THÔNG SỐ BAY CHI TIẾT (FLIGHT SOP)

Thiết bị tham chiếu tiêu chuẩn: **DJI Mini 2 SE** (Cảm biến 1/2.3" CMOS, độ phân giải 2.7K $2720 \times 1530$, tiêu cự tương đương $24\text{mm}$, tiêu cự quang học thực $4.26\text{mm}$, kích thước cảm biến $6.17\text{mm} \times 4.55\text{mm}$).

### 2.1 Độ cao bay & Độ phân giải mặt đất (GSD - Ground Sampling Distance)
Độ cao bay quyết định trực tiếp tới việc AI có nhìn thấy vết nứt hay không. Công thức tính GSD quang học:
$$\text{GSD} = \frac{\text{Độ cao bay (m)} \times 1000 \times 6.17\text{ mm}}{4.26\text{ mm} \times 2720\text{ px}} \approx \text{Độ cao bay (m)} \times 0.10645 \quad (\text{mm/pixel})$$

```text
┌────────────────────────────────────────┐                 ┌────────────────────────────────────────┐
│              ĐỘ CAO BAY                │                 │       NĂNG LỰC PHÁT HIỆN CỦA AI        │
├────────────────────────────────────────┤                 ├────────────────────────────────────────┤
│  6m - 8m   (GSD: 0.64 - 0.85 mm/px)    │  ─────────────► │  Vết nứt chân chim mảnh ≥ 1.5mm - 2mm  │
│  10m       (GSD: 1.07 mm/px)           │  ─────────────► │  Vết nứt chuẩn ≥ 3mm + Ổ gà + Bong tróc│
│  12m - 15m (GSD: 1.28 - 1.60 mm/px)    │  ─────────────► │  Chỉ phát hiện nứt lớn ≥ 5mm + Ổ gà    │
│  > 20m     (GSD > 2.13 mm/px)          │  ─────────────► │  ❌ MẤT CHI TIẾT - Cảnh báo HIGH_ALT    │
└────────────────────────────────────────┘                 └────────────────────────────────────────┘
```

| Độ cao ($H$) | GSD thực tế | Bề rộng vệt quan sát (Footprint) | Loại hư hỏng phát hiện tốt nhất | Đánh giá & Khuyến nghị |
|:---:|:---:|:---:|:---|:---|
| **$8\text{m}$** | **$0.85\text{ mm/px}$** | $2.32\text{m}$ | Vết nứt sợi tóc mảnh từ $2\text{mm}$, xói lở mép lề | ⭐️ **Khuyến nghị vàng cho nứt mặt đường** |
| **$10\text{m}$** | **$1.07\text{ mm/px}$** | $2.91\text{m}$ | Vết nứt từ $3\text{mm}$, ổ gà, nứt chân chim, lún mép | ✅ **Chuẩn mực khảo sát toàn tuyến** |
| **$15\text{m}$** | **$1.60\text{ mm/px}$** | $4.36\text{m}$ | Ổ gà lớn, bong tróc bê-tông, nứt vỡ mảng lớn | ⚠️ Giới hạn tối đa (chỉ dùng khi cây cao) |
| **$> 20\text{m}$** | **$> 2.14\text{ mm/px}$** | $> 5.82\text{m}$ | Chỉ thấy ổ gà lớn, hoàn toàn mất vết nứt | ❌ **BỊ TỪ CHỐI — Phải bay lại** |

---

### 2.2 Vận tốc bay & Độ chồng lấn khung hình (Frame Overlap)
Hệ thống AI Engine bóc tách khung hình với tần suất cố định **$2\text{ fps}$** (mỗi $0.5\text{ giây}$ lấy 1 frame). Để thuật toán bám vết nứt (ByteTrack) không bị mất dấu giữa 2 khung hình liên tiếp, **độ phủ gối đầu (overlap) bắt buộc phải đạt $\ge 60\%$**.

```text
┌───────────────────────────────────┐
│ Frame 1 (Thời điểm t = 0.0s)      │
│ ┌───────────────────────────────┐ │
│ │                               │ │
│ │   ┌───────────────────────┐   │ │
│ │   │  Ổ gà / Vết nứt       │   │ │
│ └───┼───────────────────────┼───┘ │
└─────┼───────────────────────┼─────┘
      │ VÙNG GỐI ĐẦU OVERLAP  │ (Drone bay tiến v = 1.2 m/s, dịch chuyển 0.6m)
┌─────┼───────────────────────┼─────┐
│ ┌───┼───────────────────────┼───┐ │
│ │   │  Ổ gà / Vết nứt       │   │ │
│ │   └───────────────────────┘   │ │
│ │                               │ │
│ └───────────────────────────────┘ │
│ Frame 2 (Thời điểm t = 0.5s)      │
└───────────────────────────────────┘
   ==> Tỷ lệ Overlap ≥ 63.4%: AI bám dính đối tượng liên tục qua 3-6 frame!
```

| Vận tốc bay ($v$) | Khoảng cách tiến / $0.5\text{s}$ | Độ gối đầu Overlap | Đánh giá vận hành |
|:---:|:---:|:---:|:---|
| **$\le 1.0\text{ m/s}$ ($3.6\text{ km/h}$)** | $\le 0.50\text{m}$ | $\ge 69.5\%$ | ⭐️ **Cực tốt:** Ảnh không bị nhòe động, AI bám đối tượng qua 5-7 frame. |
| **$1.0 – 1.5\text{ m/s}$ ($5.4\text{ km/h}$)** | $0.50 – 0.75\text{m}$ | **$54.3\% – 69.5\%$** | ✅ **Khuyến nghị vận hành chuẩn:** Cân bằng hoàn hảo tốc độ và độ nét. |
| **$1.5 – 2.5\text{ m/s}$ ($9.0\text{ km/h}$)** | $0.75 – 1.25\text{m}$ | $23.8\% – 54.3\%$ | ⚠️ **Cảnh báo:** Có nguy cơ nhòe mờ khi ánh sáng yếu, dễ sót vết nứt ngắn. |
| **$> 3.0\text{ m/s}$ ($10.8\text{ km/h}$)** | $> 1.50\text{m}$ | $< 8.5\%$ | ❌ **NGHIÊM CẤM:** Mất dấu đối tượng, hệ thống sẽ đánh rớt dữ liệu. |

---

### 2.3 Quy tắc hướng bay & Chiều tăng lý trình (BẮT BIẾN)
> 🔴 **ĐIỀU CỐT LÕI CẦN GHI NHỚ:**
> Trong hệ thống RoadGuard: **Trái / Phải được định nghĩa theo chiều tăng lý trình ($Km0 \rightarrow Km1 \rightarrow Km...$), TUYỆT ĐỐI KHÔNG ĐỔI KHI DRONE BAY NGƯỢC CHIỀU.**

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│          CHIỀU TĂNG LÝ TRÌNH THIẾT KẾ ĐƯỜNG (Km 0+000 ──────────────────► Km 1+000)    │
│  ┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐ │
│  │   LỀ TRÁI (LEFT_EDGE)   │  │   LÒNG ĐƯỜNG (SURFACE)  │  │   LỀ PHẢI (RIGHT_EDGE)  │ │
│  └─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────┘
                               │                                         │
        ┌──────────────────────┘                                         └──────────────────────┐
        ▼                                                                                       ▼
┌──────────────────────────────────────────────┐        ┌──────────────────────────────────────────────┐
│ TRƯỜNG HỢP 1: DRONE BAY XUÔI CHIỀU LÝ TRÌNH  │        │ TRƯỜNG HỢP 2: DRONE BAY NGƯỢC CHIỀU LÝ TRÌNH │
│              (Km 0 ────────► Km 1)           │        │              (Km 1 ────────► Km 0)           │
├──────────────────────────────────────────────┤        ├──────────────────────────────────────────────┤
│ • Bên Trái màn hình camera = LỀ TRÁI         │        │ • Bên Trái màn hình camera = LỀ PHẢI         │
│   (LEFT_EDGE theo lý trình)                  │        │   (RIGHT_EDGE theo lý trình)                 │
│ • Bên Phải màn hình camera = LỀ PHẢI         │        │ • Bên Phải màn hình camera = LỀ TRÁI         │
│   (RIGHT_EDGE theo lý trình)                 │        │   (LEFT_EDGE theo lý trình)                  │
└──────────────────────────────────────────────┘        └──────────────────────────────────────────────┘
```

- **Khi bay Xuôi lý trình:** Bên trái màn hình điện thoại là `LEFT_EDGE`, bên phải là `RIGHT_EDGE`.
- **Khi bay Ngược lý trình:** Bên trái màn hình điện thoại là `RIGHT_EDGE`, bên phải là `LEFT_EDGE`.
- **Lưu ý:** Drone Operator không cần tự đảo nhãn, nhưng **phải bay thẳng theo trục tim đường**, tránh bay lượn vòng vèo zíc-zắc làm lệch vector tính toán của AI.

---

### 2.4 Chiến lược bay đa lượt theo dải mục tiêu (Target Bands Strategy)
Domain Model quy định: *"Một SurveyWorkItem có nhiều band; không bắt buộc ba chuyến bay"*. Đội bay áp dụng linh hoạt theo độ rộng mặt đường:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        ĐƯỜNG BÊ-TÔNG NÔNG THÔN HẸP (BỀ RỘNG ≤ 3.5M)                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  1 LƯỢT BAY DUY NHẤT:                                                                  │
│  • Bay chính giữa tim đường, độ cao H = 10m, Gimbal chúi thẳng -90°                    │
│  • Vệt quét Footprint rộng 2.91m bao trọn cả lòng đường (SURFACE) lẫn 2 bên mép lề     │
└────────────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────────────┐
│              ĐƯỜNG BÊ-TÔNG RỘNG (> 3.5M - 5.0M) HOẶC CỎ RẬM CHE KHUẤT LỀ              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  LƯỢT 1 (SURFACE):   Bay chính giữa tim đường H = 10m (Khảo sát mặt đường tổng quan)   │
│  LƯỢT 2 (LEFT_EDGE): Bay lệch sang trái 1.2m - 1.5m, H = 8m (Soi sát mép lề trái)     │
│  LƯỢT 3 (RIGHT_EDGE):Bay lệch sang phải 1.2m - 1.5m, H = 8m (Soi sát mép lề phải)     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. QUY TRÌNH NẠP DỮ LIỆU & KIỂM TRA CHẤT LƯỢNG TẠI HIỆN TRƯỜNG (QUALITY GATE)

Drone Operator không được phép rời khỏi hiện trường khi chưa chạy bước kiểm tra này trên RoadGuard Android App.

```text
  Phi công (Operator)       RoadGuard Android App          Bộ nhớ điện thoại           Backend ASP.NET Core
          │                           │                            │                            │
          │── 1. Cắm thẻ nhớ OTG ────►│                            │                            │
          │                           │── 2. Copy MP4 + SRT ──────►│                            │
          │                           │   (Bắt buộc cùng tên file) │                            │
          │                           │◄─ 3. Copy hoàn tất ────────│                            │
          │                           │                            │                            │
          │── 4. Bấm "Kiểm định" ────►│                            │                            │
          │                           │── 5. Kiểm tra thời lượng   │                            │
          │                           │── 6. Parse SRT (GPS, H≤20m)│                            │
          │                           │── 7. Lọc mờ Laplacian ≥100 │                            │
          │                           │                            │                            │
   [NẾU ĐẠT CHUẨN (≥ 70% rõ nét)]     │                            │                            │
          │◄─ 8. Báo XANH: Đạt chuẩn ─│                            │                            │
          │── 9. Bấm "Tải lên" ──────►│                            │                            │
          │                           │── 10. Tải video + SRT ─────┼───────────────────────────►│
          │                           │◄─ 11. SERVER_CONFIRMED ────┼────────────────────────────│
          │◄─ 12. Báo thành công ─────│   (Xác nhận toàn vẹn)      │                            │
          │                           │                            │                            │
   [NẾU KHÔNG ĐẠT (Mờ/Mất GPS >30%)]  │                            │                            │
          │◄─ 8b. Báo ĐỎ: Cảnh báo ───│                            │                            │
          │   (Đoạn Km0+200 bị mờ)    │                            │                            │
          │── 9b. Bay bổ sung tại chỗ │                            │                            │
```

### Tiêu chí nghiệm thu tại chỗ của Quality Gate (Bảng kiểm tra nhanh)
| Hạng mục kiểm tra | Tiêu chuẩn ĐẠT | Xử lý khi KHÔNG ĐẠT |
|:---|:---|:---|
| **Cặp tệp viễn thám** | Tên file video `DJI_xxxx.MP4` và `DJI_xxxx.SRT` phải trùng khớp 100%. | Đổi lại tên file hoặc xuất lại SRT từ DJI Fly trước khi nạp. |
| **Độ rõ nét (Blur Check)** | Phương sai Laplacian $\ge 100.0$. Tỷ lệ frame mờ $< 30\%$. | Giảm vận tốc bay xuống $1.0\text{ m/s}$, lau sạch ống kính camera. |
| **Độ cao an toàn** | Độ cao hiển thị trong SRT $H \le 20\text{m}$ (tối ưu $8 - 10\text{m}$). | Hạ độ cao drone và thực hiện bay lại phân đoạn đó. |
| **Tín hiệu GPS/SRT** | Không bị mất tín hiệu GPS liên tục quá $3\text{ giây}$. | Nếu dưới tán cây rậm: bay chậm lại hoặc đợi tín hiệu vệ tinh $\ge 10$ tinh. |
| **Góc nghiêng Gimbal** | Góc Pitch bắt buộc chúi thẳng $-90^\circ$ ($\pm 3^\circ$). | Tuyệt đối không để góc chéo $-45^\circ$ hoặc $-60^\circ$ (sai lệch GSD). |

---

## 4. CÁC QUY TẮC RÀNG BUỘC BẤT BIẾN CỦA ĐỘI BAY (INVARIANTS)

1. **Quy tắc bảo tồn dữ liệu gốc:** Tuyệt đối **không format thẻ nhớ** hoặc xóa video trên Flycam cho đến khi RoadGuard App thông báo trạng thái `SERVER_CONFIRMED`.
2. **Quy tắc tính nguyên vẹn tệp:** Tuyệt đối không chỉnh sửa, cắt ghép (edit/trim), re-encode hoặc đổi định dạng video bằng các app bên thứ 3 (CapCut, v.v.) vì sẽ làm gãy chuỗi thời gian đồng bộ với file `.SRT`.
3. **Quy tắc phân biệt Hoãn vs Hủy:**
   - Trời mưa/Gió bão: Chọn `Hoãn khảo sát (Postponed)` trên App kèm lý do thời tiết.
   - Chỉ PM mới có quyền `Hủy yêu cầu khảo sát (Cancelled)` khi chưa có dữ liệu nộp lên máy chủ.
4. **Quy tắc an toàn hành lang bay:** Tránh xa dây điện cao thế, đường dây viễn thông nông thôn cắt ngang đường; luôn duy trì đường truyền Visual Line of Sight (VLOS).

---

## 5. USER STORIES DÀNH CHO ĐỘI BAY (ACCEPTANCE CRITERIA)

### US-05: Tiếp nhận và Quản lý Nhiệm vụ Bay Khảo sát
> **Là một** Drone Operator,  
> **Tôi muốn** xem danh sách các tuyến đường được giao trên bản đồ số của RoadGuard App,  
> **Để** tôi chủ động lên kế hoạch di chuyển và thực hiện chuyến bay đúng phạm vi yêu cầu.

```
Given: Drone Operator đã đăng nhập vào ứng dụng RoadGuard Android
When: Mở mục "Nhiệm vụ khảo sát" và chọn một SurveyRequest có trạng thái "Mới giao"
Then:
  - Hệ thống hiển thị chi tiết: Tên tuyến đường, lý trình bắt đầu (Km Start), lý trình kết thúc (Km End), bản đồ tim tuyến (LineString) và TargetBand yêu cầu (SURFACE/EDGE).
  - Drone Operator có thể bấm "Tiếp nhận" (chuyển sang "Đã nhận") hoặc bấm "Từ chối" kèm lý do chính đáng (thiết bị hỏng, đường bị cấm bay quân sự).
  - Khi đã bấm "Tiếp nhận", hệ thống khóa nút từ chối; muốn hủy phải liên hệ PM.
```

---

### US-06: Nhập Thẻ Nhớ, Kiểm Định Chất Lượng & Tải Dữ Liệu
> **Là một** Drone Operator,  
> **Tôi muốn** cắm thẻ nhớ máy bay vào điện thoại để ứng dụng tự sao chép, tự thẩm định chất lượng video và tự đồng bộ khi có mạng,  
> **Để** tôi biết chắc chắn dữ liệu của mình đạt chuẩn trước khi rời hiện trường.

```
Given: Drone Operator đã bay xong và cắm thẻ nhớ/đầu đọc vào điện thoại
When: Chọn tệp video vừa quay trong danh sách phát hiện
Then:
  - Ứng dụng tự động tìm tệp .SRT đi kèm có cùng tên. Nếu thiếu SRT, hiện thông báo cảnh báo buộc bổ sung.
  - Ứng dụng sao chép tệp vật lý vào thư mục bảo mật của ứng dụng (không phụ thuộc vào việc rút thẻ nhớ ra sau đó).
  - Chạy module kiểm tra tại chỗ: Kiểm tra độ nét Laplacian (ngưỡng 100), kiểm tra độ cao bay và tọa độ GPS trong SRT.
  - Nếu tỷ lệ mờ < 30%: Cho phép bấm "Xác nhận & Tải lên". Dữ liệu được đưa vào hàng đợi Upload tự động (hỗ trợ tiếp tục tải khi mất mạng giữa chừng).
```

---

### US-07: Tiếp Nhận Yêu Cầu Bay Bổ Sung (Supplementary Survey)
> **Là một** Drone Operator,  
> **Tôi muốn** nhận được cảnh báo các đoạn đường bị lỗi dữ liệu kèm vị trí chính xác trên bản đồ,  
> **Để** tôi thực hiện bay bù ngay lập tức mà không phải khảo sát lại toàn bộ tuyến đường.

```
Given: Một lần khảo sát có phân đoạn bị Quality Gate đánh giá "Không đạt" hoặc PM yêu cầu bay bổ sung
When: Drone Operator mở thông báo "Yêu cầu bay bổ sung"
Then:
  - Bản đồ làm nổi bật đúng phân đoạn bị thiếu (Ví dụ: Từ Km 0+350 đến Km 0+450).
  - Hệ thống hiển thị lý do cụ thể: "Hình ảnh bị rung mờ do gió" hoặc "Độ cao bay vượt quá 20m".
  - Drone Operator tiến hành bay lại đúng đoạn đó và nộp tệp mới; hệ thống tự động đánh dấu tệp này thuộc lượt bay bổ sung mà không ghi đè video gốc lần 1.
```

---

# 📋 BẢNG CHECKLIST BỎ TÚI CHO PHI CÔNG (IN RA TRƯỚC KHI RA ĐỒNG)

- [ ] Pin Flycam $\ge 3$ quả sạc đầy 100%, pin tay cầm $\ge 80\%$.
- [ ] Điện thoại Android cài sẵn app RoadGuard bản mới nhất, bộ nhớ trống $\ge 15\text{GB}$.
- [ ] Đã bật tùy chọn **"Video Subtitles" (File .SRT)** trong cài đặt camera DJI Fly.
- [ ] Gimbal camera đã khóa góc chúc thẳng đứng **$-90^\circ$ (Nadir View)**.
- [ ] Bay ở độ cao chuẩn **$8\text{m} - 10\text{m}$**, vận tốc bay giữ đều **$1.0 - 1.5\text{ m/s}$**.
- [ ] Hạ cánh: Cắm thẻ nhớ vào điện thoại, chạy kiểm tra Quality Gate trên RoadGuard App.
- [ ] Nhận thông báo **ĐẠT (PASSED)** trên màn hình mới thu dọn thiết bị ra về!
