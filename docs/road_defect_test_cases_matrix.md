# 📋 BỘ MA TRẬN TEST CASE TOÀN DIỆN KHUYẾT TẬT ĐƯỜNG BỘ & NGOẠI CẢNH — ROADGUARD AI
> **Dự án:** RoadGuard / CrackScan VN — Hệ thống AI Khảo sát & Giám định Khuyết tật Cầu đường Nông thôn qua Video Drone  
> **Phiên bản tài liệu:** v2.0.0 (Chuẩn nghiệm thu công trình & Quy định Huấn luyện AI Hai tầng)  
> **Áp dụng cho:** Model Stage 1 (YOLOv11 Object Detection) + Model Stage 2 (KTV GPT-5.4 Vision Inspection)  
> **Tài liệu tham chiếu:** TCVN 8865:2011, ASTM D6433 (Pavement Condition Index - PCI), AASHTO R 85, Distress Identification Manual for LTPP (FHWA-RD-03-031).

---

## 🎯 MỤC TIÊU & TẦM NHÌN KỸ THUẬT CHO GIAI ĐOẠN MVP

Để hệ thống RoadGuard AI đạt tiêu chuẩn **MVP (Minimum Viable Product)** khi triển khai thực tế trên các tuyến đường giao thông nông thôn và đô thị (đặc biệt là đường bê tông xi măng), mô hình không chỉ dừng lại ở việc phát hiện vết nứt thô mà phải đáp ứng **3 trụ cột chất lượng**:
1. **Nhận thức cân bằng cả 2 loại khuyết tật cốt lõi**: Vết nứt (`crack`) và Ổ gà / Hố sụt (`pothole`).
2. **Khử triệt để Báo động giả (False Alarm Rejection)** từ các yếu tố ngoại cảnh phức tạp: Người đi bộ, xe cộ, thùng rác ven đường, tán cây bóng râm, và đặc biệt là **dây điện mảnh hạ thế trên cao rọi bóng hình sin xuống mặt đường**.
3. **Phân biệt rạch ròi kết cấu công trình nhân tạo**: Phân biệt giữa **Khe co giãn bê tông cưa máy tiêu chuẩn (KHÔNG ĐƯỢC BÁO LỖI)** với **Vết nứt nẻ gãy tấm hoặc vỡ mép khe (BÁO LỖI CHÍNH XÁC)**.

---

## 📊 BẢNG TỔNG HỢP CÁC PHÂN HỆ TEST CASES (35 TEST CASES TOÀN DIỆN)

```
                                HỆ THỐNG 35 TEST CASES ROADGUARD AI
                                                 │
    ┌───────────────────────┬────────────────────┼────────────────────┬───────────────────────┐
    ▼                       ▼                    ▼                    ▼                       ▼
PHÂN HỆ A:              PHÂN HỆ B:           PHÂN HỆ C:           PHÂN HỆ D:              PHÂN HỆ E & F:
CÁC DẠNG VẾT NỨT        CÁC DẠNG Ổ GÀ        VẬT THỂ & XE CỘ      CÂY CỐI & BÓNG RÂM      DÂY ĐIỆN & KẾT CẤU
- Nứt dọc tim đường     - Ổ gà nông bề mặt   - Người đi bộ        - Bóng râm mờ đồng nhất - Dây điện hạ thế trên cao
- Nứt ngang tấm đan     - Ổ gà sâu lộ móng   - Xe máy, xe đạp     - Bóng cành cây sắc nét - Vệt bóng dây điện hình sin
- Nứt lưới mai rùa      - Ổ gà đọng nước     - Ô tô, xe tải       - Tán lá lốm đốm nắng   - Khe co giãn cưa máy
- Nứt mép vai đường     - Bong tróc vữa mặt  - Thùng rác vệ đường - Cỏ mọc lấn mép đường  - Khe thi công dọc
- Vỡ góc tấm bê tông    - Vỡ mép khe nối     - Gạch đá rơi vãi    - Bụi rậm che khuất     - Vệt trám nứt bitum cũ
```

---

## 🟢 PHÂN HỆ A: CÁC DẠNG VẾT NỨT MẶT ĐƯỜNG (CRACK TEST CASES - POSITIVE)

