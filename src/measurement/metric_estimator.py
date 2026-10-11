"""
src/measurement/metric_estimator.py — Đo đạc 2D kích thước thực tế & Phân loại Severity
======================================================================================
Quy đổi kích thước pixel sang mm/m dựa trên GSD và phân cấp độ nghiêm trọng.
Áp dụng tiêu chuẩn đo đạc và phân cấp mức độ hư hỏng mặt đường FHWA (Federal Highway Administration):
1. Nứt dọc (Longitudinal Cracking):
   - Nhẹ (LOW): Độ mở < 3 mm
   - Trung bình (MEDIUM): Độ mở 3 – 13 mm
   - Nặng (HIGH): Độ mở ≥ 13 mm
2. Nứt ngang (Transverse Cracking):
   - Nhẹ (LOW): Độ mở < 3 mm
   - Trung bình (MEDIUM): Độ mở 3 – 6 mm
   - Nặng (HIGH): Độ mở ≥ 6 mm
3. Nứt da cá sấu / nứt mai rùa (Alligator Cracking):
   - Nặng (HIGH / CRITICAL do phá hủy kết cấu móng áo đường)
4. Ổ gà (Potholes):
   - Nhỏ / Trung bình (MEDIUM): Đường kính < 150 mm
   - Lớn / Sâu (HIGH): Đường kính 150 – 300 mm
   - Khẩn cấp (CRITICAL): Đường kính ≥ 300 mm hoặc chiều dài ≥ 0.5 m

Quy tắc GSD (Ground Sampling Distance Resolution Limit):
- Chi tiết nhỏ nhất đo được trên ảnh số xấp xỉ 2 × GSD (Nyquist-Shannon sampling limit).
- Để đo được vết nứt hairline 3 mm theo FHWA, camera drone cần đạt GSD ≤ 1.5 mm/px.
- Nếu GSD > 1.5 mm/px (ví dụ bay cao 10m với cảm biến nhỏ cho GSD ~ 5.3 mm/px), các vết nứt nhỏ hơn 2×GSD
  được đánh dấu cảnh báo độ phân giải `is_sub_resolution = True`.
"""

from typing import Dict, Any


class MetricEstimator:
    """Ước lượng kích thước thực tế 2D và xếp loại mức độ nghiêm trọng khuyết tật theo FHWA."""

    SEVERITY_LEVELS = {
        "LOW": "Thấp (Theo dõi)",
        "MEDIUM": "Trung bình (Cần bảo dưỡng định kỳ)",
        "HIGH": "Nghiêm trọng (Cần sửa chữa sớm)",
        "CRITICAL": "Khẩn cấp (Nguy hiểm an toàn giao thông)",
    }

    def estimate_dimensions(
        self,
        box: list,
        gsd_mm_per_px: float,
        defect_type_code: str = "pothole"
    ) -> Dict[str, Any]:
        """
        Tính kích thước vật lý dựa trên BBox và GSD theo chuẩn FHWA.
        box: [x1, y1, x2, y2]
        """
        x1, y1, x2, y2 = box
        px_w = abs(x2 - x1)
        px_h = abs(y2 - y1)

        # Tính width_mm và length_m
        width_mm = round(min(px_w, px_h) * gsd_mm_per_px, 1)
        length_m = round((max(px_w, px_h) * gsd_mm_per_px) / 1000.0, 3)

        # Quy tắc GSD: chi tiết nhỏ nhất đo được ≈ 2 x GSD (muốn đo 3mm cần GSD <= 1.5mm/px)
        min_measurable_mm = round(2.0 * gsd_mm_per_px, 2)
        is_sub_resolution = width_mm < min_measurable_mm

        # Phân loại severity theo tiêu chuẩn FHWA
        severity = self._classify_severity(defect_type_code, width_mm, length_m)

        return {
            "is_2d_estimate": True,
            "estimated_width_mm": width_mm,
            "estimated_length_m": length_m,
            "severity": severity,
            "gsd_used": gsd_mm_per_px,
            "min_measurable_width_mm": min_measurable_mm,
            "is_sub_resolution": is_sub_resolution,
            "standard_rules": "FHWA_SEVERITY_RULES_V1"
        }

    def _classify_severity(self, defect_type_code: str, width_mm: float, length_m: float) -> str:
        """
        Phân cấp mức độ nghiêm trọng theo tiêu chuẩn kỹ thuật đường bộ FHWA:
        - Nứt dọc: <3mm (LOW), 3-13mm (MEDIUM), >=13mm (HIGH)
        - Nứt ngang: <3mm (LOW), 3-6mm (MEDIUM), >=6mm (HIGH)
        - Nứt mai rùa / lưới: HIGH hoặc CRITICAL
        - Ổ gà: >=300mm (CRITICAL), >=150mm (HIGH), <150mm (MEDIUM)
        """
        code = str(defect_type_code).lower()

        # 1. Ổ gà (Pothole)
        if "pothole" in code:
            if width_mm >= 300.0 or length_m >= 0.5:
                return "CRITICAL"
            elif width_mm >= 150.0:
                return "HIGH"
            return "MEDIUM"

        # 2. Bong tróc vỡ mép / mặt bê-tông (Spalling / Scaling)
        if "spalling" in code or "bong_troc" in code:
            if width_mm >= 150.0 or length_m >= 0.3:
                return "HIGH"
            return "MEDIUM"

        # 3. Nứt da cá sấu / nứt mai rùa / nứt lưới (Alligator / Fatigue Crack)
        if "alligator" in code or "fatigue" in code:
            if width_mm >= 6.0 or length_m >= 1.0:
                return "CRITICAL"
            return "HIGH"

        # 4. Nứt ngang tuyến (Transverse Crack) — Ngưỡng FHWA: <3mm nhẹ, 3-6mm TB, >=6mm nặng
        if "transverse" in code or "ngang" in code:
            if width_mm >= 6.0:
                return "HIGH"
            elif width_mm >= 3.0:
                return "MEDIUM"
            return "LOW"

        # 5. Nứt mép đường (Edge Crack)
        if "edge" in code:
            if length_m >= 2.0 or width_mm >= 13.0:
                return "HIGH"
            return "MEDIUM"

        # 6. Nứt dọc tuyến (Longitudinal Crack) & Nứt tổng quát (Crack)
        # Chuẩn FHWA: <3mm nhẹ (LOW), 3-13mm trung bình (MEDIUM), >=13mm nặng (HIGH)
        if width_mm >= 13.0:
            return "HIGH"
        elif width_mm >= 3.0:
            return "MEDIUM"
        else:
            return "LOW"

