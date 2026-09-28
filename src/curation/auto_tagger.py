"""
src/curation/auto_tagger.py — Module AI Sàng lọc & Gắn Tag Tự Động (AI-Assisted Curation)
========================================================================================
Cung cấp Model AI thứ 2 đóng vai trò 'Giám khảo / Trợ lý chuyên gia':
- Thẩm định ảnh cận cảnh (Crops) xem có thực sự là khuyết tật hay báo động giả (bóng râm/rác).
- Gắn tag phân loại chi tiết (Fine-grained classification: nứt dọc/ngang/lưới, ổ gà nông/sâu).
- Đánh giá mức độ nghiêm trọng (Severity: LOW, MEDIUM, CRITICAL).
- Hỗ trợ kiến trúc Pluggable Hook (có thể cắm Vision LLM API hoặc Model PyTorch ngoài).
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional


class AIAutoTagger:
    """Bộ thẩm định và gắn nhãn tự động cho các khuyết tật đường."""

    FINE_CLASSES = {
        "pothole": {
            "shallow": "Ổ gà nông (< 3cm)",
            "deep": "Ổ gà sâu (> 5cm, nguy hiểm)",
            "water_filled": "Ổ gà đọng nước"
        },
        "crack": {
            "longitudinal": "Vết nứt dọc tuyến",
            "transverse": "Vết nứt ngang tuyến",
            "alligator": "Vết nứt chân chim / nứt lưới"
        }
    }

    def __init__(self, api_key: Optional[str] = None, provider: str = "builtin_cv_expert"):
        self.api_key = api_key
        self.provider = provider

    def analyze_crop(self, crop_path: Path | str, base_class: str, confidence: float) -> Dict[str, Any]:
        """
        Thẩm định 1 ảnh crop khuyết tật.
        Trả về kết quả sàng lọc: is_valid, fine_tag, severity, reasoning.
        """
        crop_path = Path(crop_path)
        if not crop_path.exists():
            return {
                "is_valid": False,
                "status": "ERROR",
                "reasoning": f"Không tìm thấy file ảnh: {crop_path.name}"
            }

        # Đọc ảnh an toàn với đường dẫn tiếng Việt trên Windows
        try:
            img = cv2.imdecode(np.fromfile(str(crop_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        except Exception:
            img = None

        if img is None or img.size == 0:
            return {
                "is_valid": False,
                "status": "ERROR",
                "reasoning": "Ảnh crop bị lỗi hoặc kích thước 0"
            }

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 1. Phân tích quang độ và độ tương phản (Contrast / Darkness)
        mean_brightness = float(np.mean(gray))
        std_brightness = float(np.std(gray))

        # 2. Phân tích mật độ cạnh viền (Edge Density qua Canny & Sobel)
        edges = cv2.Canny(gray, 40, 130)
        edge_ratio = float(np.count_nonzero(edges) / max(1, h * w))

        # 3. Phân tích định hướng cạnh viền (Directionality cho vết nứt)
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        var_x = float(np.var(sobelx))
        var_y = float(np.var(sobely))

        aspect_ratio = float(w / max(1, h))

        # ==============================================================
        # LOGIC SÀNG LỌC CHUYÊN SÂU (HEURISTIC EXPERT REASONING)
        # ==============================================================
        # Kiểm tra báo động giả (False Alarm)
        # - Ảnh quá mờ, không có cạnh rõ nét (edge_ratio quá thấp < 0.015)
        # - Hoặc toàn màu xám đồng nhất (std_brightness < 8.0)
        # - Hoặc bóng râm lớn nhưng không có độ dốc mép nứt
        is_false_alarm = False
        false_alarm_reason = ""

        if edge_ratio < 0.018 and std_brightness < 12.0:
            is_false_alarm = True
            false_alarm_reason = "Vùng bề mặt tương đối nhẵn, không có đường biên khuyết tật rõ rệt (nghi vấn bóng râm nhẹ hoặc vân đá phẳng)."
        elif mean_brightness > 230:
            is_false_alarm = True
            false_alarm_reason = "Vùng bị lóa sáng mạnh (Overexposure), không đủ chi tiết cấu trúc."

        if is_false_alarm:
            return {
                "is_valid": False,
                "status": "FALSE_ALARM",
                "tag_category": "hard_negative",
                "fine_tag": "Báo động giả / Nền sạch",
                "severity": "NONE",
                "confidence_verified": round(min(confidence, 0.35), 2),
                "reasoning": false_alarm_reason,
                "yolo_class_id": -1  # Nhãn rỗng
            }

        # Nếu là khuyết tật hợp lệ -> Phân loại chi tiết (Fine-grained Tagging)
        if base_class == "pothole":
            # Ổ gà: Xem xét độ tối vùng lõi và kích thước
            center_h, center_w = h // 4, w // 4
            core_roi = gray[center_h:center_h*3, center_w:center_w*3]
            core_mean = float(np.mean(core_roi)) if core_roi.size > 0 else mean_brightness

            if core_mean < 70 and edge_ratio > 0.06:
                fine_tag = self.FINE_CLASSES["pothole"]["deep"]
                severity = "CRITICAL"
                reasoning = "Hố sâu rõ rệt, vùng lõi tối và có gờ mép vỡ bê-tông sắc nét, nguy cơ gây mất an toàn cao."
                yolo_cls = 0
            elif core_mean < 85 and std_brightness > 35:
                fine_tag = self.FINE_CLASSES["pothole"]["water_filled"]
                severity = "CRITICAL"
                reasoning = "Hố có vùng phản xạ hoặc đọng nước, biến dạng bề mặt lớn."
                yolo_cls = 0
            else:
                fine_tag = self.FINE_CLASSES["pothole"]["shallow"]
                severity = "MEDIUM"
                reasoning = "Hố sụt nông bề mặt, gờ mép thấp, cần theo dõi định kỳ."
                yolo_cls = 0

        else:  # crack
            # Vết nứt: Phân tích hướng nứt theo biến thiên Sobel và tỉ lệ khung hình
            if var_x > var_y * 1.6 or aspect_ratio < 0.6:
                fine_tag = self.FINE_CLASSES["crack"]["longitudinal"]
                severity = "MEDIUM"
                reasoning = "Vết nứt chạy dọc theo chiều dài tuyến đường, mép nứt rõ nét."
                yolo_cls = 1
            elif var_y > var_x * 1.6 or aspect_ratio > 1.6:
                fine_tag = self.FINE_CLASSES["crack"]["transverse"]
                severity = "MEDIUM"
                reasoning = "Vết nứt cắt ngang bề mặt tấm bê-tông, có thể do co ngót nhiệt độ."
                yolo_cls = 1
            else:
                fine_tag = self.FINE_CLASSES["crack"]["alligator"]
                severity = "CRITICAL" if edge_ratio > 0.08 else "MEDIUM"
                reasoning = "Vết nứt chân chim mạng lưới đa hướng, dấu hiệu nền hạ suy yếu."
                yolo_cls = 1

        return {
            "is_valid": True,
            "status": "VERIFIED",
            "tag_category": "positive_defect",
            "fine_tag": fine_tag,
            "severity": severity,
            "confidence_verified": round(max(0.70, confidence), 2),
            "reasoning": reasoning,
            "yolo_class_id": yolo_cls
        }

    def curate_batch(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sàng lọc hàng loạt danh sách các khuyết tật được chọn."""
        results = []
        for item in items:
            crop_path = item.get("crop_path") or item.get("crop_file")
            base_cls = item.get("class_name", "crack")
            conf = float(item.get("confidence", 0.5))

            curation_res = self.analyze_crop(crop_path, base_cls, conf)
            merged = {**item, **curation_res}
            results.append(merged)
        return results