| Mã TC | Tên Test Case | Đặc điểm hình thái thực tế (Visual Cues) | Kích thước & Mức độ | Kết quả AI mong đợi (Stage 1 + Stage 2) |
| :--- | :--- | :--- | :--- | :--- |
| **TC-CRK-01** | **Vết nứt dọc (Longitudinal Crack)** | Nứt chạy song song tim đường hoặc theo dải vệt bánh xe di chuyển. Đường nứt gãy khúc tự nhiên, mép nứt răng cưa. | Dài: $0.5\text{m} - 10\text{m}+$.<br>Độ mở: $<3\text{mm}$ (Nhẹ) đến $3-6\text{mm}$ (Vừa). | **Stage 1 (YOLO):** BBox nhãn `crack`.<br>**Stage 2 (KTV):** Xác nhận `crack_longitudinal`, Severity: `LOW` hoặc `MEDIUM`, đánh giá nguy cơ nước ngấm vệt bánh xe. |
| **TC-CRK-02** | **Vết nứt ngang giữa tấm đan bê tông (Mid-Slab Transverse Crack)** | Nứt cắt vuông góc hoặc xiên với tim đường, xuất hiện ở khoảng $1/3$ đến $1/2$ chiều dài tấm đan bê tông do ứng suất uốn hoặc co ngót nhiệt. | Dài: $1.0\text{m} - 3.5\text{m}$ (xuyên ngang tấm).<br>Độ mở: $2\text{mm} - 8\text{mm}$. | **Stage 1:** BBox `crack`.<br>**Stage 2:** Xác nhận `crack_transverse`. Phân biệt rõ rệt với rãnh cưa khe co giãn (đường nứt gồ ghề, không thẳng tắp). |
| **TC-CRK-03** | **Nứt lưới / Nứt da cá sấu (Alligator / Fatigue Crack)** | Mạng lưới các vết nứt đa giác đan xen liên kết thành hình vảy mai rùa, dấu hiệu nền móng đường bị mỏi mệt nghiêm trọng và mất sức chịu tải. | Diện tích: $0.2\text{m}^2 - 3.0\text{m}^2+$.<br>Kích thước ô: $5\text{cm} - 20\text{cm}$. | **Stage 1:** BBox bao trùm toàn bộ cụm nứt.<br>**Stage 2:** Gán nhãn `crack_alligator`, Severity: `CRITICAL`. Khuyến nghị bóc cắt vá hoàn trả kết cấu móng. |
| **TC-CRK-04** | **Nứt mép tấm đan / Vai đường (Edge Crack)** | Nứt chạy dọc sát mép ngoài của tấm bê tông hoặc vai đường (cách mép $< 30\text{cm}$), do thiếu gia cố lề hoặc xe tải trọng nặng chèn mép. | Dài: $0.5\text{m} - 5\text{m}$.<br>Khoảng cách mép: $< 0.3\text{m}$. | **Stage 1:** BBox `crack`, TargetBand: `LEFT_EDGE` hoặc `RIGHT_EDGE`.<br>**Stage 2:** Gán `crack_edge`. Cảnh báo nguy cơ sạt lở lề gia cố. |
| **TC-CRK-05** | **Vết nứt vỡ góc tấm bê tông (Corner Break)** | Vết nứt xiên nối từ khe ngang sang mép dọc, cắt rời một góc tam giác của tấm đan bê tông xi măng. Dưới tải trọng xe, góc tam giác bị bập bênh. | Cạnh tam giác: $0.3\text{m} - 1.2\text{m}$ tính từ góc tấm. | **Stage 1:** BBox `crack`.<br>**Stage 2:** Gán `crack` kèm mô tả `corner_break`. Đánh giá nguy cơ sập góc tấm bê tông, khuyến nghị đục thay góc tấm. |
| **TC-CRK-06** | **Nứt dạng khối ô bàn cờ (Block Crack)** | Các vết nứt hình chữ nhật đan xen phân chia tấm mặt đường thành các khối lớn ($0.5\text{m} \times 0.5\text{m}$ đến $1\text{m} \times 1\text{m}$). | Khối nứt diện rộng trên mặt đường. | **Stage 1:** BBox `crack`.<br>**Stage 2:** Gán `crack_block`, Severity: `MEDIUM`. Thường do lão hóa chất kết dính hoặc co ngót vật liệu. |
| **TC-CRK-07** | **Vết nứt chân chim sợi tóc (Hairline Crack)** | Vết nứt bề mặt siêu mảnh, chiều rộng $< 1.0\text{mm}$, chỉ quan sát rõ ở độ cao bay thấp ($H \le 8\text{m}$) hoặc ảnh zoom-in độ phân giải cao. | Rộng: $< 1.0\text{mm}$.<br>Nông trên lớp vữa mặt. | **Stage 1:** Tiling 640x640 phát hiện.<br>**Stage 2:** Gán độ mở `<3mm`, Severity: `LOW` (chỉ theo dõi, chưa cần can thiệp kết cấu ngay). |
| **TC-CRK-08** | **Nứt toác rộng có bong vỡ mép (Severe Spalled Crack)** | Vết nứt mở rộng $> 6\text{mm}$, hai bên mép nứt bị xe cộ làm vỡ vụn từng mảng bê tông nhỏ, tạo thành rãnh hở nguy hiểm. | Rộng: $> 6\text{mm}$.<br>Mép nứt lở vỡ $1 - 3\text{cm}$. | **Stage 1:** BBox `crack`.<br>**Stage 2:** Severity: `CRITICAL`. Cảnh báo khẩn cấp thấm nước làm rỗng móng dưới mặt đường. |

