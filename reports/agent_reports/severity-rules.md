# Báo cáo Task: SEVERITY-RULES

- **Thời gian thực hiện:** 2026-10-12 00:50
- **Trạng thái:** **DONE**

## 1. Đã làm gì
1. **Kiểm tra và chuẩn hóa `05_measure.py` & `src/measurement/metric_estimator.py`:**
   - Đã áp dụng đầy đủ quy chuẩn FHWA (Federal Highway Administration) cho phân loại mức độ nghiêm trọng (Severity):
     * **Nứt dọc tuyến (Longitudinal Crack):**
       - Nhẹ (`LOW`): Độ mở $< 3\text{ mm}$
       - Trung bình (`MEDIUM`): Độ mở $3 - 13\text{ mm}$
       - Nặng (`HIGH`): Độ mở $\ge 13\text{ mm}$
     * **Nứt ngang tuyến (Transverse Crack):**
       - Nhẹ (`LOW`): Độ mở $< 3\text{ mm}$
       - Trung bình (`MEDIUM`): Độ mở $3 - 6\text{ mm}$
       - Nặng (`HIGH`): Độ mở $\ge 6\text{ mm}$
     * **Nứt mai rùa / da cá sấu (Alligator / Fatigue Crack):**
       - Nặng (`HIGH` / `CRITICAL` do suy giảm khả năng chịu lực móng áo đường).
     * **Ổ gà (Potholes):**
       - Khẩn cấp (`CRITICAL`): Đường kính $\ge 300\text{ mm}$ hoặc chiều dài $\ge 0.5\text{ m}$.
       - Nặng (`HIGH`): Đường kính $\ge 150\text{ mm}$.
       - Trung bình (`MEDIUM`): Đường kính $< 150\text{ mm}$.
2. **Áp dụng Quy tắc Phân giải GSD:**
   - Chi tiết nhỏ nhất đo được trên ảnh $\approx 2 \times \text{GSD}$ (giới hạn lấy mẫu Nyquist-Shannon).
   - Để đo vết nứt $3\text{ mm}$, camera drone cần đạt $\text{GSD} \le 1.5\text{ mm/px}$.
   - Khi $\text{GSD} > 1.5\text{ mm/px}$, các vết nứt nhỏ hơn $2 \times \text{GSD}$ tự động được đánh dấu cờ cảnh báo `is_sub_resolution = True`.
3. **Đánh dấu rõ ràng các giá trị tạm thời:**
   - Đã đánh dấu comment `# TẠM — chờ thông số camera thật` tại:
     * [src/pipeline/stages/05_measure.py:28-31](file:///f:/train%20AI%20đồ%20án/src/pipeline/stages/05_measure.py#L28-L31) (`default_altitude_m`, `default_gsd_mm_per_px`, `sensor_width_mm`, `focal_length_mm`).
     * [src/pipeline/stages/05_measure.py:47-53](file:///f:/train%20AI%20đồ%20án/src/pipeline/stages/05_measure.py#L47-L53) (công thức ước lượng GSD từ độ cao bay).
     * [configs/pipeline.yaml:61-68](file:///f:/train%20AI%20đồ%20án/configs/pipeline.yaml#L61-L68).
4. **Kiểm thử tự động:**
   - Mở rộng unit test trong [tests/test_pipeline.py](file:///f:/train%20AI%20đồ%20án/tests/test_pipeline.py#L46-L84) kiểm tra đầy đủ các ngưỡng nứt dọc, nứt ngang, ổ gà và quy tắc giới hạn phân giải GSD.
   - Toàn bộ 24/24 unit tests đạt **PASS** 100%.

## 2. Bằng chứng & File sửa đổi
- [src/measurement/metric_estimator.py](file:///f:/train%20AI%20đồ%20án/src/measurement/metric_estimator.py) (triển khai quy chuẩn FHWA và cờ `is_sub_resolution`).
- [src/pipeline/stages/05_measure.py](file:///f:/train%20AI%20đồ%20án/src/pipeline/stages/05_measure.py) (comment `# TẠM — chờ thông số camera thật`).
- [configs/pipeline.yaml](file:///f:/train%20AI%20đồ%20án/configs/pipeline.yaml) (đánh dấu cấu hình camera tạm thời).
- [tests/test_pipeline.py](file:///f:/train%20AI%20đồ%20án/tests/test_pipeline.py) (test suite xác thực quy chuẩn).

## 3. Việc còn lại
- Chờ thông số sensor width và focal length thực tế từ camera drone để thay thế các giá trị tạm.
- Chuyển sang task tiếp theo trong hàng đợi: `TASK KTV-WIRING`.
