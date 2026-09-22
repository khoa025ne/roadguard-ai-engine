"""
src/measurement/metric_estimator.py — Đo đạc 2D kích thước thực tế & Phân loại Severity
======================================================================================
Quy đổi kích thước pixel sang mm/m dựa trên GSD và phân cấp độ nghiêm trọng.
"""

from typing import Dict, Any


class MetricEstimator:
    """Ước lượng kích thước thực tế 2D và xếp loại mức độ nghiêm trọng khuyết tật."""

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
        Tính kích thước vật lý dựa trên BBox và GSD.
        box: [x1, y1, x2, y2]
        """
        x1, y1, x2, y2 = box
        px_w = abs(x2 - x1)
        px_h = abs(y2 - y1)

        # Tính width_mm và length_m
        width_mm = round(min(px_w, px_h) * gsd_mm_per_px, 1)
        length_m = round((max(px_w, px_h) * gsd_mm_per_px) / 1000.0, 3)

        # Phân loại severity
        severity = self._classify_severity(defect_type_code, width_mm, length_m)

        return {
            "is_2d_estimate": True,
            "estimated_width_mm": width_mm,
            "estimated_length_m": length_m,
            "severity": severity,
            "gsd_used": gsd_mm_per_px
        }

    def _classify_severity(self, defect_type_code: str, width_mm: float, length_m: float) -> str:
        """
        Phân cấp mức độ nghiêm trọng theo tiêu chuẩn kỹ thuật đường bộ.
        """
        code = defect_type_code.lower()

        # Ổ gà luôn có mức độ nguy hiểm cao đến khẩn cấp
        if "pothole" in code:
            if width_mm >= 300 or length_m >= 0.5:
                return "CRITICAL"
            return "HIGH"

        # Bong tróc vỡ bê-tông
        if "spalling" in code:
            if width_mm >= 150:
                return "HIGH"
            return "MEDIUM"

        # Nứt mép đường
        if "edge" in code:
            if length_m >= 2.0:
                return "HIGH"
            return "MEDIUM"

        # Nứt chân chim, nứt dọc, nứt ngang
        if width_mm >= 10.0:
            return "HIGH"
        elif width_mm >= 3.0:
            return "MEDIUM"
        else:
            return "LOW"