---

## 🔵 PHÂN HỆ B: CÁC DẠNG Ổ GÀ & HƯ HỎNG BỀ MẶT (POTHOLE TEST CASES - POSITIVE)

| Mã TC | Tên Test Case | Đặc điểm hình thái thực tế (Visual Cues) | Kích thước & Mức độ | Kết quả AI mong đợi (Stage 1 + Stage 2) |
| :--- | :--- | :--- | :--- | :--- |
| **TC-POT-01** | **Ổ gà nông bề mặt (Shallow Pothole)** | Hốc trũng cục bộ do bong tróc lớp vữa mặt bê tông xi măng (Scaling / Raveling). Đáy hốc chưa khoét sâu xuống lớp đá thô. | Đường kính: $15\text{cm} - 35\text{cm}$.<br>Độ sâu: $< 3.0\text{cm}$. | **Stage 1:** BBox nhãn `pothole`.<br>**Stage 2:** Xác nhận `pothole_shallow`, Severity: `MEDIUM`. Khuyến nghị làm sạch thổi bụi và trám vá vữa cường độ cao. |
| **TC-POT-02** | **Ổ gà sâu nguy hiểm (Deep Structural Pothole)** | Hố khoét sâu thủng lớp mặt, vách hố đứng thẳng sắc nhọn, lộ cốt liệu đá dăm thô hoặc lộ móng cấp phối. Cực kỳ nguy hiểm cho xe máy nông thôn. | Đường kính: $30\text{cm} - 80\text{cm}+$.<br>Độ sâu: $> 5.0\text{cm} - 10\text{cm}+$. | **Stage 1:** BBox `pothole`.<br>**Stage 2:** Xác nhận `pothole_deep`, Severity: `CRITICAL`. Đề xuất cắt vuông mép hố, đầm lèn móng và hoàn trả bê tông mác cao. |
| **TC-POT-03** | **Ổ gà đọng nước đục (Water-filled Pothole)** | Hố ổ gà đọng nước mưa hoặc bùn đất đục ngầu, mặt nước phản chiếu ánh sáng bầu trời, thành mép hố vỡ nham nhở gồ ghề. | Hốc trũng có ngấn nước bên trong. | **Stage 1:** BBox `pothole`.<br>**Stage 2:** Gán `pothole_deep_water`, Severity: `CRITICAL`. Phân biệt rõ với vũng nước mỏng trên mặt đường phẳng. |
| **TC-POT-04** | **Bong tróc bê tông diện rộng (Concrete Surface Scaling)** | Bề mặt tấm đan bê tông bị phong hóa, mòn trơ sỏi đá lồi lõm trên diện tích rộng nhưng chưa khoét thành hố sâu độc lập. | Vùng loang lổ $0.5\text{m}^2 - 3\text{m}^2$. | **Stage 1:** BBox `pothole` hoặc `crack`.<br>**Stage 2:** Gán `pothole_shallow`, ghi nhận hư hỏng bề mặt do mác bê tông kém hoặc nước mặn/phèn xâm thực. |
| **TC-POT-05** | **Vỡ mép khe co giãn (Joint Spalling)** | Dọc theo đường khe co giãn ngang, bê tông 2 bên mép bị vỡ vụn từng mảng dài $>5\text{cm}$, tạo thành hốc lõm kéo dài dọc khe nối. | Vệt vỡ rộng $5 - 15\text{cm}$ bám theo rãnh cưa. | **Stage 1:** BBox `pothole` hoặc `crack`.<br>**Stage 2:** **BÁO HỎNG:** Nhận diện là hư hỏng vỡ mép khe nối bê tông (`joint_spalling`), phân biệt rõ với rãnh cưa nguyên vẹn. |
| **TC-POT-06** | **Tổ hợp Nứt vỡ liên hoàn thành Hố (Crack-to-Pothole Progression)** | Vùng nứt da cá sấu nghiêm trọng bị bánh xe băm nát, ở trung tâm đã vỡ lún thành hố ổ gà sâu. | Có mạng nứt bao quanh 1 hoặc nhiều hốc ổ gà. | **Stage 1:** Nhận diện đồng thời cả `crack` lẫn `pothole`.<br>**Stage 2:** Đánh giá mức độ xuống cấp nghiêm trọng liên hoàn của cấu trúc tấm đan. |

