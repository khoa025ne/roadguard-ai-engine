# Báo cáo Task: PDF-REPORT

- **Thời gian thực hiện:** 2026-10-12 00:59
- **Trạng thái:** **DONE**

## 1. Đã làm gì
1. **Khảo sát & Triển khai Module Xuất Báo Cáo PDF:**
   - Tạo mới module [src/reporting/pdf_exporter.py](file:///f:/train%20AI%20đồ%20án/src/reporting/pdf_exporter.py) và [src/reporting/__init__.py](file:///f:/train%20AI%20đồ%20án/src/reporting/__init__.py).
   - Thiết kế giao diện HTML và PDF tuân thủ nghiêm ngặt Design Tokens Thủy Mệnh:
     * **Nền:** `#FFFFFF` (nền chính) / `#F4F7FA` (thẻ tóm tắt và tiêu đề bảng) / `#E9EFF5` (đường kẻ phân cách).
     * **Chữ:** `#0A2540` (tiêu đề và chữ chính), `#3D4F61` (nội dung kỹ thuật), `#7A8FA3` (nhãn phụ).
     * **Accent:** `#1E88C7` (đường viền tiêu đề và chỉ số nổi bật).
     * **Badge Severity:**
       - `LOW`: Nền `#D6E9F5`, chữ `#0A2540` (Chuẩn Thủy Mệnh).
       - `MEDIUM`: Nền `#E9EFF5`, chữ `#0A2540`.
       - `HIGH / CRITICAL`: Nền `#E5484D`, chữ `#FFFFFF` (Danger duy nhất ngoài hue).
     * **Hình khối:** Card bo góc tròn `12px`, nút bo góc `4px`, tuyệt đối **KHÔNG dùng box-shadow**.
     * **Typography:** Ưu tiên font `Be Vietnam Pro` / `Inter` / `ArialVN` (TrueType hỗ trợ 100% tiếng Việt).
2. **Cơ chế Động cơ Kép (Dual Engine) chống phụ thuộc hệ điều hành:**
   - Thử nghiệm WeasyPrint: Trên Windows thiếu thư viện hệ thống C `libgobject-2.0-0` / Pango.
   - Triển khai động cơ kết hợp: Tự động fallback sang ReportLab Platypus Engine (100% Python thuần túy, có sẵn trên mọi môi trường) để bảo đảm file PDF luôn được sinh thành công với đúng cấu trúc bảng, thẻ chỉ số và dữ liệu.
   - Tích hợp trực tiếp vào Stage 07 [src/pipeline/stages/07_report.py](file:///f:/train%20AI%20đồ%20án/src/pipeline/stages/07_report.py) và [configs/pipeline.yaml](file:///f:/train%20AI%20đồ%20án/configs/pipeline.yaml) (`save_inspection_pdf: true`).
3. **Sinh PDF Mẫu Từ Task Thật:**
   - Đã sinh mẫu thành công từ task kiểm định thực tế [outputs/reports/test_seg_e2e/inspection_report.json](file:///f:/train%20AI%20đồ%20án/outputs/reports/test_seg_e2e/inspection_report.json):
     * File PDF: [outputs/reports/sample_task_seg_e2e.pdf](file:///f:/train%20AI%20đồ%20án/outputs/reports/sample_task_seg_e2e.pdf) (81,528 bytes).
     * File HTML: [outputs/reports/sample_task_seg_e2e.html](file:///f:/train%20AI%20đồ%20án/outputs/reports/sample_task_seg_e2e.html) (6,963 bytes).
   - Đầy đủ toàn bộ các trường dữ liệu bắt buộc:
     * Danh sách detections (Phân loại, Fine Tag).
     * Mức độ nghiêm trọng (Severity: CRITICAL, MEDIUM).
     * Thời gian thực thi & thời gian tạo báo cáo.
     * Tọa độ WGS84 GPS thực địa (Lat, Lon, phương pháp quan trắc).
     * Kích thước vật lý 2D (Độ mở mm, Chiều dài m) và Nhận định kỹ thuật KTV.

## 2. Bằng chứng & File sửa đổi
- [src/reporting/pdf_exporter.py](file:///f:/train%20AI%20đồ%20án/src/reporting/pdf_exporter.py)
- [src/reporting/__init__.py](file:///f:/train%20AI%20đồ%20án/src/reporting/__init__.py)
- [src/pipeline/stages/07_report.py](file:///f:/train%20AI%20đồ%20án/src/pipeline/stages/07_report.py)
- [configs/pipeline.yaml](file:///f:/train%20AI%20đồ%20án/configs/pipeline.yaml)
- File PDF mẫu: `outputs/reports/sample_task_seg_e2e.pdf`
- Lệnh sinh lại độc lập:
  ```powershell
  python src/reporting/pdf_exporter.py --report outputs/reports/test_seg_e2e/inspection_report.json --output outputs/reports/sample_task_seg_e2e.pdf
  ```

## 3. Việc còn lại
- Chuyển sang task tiếp theo trong hàng đợi: `TASK UI-POLISH`.
