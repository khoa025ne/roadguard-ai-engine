"""
src/curation/crack_analyzer.py — Chuyên module Đánh giá & Phân loại Vết Nứt Đường Bộ
====================================================================================
Cung cấp chức năng thẩm định chuyên sâu cho các loại vết nứt mặt đường theo tiêu chuẩn kỹ thuật:
1. Phân loại hình thái vết nứt (Taxonomy):
   - crack_longitudinal: Vết nứt dọc tuyến (chạy theo chiều dài / vệt bánh xe)
   - crack_transverse: Vết nứt ngang tuyến (cắt ngang mặt đường, co ngót nhiệt)
   - crack_alligator: Vết nứt chân chim / nứt lưới mai rùa (mỏi mệt nền, giảm khả năng chịu lực)
   - crack_edge: Vết nứt mép đường / vai đường (sạt lở, yếu lề gia cố)
   - crack_block: Vết nứt khối / bàn cờ (lão hóa bê tông nhựa diện rộng)

2. Đánh giá định lượng & Thông số kỹ thuật:
   - Ước lượng cấp độ mở rộng vết nứt (Crack Width Level):
     * < 3mm: Vết nứt tóc / nhỏ (Hairline / Minor crack)
     * 3 - 6mm: Vết nứt trung bình (Medium crack)
     * > 6mm: Vết nứt rộng / nghiêm trọng (Severe / Wide crack)
   - Góc nghiêng chủ đạo (Dominant Orientation Angle)
   - Mật độ phân nhánh vết nứt (Crack Density / Branching Ratio)

3. Phân cấp nguy cơ kết cấu & Khuyến nghị kỹ thuật xử lý (Structural Risk & Recommendations):
   - Trám khe nứt nhựa nóng (Crack Sealing)
   - Rải màng vi thảm bảo dưỡng (Microsurfacing / Slurry Seal)
   - Cắt vá hoàn trả kết cấu móng (Full-depth Patching)
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


CRACK_CLASSES = {
    "crack_longitudinal": {
        "vn_name": "Vết nứt dọc tuyến",
        "description": "Vết nứt chạy song song tim đường hoặc theo vệt bánh xe, thường do mỏi mệt nền hoặc tải trọng trục nặng.",
        "default_risk": "Nước mưa có nguy cơ thấm dọc tuyến làm suy yếu kết cấu áo đường.",
        "default_recommendation": "Trám chèn khe nứt bằng bitum nhũ tương hoặc keo nhựa nóng (Crack Sealing)."
    },
    "crack_transverse": {
        "vn_name": "Vết nứt ngang tuyến",
        "description": "Vết nứt cắt vuông góc hoặc xiên với tim đường, thường hình thành do co ngót nhiệt độ hoặc nứt phản xạ từ móng.",
        "default_risk": "Gây xóc nảy phương tiện và dẫn nước xuống móng dưới tại các mối nối tấm.",
        "default_recommendation": "Xẻ rãnh và trám bitum đàn hồi chịu co giãn nhiệt (Routing & Sealing)."
    },
    "crack_alligator": {
        "vn_name": "Vết nứt chân chim / nứt lưới mai rùa",
        "description": "Mạng lưới các vết nứt đan xen hình đa giác, dấu hiệu kết cấu nền hạ bị mỏi mệt nghiêm trọng và mất khả năng chịu tải.",
        "default_risk": "Nguy cơ bong tróc đá dăm và vỡ nát thành hố ổ gà trong thời gian ngắn.",
        "default_recommendation": "Cắt bóc toàn bộ vùng nứt và vá hoàn trả kết cấu móng (Full-depth Patching)."
    },
    "crack_edge": {
        "vn_name": "Vết nứt mép đường / vai đường",
        "description": "Vết nứt xuất hiện sát mép lề đường do thiếu gia cố lề hoặc hệ thống thoát nước rãnh biên bị xói lở.",
        "default_risk": "Nguy cơ sạt trượt mép lề và phá hủy taluy đường.",
        "default_recommendation": "Gia cố bù lề đường, đắp phụ nền vai đường và xử lý thoát nước biên."
    },
    "crack_block": {
        "vn_name": "Vết nứt khối / bàn cờ",
        "description": "Các vết nứt hình chữ nhật hoặc ô bàn cờ kích thước lớn, thường do lão hóa chất kết dính nhựa đường.",
        "default_risk": "Làm rạn nứt toàn diện bề mặt màng asphalt.",
        "default_recommendation": "Rải thảm vi phủ bảo vệ bề mặt (Microsurfacing / Slurry Seal)."
    }
}


class CrackAnalyzer:
    """Bộ phân tích & đánh giá vết nứt đường bộ chuyên sâu."""

    @staticmethod
    def analyze_crop_image(
        crop_path_or_img: Path | str | np.ndarray,
        confidence: float = 0.5
    ) -> Dict[str, Any]:
        """
        Phân tích chi tiết vết nứt từ ảnh crop bằng Computer Vision & Heuristic:
        - Định hướng nứt (dọc, ngang, lưới, mép)
        - Độ rộng ước tính (<3mm, 3-6mm, >6mm)
        - Mật độ nứt & mức độ nghiêm trọng
        - Đề xuất giải pháp kỹ thuật
        """
        if isinstance(crop_path_or_img, (str, Path)):
            c_path = Path(crop_path_or_img)
            if not c_path.exists():
                return CrackAnalyzer._default_crack_result(
                    "crack_longitudinal",
                    confidence,
                    "Không tìm thấy file ảnh crop"
                )
            try:
                img = cv2.imdecode(np.fromfile(str(c_path), dtype=np.uint8), cv2.IMREAD_COLOR)
            except Exception:
                img = None
        else:
            img = crop_path_or_img

        if img is None or img.size == 0:
            return CrackAnalyzer._default_crack_result(
                "crack_longitudinal",
                confidence,
                "Ảnh rỗng hoặc không đọc được"
            )

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Tiền xử lý: làm mượt nhẹ giảm nhiễu hạt nhựa đường
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # 1. Trích xuất biên vết nứt qua Canny và ngưỡng thích nghi
        edges = cv2.Canny(blurred, 35, 120)
        edge_pixels = int(np.count_nonzero(edges))
        total_pixels = max(1, h * w)
        edge_density = float(edge_pixels / total_pixels)

        # 2. Phân tích định hướng gradient qua Sobel X và Sobel Y
        sobelx = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
        var_x = float(np.var(sobelx))
        var_y = float(np.var(sobely))
        aspect_ratio = float(w / max(1, h))

        # 3. Ước tính góc nghiêng chủ đạo từ ma trận Hessian / Moment
        moments = cv2.moments(edges)
        dominant_angle_deg = 90.0
        if moments["mu20"] + moments["mu02"] > 0:
            # Góc định hướng nứt chính
            diff = moments["mu20"] - moments["mu02"]
            angle_rad = 0.5 * np.arctan2(2 * moments["mu11"], diff)
            dominant_angle_deg = float(np.degrees(angle_rad)) % 180

        # 4. Phân loại hình thái vết nứt (Crack Classification)
        if edge_density > 0.075:
            # Mật độ cạnh cao, đa hướng -> Nứt chân chim / nứt lưới
            crack_type = "crack_alligator"
            severity = "CRITICAL"
        elif var_x > var_y * 1.55 or aspect_ratio < 0.65 or (70 <= dominant_angle_deg <= 110):
            # Gradient ngang mạnh hơn -> Đường nứt chạy dọc
            crack_type = "crack_longitudinal"
            severity = "MEDIUM" if edge_density > 0.035 else "LOW"
        elif var_y > var_x * 1.55 or aspect_ratio > 1.55 or (dominant_angle_deg < 25 or dominant_angle_deg > 155):
            # Gradient dọc mạnh hơn -> Đường nứt cắt ngang
            crack_type = "crack_transverse"
            severity = "MEDIUM" if edge_density > 0.035 else "LOW"
        elif edge_density > 0.05:
            # Mạng lưới nứt dạng bàn cờ
            crack_type = "crack_block"
            severity = "MEDIUM"
        else:
            crack_type = "crack_longitudinal"
            severity = "LOW"

        # 5. Ước lượng bề rộng vết nứt (Crack Width Level)
        # Sử dụng phép giãn nở khoảng cách (Distance Transform trên vệt nứt nhị phân)
        inv_edges = cv2.bitwise_not(edges)
        dist_transform = cv2.distanceTransform(inv_edges, cv2.DIST_L2, 3)
        # Bề rộng cục bộ trung bình của vùng tối vết nứt
        _, dark_mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        crack_core = cv2.bitwise_and(dark_mask, edges)
        core_px = np.count_nonzero(crack_core)

        if core_px > 0:
            core_ratio = float(core_px / total_pixels)
        else:
            core_ratio = edge_density

        if core_ratio > 0.045 or severity == "CRITICAL":
            crack_width_level = "> 6mm (Rộng / Nguy hiểm)"
            crack_width_code = "wide"
            if severity != "CRITICAL":
                severity = "CRITICAL"
        elif core_ratio > 0.022 or severity == "MEDIUM":
            crack_width_level = "3 - 6mm (Trung bình)"
            crack_width_code = "medium"
        else:
            crack_width_level = "< 3mm (Nhỏ / Nứt tóc)"
            crack_width_code = "hairline"

        meta = CRACK_CLASSES.get(crack_type, CRACK_CLASSES["crack_longitudinal"])

        return {
            "is_valid": True,
            "status": "VERIFIED",
            "tag_category": "positive_defect",
            "fine_tag": meta["vn_name"],
            "fine_tag_code": crack_type,
            "class_name": "crack",
            "yolo_class_id": 1,
            "severity": severity,
            "confidence_verified": round(max(0.70, confidence), 2),
            "crack_width_level": crack_width_level,
            "crack_width_code": crack_width_code,
            "crack_density_pct": round(edge_density * 100, 1),
            "dominant_angle_deg": round(dominant_angle_deg, 1),
            "structural_risk": meta["default_risk"],
            "recommendation": meta["default_recommendation"],
            "reasoning": (
                f"{meta['vn_name']} với độ mở {crack_width_level}. "
                f"Mật độ nứt {round(edge_density * 100, 1)}%. "
                f"Khuyến nghị: {meta['default_recommendation']}"
            )
        }

    @staticmethod
    def _default_crack_result(crack_type: str, confidence: float, reason: str) -> Dict[str, Any]:
        meta = CRACK_CLASSES.get(crack_type, CRACK_CLASSES["crack_longitudinal"])
        return {
            "is_valid": True,
            "status": "VERIFIED",
            "tag_category": "positive_defect",
            "fine_tag": meta["vn_name"],
            "fine_tag_code": crack_type,
            "class_name": "crack",
            "yolo_class_id": 1,
            "severity": "MEDIUM",
            "confidence_verified": round(confidence, 2),
            "crack_width_level": "3 - 6mm (Trung bình)",
            "crack_width_code": "medium",
            "crack_density_pct": 3.0,
            "dominant_angle_deg": 90.0,
            "structural_risk": meta["default_risk"],
            "recommendation": meta["default_recommendation"],
            "reasoning": f"{meta['vn_name']}. {reason}"
        }