---

## 🔴 PHÂN HỆ C: VẬT THỂ & PHƯƠNG TIỆN TRÊN ĐƯỜNG (OBSTACLES & MOVING OBJECTS - HARD NEGATIVES)

> ⚠️ **YÊU CẦU CỦA NGƯỜI DÙNG:** "các vật thể trên đường như người xe, thùng rác ở vệ đường..."  
> Hệ thống AI **BẮT BUỘC PHẢI LOẠI TRỪ (REJECT)** hoặc phân loại là vật thể ngoại lai, **tuyệt đối không được gắn nhãn khuyết tật mặt đường**!

| Mã TC | Tên Test Case | Đặc điểm nhận dạng thực tế (Visual Cues) | Cơ chế gây báo động giả (False Alarm Mechanism) | Kết quả AI mong đợi (Ground Truth) |
| :--- | :--- | :--- | :--- | :--- |
| **TC-OBJ-01** | **Người đi bộ / Công nhân trên đường** | Hình người đứng, đi bộ hoặc cúi người làm việc trên mặt đường bê tông. Bóng đổ của người in xuống đường. | Dáng người thẳng đứng hoặc bóng người đổ dài có thể bị YOLO bắt nhầm thành vật thể lạ hoặc vết nứt dọc. | ⛔ **KHÔNG BÁO LỖI ĐƯỜNG**.<br>Stage 1: NMS/Class filter bỏ qua người. Stage 2: KTV gán `false_alarm_object` nếu lọt vào crop. |
| **TC-OBJ-02** | **Xe máy / Xe đạp đang lưu thông hoặc dựng lề đường** | Xe máy di chuyển hoặc dựng ở vai đường bê tông, lốp xe tròn đen, nan hoa kim loại, bóng xe in xuống đường. | Viền đen của lốp xe hoặc bóng xe máy rọi xuống có thể bị bắt nhầm thành ổ gà hoặc vết nứt cong. | ⛔ **KHÔNG BÁO LỖI**.<br>Target Band và Stage 2 loại bỏ hoàn toàn phương tiện giao thông. |
| **TC-OBJ-03** | **Xe ô tô / Xe tải / Xe công nông / Máy kéo** | Phương tiện cơ giới chiếm phần lớn làn đường, thân xe che khuất mặt đường bên dưới. | Khung gầm xe hoặc bóng tối dưới gầm xe tạo vùng đen lớn giống hố sụt khổng lồ. | ⛔ **KHÔNG BÁO Ổ GÀ**.<br>Bộ lọc phát hiện vùng che khuất (Occlusion Masking), không quét dưới gầm xe. |
| **TC-OBJ-04** | **Thùng rác công cộng / Đống rác ven đường** | Thùng rác nhựa màu xanh/vàng/đen hình khối chữ nhật, hoặc đống rác sinh hoạt chất ở lề đường/vỉa hè. | Góc cạnh của thùng rác hoặc rác thải màu đen/xám lọt vào góc ảnh bị YOLO tưởng là vết nứt hoặc ổ gà. | ⛔ **LOẠI BỎ 100%**.<br>1. Bộ lọc TargetBand gạt bỏ vì nằm ngoài chiều rộng $W$.<br>2. KTV Vision xác nhận `false_alarm_object` (Thùng rác lề đường). |
| **TC-OBJ-05** | **Động vật / Gia súc qua đường (Chó, bò, gà)** | Gia súc đi lại tự do trên đường giao thông nông thôn miền quê Việt Nam. | Đốm màu sẫm trên lưng/chân động vật có thể gây kích hoạt nhầm. | ⛔ **KHÔNG BÁO LỖI ĐƯỜNG**. |
| **TC-OBJ-06** | **Gạch đá, vật liệu xây dựng rơi vãi, cọc tiêu, nắp cống** | Đống cát đá dăm xây dựng tràn ra mép đường, nắp hố ga tròn bằng gang, cọc tiêu gãy đổ. | Nắp cống tròn màu đen trông giống ổ gà; đống đá dăm trông giống bong tróc bê tông. | ⛔ **Stage 2 (KTV Vision)** thẩm định trực diện: Nhận diện cấu trúc nắp cống cơ học $\rightarrow$ Gán `false_alarm_object`. |

