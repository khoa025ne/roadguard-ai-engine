"""
src/curation/auto_tagger.py — Module AI Sàng lọc & Gắn Tag Tự Động (AI-Assisted Curation)
========================================================================================
Cung cấp Model AI thứ 2 đóng vai trò 'Giám khảo / Trợ lý chuyên gia':
- Thẩm định ảnh cận cảnh (Crops) xem có thực sự là khuyết tật hay báo động giả (bóng râm/rác/đèn/cống).
- Phân loại chi tiết khuyết tật (Fine-grained classification: nứt dọc/ngang/lưới/mép/khối, ổ gà nông/sâu).
- Chức năng chuyên sâu đánh giá và phân loại vết nứt (Crack Assessment & Morphology).
- Khử trùng lặp đối tượng (Deduplication) đảm bảo số lượng item khớp không bị trùng lặp.
- Hỗ trợ gom tối đa 100 ảnh / 1 request API tới Vision Multimodal Model (gpt-5.4).
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional

from .crack_analyzer import CrackAnalyzer, CRACK_CLASSES
from .deduplicator import DefectDeduplicator


class AIAutoTagger:
    """Bộ thẩm định, phân loại chuyên sâu và khử trùng lặp khuyết tật đường."""

    FINE_CLASSES = {
        "pothole": {
            "shallow": "Ổ gà nông (< 3cm)",
            "deep": "Ổ gà sâu (> 5cm, nguy hiểm)",
            "water_filled": "Ổ gà đọng nước"
        },
        "crack": {
            "longitudinal": "Vết nứt dọc tuyến",
            "transverse": "Vết nứt ngang tuyến",
            "alligator": "Vết nứt chân chim / nứt lưới",
            "edge": "Vết nứt mép đường / vai đường",
            "block": "Vết nứt khối / bàn cờ"
        }
    }

    def __init__(self, api_key: Optional[str] = None, provider: str = "kdv_gpt54"):
        self.api_key = api_key
        self.provider = provider
        self.kdv = None
        self.deduplicator = DefectDeduplicator()
        self.crack_analyzer = CrackAnalyzer()

        if provider == "kdv_gpt54":
            try:
                from .kdv_inspector import KDVInspector
                self.kdv = KDVInspector(api_key=api_key)
            except Exception:
                self.kdv = None

    def analyze_crop(self, crop_path: Path | str, base_class: str, confidence: float) -> Dict[str, Any]:
        """
        Thẩm định 1 ảnh crop khuyết tật.
        Trả về kết quả sàng lọc: is_valid, fine_tag, severity, crack_width_level, reasoning.
        """
        if self.provider == "kdv_gpt54" and self.kdv is not None:
            return self.kdv.inspect_crop(crop_path, base_class, confidence)

        crop_path = Path(crop_path)
        if not crop_path.exists():
            return {
                "is_valid": False,
                "status": "ERROR",
                "reasoning": f"Không tìm thấy file ảnh: {crop_path.name}"
            }

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

        mean_brightness = float(np.mean(gray))
        std_brightness = float(np.std(gray))
        edges = cv2.Canny(gray, 40, 130)
        edge_ratio = float(np.count_nonzero(edges) / max(1, h * w))

        # Kiểm tra báo động giả (False Alarm)
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
                "fine_tag_code": "false_alarm_shadow",
                "severity": "NONE",
                "confidence_verified": round(min(confidence, 0.35), 2),
                "reasoning": false_alarm_reason,
                "yolo_class_id": -1
            }

        # Nếu là khuyết tật hợp lệ
        if base_class == "pothole":
            center_h, center_w = h // 4, w // 4
            core_roi = gray[center_h:center_h*3, center_w:center_w*3]
            core_mean = float(np.mean(core_roi)) if core_roi.size > 0 else mean_brightness

            if core_mean < 70 and edge_ratio > 0.06:
                fine_tag = self.FINE_CLASSES["pothole"]["deep"]
                fine_code = "pothole_deep"
                severity = "CRITICAL"
                reasoning = "Hố sâu rõ rệt, vùng lõi tối và có gờ mép vỡ bê-tông sắc nét, nguy cơ gây mất an toàn cao."
            elif core_mean < 85 and std_brightness > 35:
                fine_tag = self.FINE_CLASSES["pothole"]["water_filled"]
                fine_code = "pothole_deep_water"
                severity = "CRITICAL"
                reasoning = "Hố có vùng phản xạ hoặc đọng nước, biến dạng bề mặt lớn."
            else:
                fine_tag = self.FINE_CLASSES["pothole"]["shallow"]
                fine_code = "pothole_shallow"
                severity = "MEDIUM"
                reasoning = "Hố sụt nông bề mặt, gờ mép thấp, cần theo dõi định kỳ."

            return {
                "is_valid": True,
                "status": "VERIFIED",
                "tag_category": "positive_defect",
                "fine_tag": fine_tag,
                "fine_tag_code": fine_code,
                "severity": severity,
                "confidence_verified": round(max(0.70, confidence), 2),
                "reasoning": reasoning,
                "yolo_class_id": 0
            }

        else:
            # Phân tích vết nứt chuyên sâu qua CrackAnalyzer
            return self.crack_analyzer.analyze_crop_image(img, confidence=confidence)

    def assess_crack(self, crop_path: Path | str, confidence: float = 0.5) -> Dict[str, Any]:
        """Chức năng đánh giá và phân loại vết nứt đường bộ chuyên sâu."""
        return self.crack_analyzer.analyze_crop_image(crop_path, confidence=confidence)

    def deduplicate_items(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Khử trùng lặp đối tượng khuyết tật, đảm bảo số lượng mục match không bị trùng."""
        return self.deduplicator.deduplicate(items)

    def curate_with_overview_context(
        self,
        overview_image: Any,
        items: List[Dict[str, Any]],
        road_metadata: Optional[Dict[str, Any]] = None,
        batch_size: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Thẩm định khuyết tật với cơ chế DUAL-VIEW CONTEXT (Góc nhìn Kép: Bối cảnh Toàn cảnh + Cận cảnh phóng to).
        """
        if not items:
            return []

        if self.provider == "kdv_gpt54" and self.kdv is not None and self.kdv.is_available:
            return self.kdv.inspect_with_context(
                overview_image=overview_image,
                defect_items=items,
                road_metadata=road_metadata,
                batch_size=batch_size
            )

        # Chế độ dự phòng khi ngoại tuyến
        results = []
        for item in items:
            crop_path = item.get("crop_path") or item.get("crop_file")
            base_cls = item.get("class_name", "crack")
            conf = float(item.get("confidence", 0.5))
            curation_res = self.analyze_crop(crop_path, base_cls, conf)
            results.append({**item, **curation_res})
        return results

    def curate_batch(
        self,
        items: List[Dict[str, Any]],
        batch_size: int = 100,
        apply_dedup: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Sàng lọc hàng loạt danh sách các khuyết tật (Gom 100 ảnh / 1 request API KTV).
        Tự động khử trùng lặp đối tượng.
        """
        if not items:
            return []

        # 1. Gọi KTV thẩm định (nếu có KTV gpt-5.4)
        if self.provider == "kdv_gpt54" and self.kdv is not None and self.kdv.is_available:
            raw_curated = self.kdv.inspect_batch_crops(items, batch_size=batch_size)
        else:
            raw_curated = []
            for item in items:
                crop_path = item.get("crop_path") or item.get("crop_file")
                base_cls = item.get("class_name", "crack")
                conf = float(item.get("confidence", 0.5))
                curation_res = self.analyze_crop(crop_path, base_cls, conf)
                raw_curated.append({**item, **curation_res})

        # 2. Khử trùng lặp đối tượng
        if apply_dedup:
            dedup_res = self.deduplicator.deduplicate(raw_curated)
            return dedup_res["deduplicated_items"]

        return raw_curated