---

## 🟡 PHÂN HỆ D: CÂY CỐI, TÁN LÁ & CÁC DẠNG BÓNG RÂM (VEGETATION & SHADOWS - HARD NEGATIVES)

| Mã TC | Tên Test Case | Đặc điểm nhận dạng thực tế (Visual Cues) | Cơ chế gây báo động giả (False Alarm Mechanism) | Kết quả AI mong đợi (Ground Truth) |
| :--- | :--- | :--- | :--- | :--- |
| **TC-SHA-01** | **Bóng râm cây cối râm mờ đồng nhất (Soft Tree Shadow)** | Tán cây ven đường che bóng râm mờ, biên bóng mềm, độ tương phản chuyển tiếp từ từ từ vùng sáng sang vùng tối. | Làm thay đổi độ sáng cục bộ của khung hình. | ⛔ **KHÔNG BÁO LỖI**.<br>Histogram gradient thấp, không có rãnh cạnh Canny $\rightarrow$ Bỏ qua. |
| **TC-SHA-02** | **Bóng cành cây khẳng khiu sắc nét (Sharp Branch Shadow)** | Khi trời nắng gắt, cành cây khô hoặc cành cây ven đường rọi bóng đen sắc cạnh xuống mặt đường bê tông trắng, đường bóng khúc khuỷu hình zíc-zắc. | **CỰC KỲ NGUY HIỂM:** Đặc trưng cạnh (Edge features) của bóng cành cây giống hệt vết nứt phân nhánh (Branching Crack)! | ⛔ **Stage 2 (KTV Vision)** quan sát ảnh Toàn cảnh: Thấy tán cây ở lề đường rọi bóng xiên $\rightarrow$ Phán quyết `false_alarm_shadow`. Quy chuẩn bay SOP khuyến nghị bay giờ thiên đỉnh 10:30–13:30 để triệt tiêu bóng. |
| **TC-SHA-03** | **Bóng tán lá lốm đốm nắng râm (Dappled Sunlight)** | Ánh nắng lọt qua kẽ lá tạo thành hàng trăm đốm sáng tối tròn nhỏ xen kẽ liên tục trên mặt đường. | Các đốm tối tròn bị model phân đoạn nhầm thành chuỗi các ổ gà con liên hoàn. | ⛔ **KTV Vision** đánh giá phân bố tuần hoàn của đốm nắng $\rightarrow$ Gán `false_alarm_shadow`. |
| **TC-SHA-04** | **Cỏ dại, rêu mốc mọc lấn từ lề vào mép bê tông** | Rêu xanh ẩm ướt hoặc bụi cỏ dại bò từ mép đất phủ lên mép tấm đan bê tông. | Ranh giới giữa cỏ xanh và bê tông xám tạo thành đường tương phản cao bị nhầm là nứt mép. | ⛔ **KTV Vision** nhận diện màu sắc thực vật (Color Hue) $\rightarrow$ Gán `false_alarm_debris`. |
| **TC-SHA-05** | **Bụi rậm, cành cây sà thấp che khuất mặt đường** | Cành tre, cành dừa sà xuống hành lang bay ở độ cao $3 - 5\text{m}$. | Che khuất một phần mặt đường bên dưới. | ⛔ Gắn cờ cảnh báo chướng ngại vật bay (`FLIGHT_OBSTACLE`), không quét vùng bị che. |

---

## ⚡ PHÂN HỆ E: ĐƯỜNG DÂY ĐIỆN & BÓNG DÂY ĐIỆN TRÊN CAO (OVERHEAD WIRES & CABLE SHADOWS)

> ⚠️ **YÊU CẦU CỦA NGƯỜI DÙNG:** "như là các cọng dây ven đường thì camera sẽ có các cọng dây điện mảnh,... nó sẽ nhìn ra là vết nứt..."  
> Đây là hiện tượng thực địa vô cùng phổ biến ở nông thôn Việt Nam: Dây điện 220V dân sinh vắt ngang đường ở độ cao $4 - 6\text{m}$.

| Mã TC | Tên Test Case | Đặc điểm nhận dạng thực tế (Visual Cues) | Cơ chế gây báo động giả (False Alarm Mechanism) | Kết quả AI mong đợi (Ground Truth) |
| :--- | :--- | :--- | :--- | :--- |
| **TC-CAB-01** | **Dây điện hạ thế / Cáp viễn thông vắt ngang trời** | Đường dây điện mảnh màu đen giăng ngang đường giữa camera drone (cao 10m) và mặt đường. | Dây điện nằm lơ lửng tạo thành một vệt đen mảnh chạy suốt bề ngang khung hình $\rightarrow$ Model phát hiện nhầm 100% là vết nứt ngang (Transverse Crack)! | ⛔ **GIẢI PHÁP 2 TẦNG:**<br>1. Quang học: Drone bay thẳng đứng Nadir $90^\circ$, tiêu cự vô cực làm mờ nhạt dây điện ngoài khoảng nét.<br>2. KTV Vision: Phát hiện vệt đen chạy vượt ra ngoài phạm vi mặt đường lên tận cột điện $\rightarrow$ Kết luận `false_alarm_cable`. |
| **TC-CAB-02** | **Vệt bóng dây điện rọi xiên (Cable Cast Shadow)** | Sợi dây điện trên cao đổ bóng đen hình sin kéo dài chéo qua lòng đường bê tông sáng màu khi mặt trời chiếu góc nghiêng. | Bóng dây điện có độ tương phản cực mạnh, uốn cong nhẹ theo bề mặt đường, thị giác máy tính rất dễ nhầm là vết nứt dọc/chéo. | ⛔ **GIẢI PHÁP:**<br>1. Quy chuẩn SOP: Bay trong Khung giờ vàng 10:30–13:30 (bóng đổ triệt tiêu).<br>2. KTV Vision: Đối chiếu góc nghiêng bóng đồng pha với bóng cột điện $\rightarrow$ Gán `false_alarm_cable_shadow`. |
| **TC-CAB-03** | **Cọng dây thép gai, dây thừng, dây nilon rơi vãi trên mặt đường** | Dây dù, dây cao su hoặc dây thép rơi vãi nằm uốn lượn trên mặt đường bê tông. | Dây có độ dày $3 - 5\text{mm}$ nằm uốn khúc tự nhiên trông giống hệt vết nứt chân chim. | ⛔ **KTV Vision Zoom-in:** Quan sát vi cấu trúc thấy dây có bóng đổ riêng nổi lên trên mặt đường (vật thể lồi, không phải rãnh nứt lõm) $\rightarrow$ Gán `false_alarm_object`. |
| **TC-CAB-04** | **Chùm dây cáp viễn thông bó tròn võng thấp** | Bó cáp đen to võng xuống gần nóc xe tải ở đầu ngõ nông thôn. | Chiếm một vệt đen lớn cắt ngang video. | ⛔ Bỏ qua, cảnh báo an toàn bay cho phi công. |

---

## 📐 PHÂN HỆ F: ĐẶC THÙ KẾT CẤU MẶT ĐƯỜNG BÊ TÔNG BÌNH THƯỜNG (NORMAL CONCRETE FEATURES)

| Mã TC | Tên Test Case | Đặc điểm nhận dạng thực tế (Visual Cues) | Khác biệt cốt lõi so với khuyết tật | Kết quả AI mong đợi (Ground Truth) |
| :--- | :--- | :--- | :--- | :--- |
| **TC-PAV-01** | **Khe co giãn cưa máy định kỳ (Transverse Contraction Joint)** | Rãnh cưa cơ học bằng máy, **thẳng tắp 100%**, xuất hiện lặp lại đều đặn mỗi $4.0\text{m} \pm 0.2\text{m}$ (hoặc $5.0\text{m}$). Rãnh rộng đều $6 - 8\text{mm}$, chèn matit bitum đen. | Không gãy khúc ngẫu nhiên, không nứt vỡ mép, chu kỳ xuất hiện đều đặn suốt tuyến đường. | ⛔ **TUYỆT ĐỐI KHÔNG BÁO LỖI**.<br>Stage 2: KTV Vision nhận diện chu kỳ khe co giãn tấm đan bê tông $\rightarrow$ Gán `false_alarm_joint` (`is_valid: false`). |
| **TC-PAV-02** | **Khe thi công dọc tim tuyến (Longitudinal Construction Joint)** | Mạch nối thẳng tắp giữa 2 dải đổ bê tông riêng biệt dọc theo tim đường. | Chạy thẳng tắp theo trục tim đường, phẳng phiu, có bố trí thanh liên kết (Tie bar). | ⛔ **KHÔNG BÁO LỖI** (`is_valid: false`). |
| **TC-PAV-03** | **Vết trám nứt nhựa đường cũ (Tar Snakes / Sealed Cracks)** | Vệt nhựa bitum đen lồi lên mặt đường do công nhân đã trám bảo dưỡng vết nứt cũ trước đây. | Bề mặt đã được lấp đầy kín khít, trơn nhẵn, nước không thể ngấm, không còn khe hở rỗng. | ⛔ **KHÔNG BÁO NỨT MỞ**.<br>Ghi nhận trạng thái `REPAIRED_PATCHED` (đã sửa chữa, không tính là khuyết tật hở). |
| **TC-PAV-04** | **Vệt phanh cao su & Vệt lốp xe đen (Tire Skid Marks)** | Vệt cao su màu đen do xe máy hoặc xe tải phanh gấp để lại trên mặt đường bê tông. | Mặt đường phẳng hoàn toàn, không có chiều sâu rãnh nứt, đổi góc nhìn thì vệt mờ dần. | ⛔ **KHÔNG BÁO LỖI** (`false_alarm_debris`). |
| **TC-PAV-05** | **Vũng nước mỏng phẳng phản chiếu gương (Shallow Puddle)** | Nước mưa đọng thành vệt mỏng trên mặt đường phẳng sau cơn mưa nhỏ. | Không có thành vách đứng của hố ổ gà, mặt nước phẳng lặng phản chiếu bầu trời. | ⛔ **KHÔNG BÁO Ổ GÀ** (`false_alarm_debris`). |
| **TC-PAV-06** | **Rãnh bó vỉa thoát nước biên (Curb / Gutter Joint)** | Rãnh thẳng nhân tạo phân cách giữa tấm bê tông lòng đường và gờ bó vỉa/rãnh thoát nước biên. | Kết cấu vỉa hè xây dựng cố định, nằm ngoài ranh giới lòng đường. | ⛔ **Target Band** tự động cắt bỏ vì nằm ngoài chiều rộng $W$. |

---

## ✈️ PHÂN HỆ G: ĐIỀU KIỆN MÔI TRƯỜNG & THIẾT BỊ BAY (DRONE OPERATIONAL EDGE CASES)

| Mã TC | Tên Test Case | Điều kiện thực nghiệm | Thách thức đối với mô hình AI | Tiêu chí nghiệm thu |
| :--- | :--- | :--- | :--- | :--- |
| **TC-ENV-01** | **Bay thấp ($H = 6\text{m} - 8\text{m}$) — GSD siêu nét ($< 1.5\text{mm/px}$)** | Flycam bay sát mặt đường, nhìn rõ từng viên sỏi nhỏ. | Vết nứt hiển thị rất lớn, có thể bị chia cắt thành nhiều BBox nhỏ rời rạc. | Cross-Tile NMS gom cụm hoàn chỉnh, không nhân đôi 1 vết nứt thành 10 box. |
| **TC-ENV-02** | **Bay cao ($H = 15\text{m} - 20\text{m}$) — GSD thô ($> 3.0\text{mm/px}$)** | Flycam bay tầm cao để khảo sát nhanh diện rộng. | Vết nứt mảnh chỉ rộng $1 - 2$ pixel, dễ bị trôi mất qua các lớp tích chập Conv. | Spatial Tiling 640x640 bảo toàn độ phân giải, bắt được vết nứt $\ge 3\text{mm}$. |
| **TC-ENV-03** | **Ánh sáng chói lóa nắng gắt (High Glare at Noon)** | Nắng trưa gay gắt, mặt đường bê tông trắng phản xạ mạnh, độ tương phản thấp. | Vết nứt bị ánh sáng lóa làm nhạt màu, khó phân biệt với nền bê tông. | Recall vết nứt đạt $\ge 75\%$ trên ảnh phơi sáng mạnh. |
| **TC-ENV-04** | **Thiếu sáng / Trời âm u (Low Light / Overcast)** | Bay vào chiều tà ($16\text{h}30 - 17\text{h}30$), bóng râm bao phủ tuyến đường, nhiễu hạt ISO cao. | Nhiễu hạt điện tử (Digital Noise) dễ bị AI nhìn nhầm thành nứt sợi tóc. | Bộ lọc Canny/Sobel khử nhiễu tốt, không bắt nhầm hạt noise. |
| **TC-ENV-05** | **Chuyển động rung nhòe (Motion Blur ở ngưỡng KS08)** | Drone gặp gió giật, độ nét Laplacian variance ở mức $100 - 120$ (sát ngưỡng loại bỏ $100.0$). | Chi tiết mép nứt bị kéo vệt nhòe mờ. | Vẫn định vị được ổ gà lớn và nứt nặng mà không bị crash hệ thống. |
| **TC-ENV-06** | **Góc quay camera nghiêng (Oblique Gimbal $60^\circ - 75^\circ$)** | Drone bay tiến phía trước với camera chúc $60^\circ$ thay vì $90^\circ$ thẳng đứng (Nadir). | Biến dạng phối cảnh (Perspective distortion): Vật thể phía xa nhỏ hơn phía gần. | Cảnh báo vi phạm SOP, khuyến nghị phi công chỉnh Gimbal về Nadir $90^\circ$. |
| **TC-ENV-07** | **Mặt đường bê tông ẩm ướt sau mưa (Damp Concrete)** | Mặt đường bê tông loang lổ mảng ướt sẫm màu và mảng khô sáng màu. | Ranh giới giữa vùng ướt và khô tạo thành đường tương phản cao dễ nhầm là nứt. | KTV Vision phân tích vùng loang ẩm $\rightarrow$ Không nhận nhầm thành nứt. |

---

## 🏆 TIÊU CHUẨN NGHIỆM THU MVP DỰA TRÊN BỘ 35 TEST CASES

1. **Độ nhạy khuyết tật thật (Recall)**:
   - Nhận diện vết nứt thật (Phân hệ A): $\ge \mathbf{85.0\%}$.
   - Nhận diện ổ gà thật (Phân hệ B): $\ge \mathbf{90.0\%}$.
2. **Khử Báo động giả (False Positive Rate)**:
   - Tỷ lệ báo nhầm trên Khe co giãn bê tông (TC-PAV-01): $< \mathbf{2.0\%}$.
   - Tỷ lệ báo nhầm trên Dây điện & Bóng dây điện (Phân hệ E): $< \mathbf{1.5\%}$.
   - Tỷ lệ báo nhầm trên Thùng rác, Người, Xe cộ (Phân hệ C): $< \mathbf{0.5\%}$.
   - Tỷ lệ báo nhầm trên Bóng cành cây & Tán lá (Phân hệ D): $< \mathbf{2.0\%}$.
3. **Độ chính xác thẩm định KTV GPT-5.4 Vision**:
   - Phán quyết đúng bản chất (Is Valid / False Alarm): $\ge \mathbf{95.0\%}$.
   - Lập luận chuyên môn (Reasoning) xuất ra bằng văn bản thuần túy, tự nhiên, phân tích sâu sắc hình thái, độ mở và giải pháp sửa chữa công trình.
