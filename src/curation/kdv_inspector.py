"""
src/curation/kdv_inspector.py — Model AI Thứ 2: KTV / KDV (Kiểm Duyệt Viên & Giám Định Kỹ Thuật)
================================================================================================
Sử dụng Vision Multimodal AI (gpt-5.4) để đóng vai trò Chuyên gia Kỹ thuật Giám định Đường bộ:
1. SÀNG LỌC (Verify): Phán quyết [CHUẨN] (is_valid: true) hay [BÁO ĐỘNG GIẢ] (is_valid: false).
2. GẮN TAG & PHÂN LOẠI VẾT NỨT CHUYÊN SÂU:
   - Nứt dọc (longitudinal), Nứt ngang (transverse), Nứt lưới (alligator), Nứt mép (edge), Nứt khối (block)...
   - Đánh giá độ mở rộng vết nứt (< 3mm, 3-6mm, > 6mm) và nguy cơ kết cấu.
3. KHỬ TRÙNG LẶP ĐỐI TƯỢNG (Deduplication): Nhận diện các góc chụp lặp để không trùng lặp số lượng khuyết tật.
4. BATCHING 100 ẢNH / 1 REQUEST: Tối ưu gom tối đa 100 ảnh cắt cận cảnh thành các bảng mosaic và gửi trong 1 request.
5. DỰ PHÒNG THÔNG MINH (Graceful Fallback): Tự động chuyển sang Computer Vision Heuristic + CrackAnalyzer nếu mất mạng.
"""

import os
import json
import time
import base64
import re
import math
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from .crack_analyzer import CrackAnalyzer, CRACK_CLASSES


TAG_MAP = {
    "crack_longitudinal": "Vết nứt dọc tuyến",
    "crack_transverse": "Vết nứt ngang tuyến",
    "crack_alligator": "Vết nứt chân chim / nứt lưới",
    "crack_edge": "Vết nứt mép đường / vai đường",
    "crack_block": "Vết nứt khối / bàn cờ",
    "pothole_shallow": "Ổ gà nông (< 3cm)",
    "pothole_deep_water": "Ổ gà sâu / đọng nước",
    "pothole_deep": "Ổ gà sâu (> 5cm)",
    "false_alarm_joint": "Báo động giả (Khe co giãn tấm đan bê tông)",
    "false_alarm_cable_shadow": "Báo động giả (Bóng dây điện / bóng cây)",
    "false_alarm_shadow": "Báo động giả (Bóng râm / bóng cây)",
    "false_alarm_debris": "Báo động giả (Vệt sơn / rác / vệt dầu)",
    "false_alarm_object": "Báo động giả (Thùng rác / đèn đường / nắp cống / rãnh)",
    "false_alarm": "Báo động giả / Nền sạch"
}


def _load_env_if_exists():
    """Tự động nạp cấu hình bảo mật từ file .env cục bộ nếu có."""
    if os.getenv("KDV_API_KEY"):
        return
    for candidate in [Path(".env"), Path(__file__).resolve().parents[2] / ".env"]:
        if candidate.exists():
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip().strip("'\"")
                            if k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass


class KDVInspector:
    """Model AI Thứ 2 — KTV / KDV thẩm định và phân loại khuyết tật đường."""

    DEFAULT_BASE_URL = "https://api.xah.io/v1"
    DEFAULT_MODEL = "gpt-5.4"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 90.0,
        max_retries: int = 3
    ):
        _load_env_if_exists()
        self.api_key = api_key or os.getenv("KDV_API_KEY", "")
        self.base_url = base_url or os.getenv("KDV_BASE_URL", self.DEFAULT_BASE_URL)
        self.model = model or os.getenv("KDV_MODEL", self.DEFAULT_MODEL)
        self.timeout = timeout
        self.max_retries = max_retries

        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout
            )
        except Exception as e:
            self._client = None
            print(f"[KDVInspector] Cảnh báo: Không thể khởi tạo OpenAI client ({e})")

    @property
    def is_available(self) -> bool:
        return self._client is not None and bool(self.api_key)

    def _encode_image_b64(self, image_path: Path | str) -> Optional[str]:
        image_path = Path(image_path)
        if not image_path.exists():
            return None
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            return None

    def _build_prompt(self, base_class: str, confidence: float, context_info: Optional[str] = None) -> str:
        ctx_section = f"\nThông tin bối cảnh trắc địa/tuyến: {context_info}\n" if context_info else ""
        return f"""Bạn là KTV (Kỹ Thuật Viên Giám Định) - Chuyên gia Cao cấp về Giám định Kết cấu Mặt đường (Senior Pavement Structural Inspector) của dự án RoadGuard.
Model quét nhanh sơ bộ (YOLO) đã phát hiện vị trí này nghi vấn là [{base_class.upper()}] với độ tin cậy sơ bộ {confidence:.2f}.{ctx_section}

Bạn hãy quan sát kỹ lưỡng và đưa ra nhận định chuyên môn độc lập, tự nhiên và sắc bén của một kỹ sư cầu đường thực thụ:
1. SÀNG LỌC BẢO CHỨNG (Verification):
   - Phán quyết: is_valid = true (khuyết tật kết cấu thật) hoặc false (BÁO ĐỘNG GIẢ).
   - Hãy thẩm tra nghiêm ngặt để loại bỏ báo động giả: bóng râm cây cối, bóng dây điện mảnh rọi xiên, khe co giãn / khe thi công tiêu chuẩn giữa các tấm đan bê tông, vệt trám nhựa đường/matit cũ, vết dầu mỡ, vệt nước đọng, rác rưởi hoặc chướng ngại vật ven lề đường.

2. PHÂN LOẠI CHI TIẾT KHUYẾT TẬT (fine_tag):
   - "crack_longitudinal": Vết nứt dọc theo tim tuyến đường (thường do lún lệch nền hoặc mệt mỏi dưới dải vệt bánh xe).
   - "crack_transverse": Vết nứt ngang vuông góc với tim đường (thường do ứng suất co ngót nhiệt hoặc tải trọng uốn của tấm đan).
   - "crack_alligator": Vết nứt chân chim / nứt lưới mai rùa (phản ánh sự suy kiệt kết cấu móng bên dưới).
   - "crack_edge": Vết nứt mép tấm đan bê tông hoặc lề đường (do thiếu đệm đỡ vai đường hoặc xe tải chèn mép).
   - "crack_block": Vết nứt khối chữ nhật / ô bàn cờ liên kết.
   - "pothole_shallow": Ổ gà nông bề mặt (< 3cm), bong tróc lớp vữa mặt.
   - "pothole_deep_water": Ổ gà sâu đọng nước, tiềm ẩn nguy cơ mất an toàn giao thông nghiêm trọng.
   - "pothole_deep": Ổ gà sâu (> 5cm) khoét sâu xuống lớp móng.
   - "false_alarm_joint": Báo động giả do khe co giãn / khe nối thi công tiêu chuẩn của tấm đan bê tông xi măng.
   - "false_alarm_cable_shadow": Báo động giả do bóng dây điện mảnh trên cao hoặc bóng cành cây rọi xuống.
   - "false_alarm_object": Báo động giả do vật thể ngoại lai (thùng rác lề đường, đèn, nắp cống, xe cộ, người).
   - "false_alarm_debris": Báo động giả do vệt sơn mòn, rác rưởi, vệt bùn đất bẩn, vệt lốp xe.

3. ĐÁNH GIÁ ĐỊNH LƯỢNG & NGUY CƠ:
   - crack_width: "<3mm" (vết nứt chân chim sợi tóc), "3-6mm" (vết nứt mở rộng trung bình), ">6mm" (vết nứt toác nguy hiểm).
   - severity: "LOW", "MEDIUM", "CRITICAL" (hoặc "NONE" nếu là báo động giả).
   - reasoning: Đoạn văn bản nhận định kỹ thuật thuần túy bằng tiếng Việt do bạn tự suy luận và đúc kết (không được sao chép khuôn mẫu): Mô tả hình thái hư hại, đặc điểm mép nứt, phân biệt với khe co giãn/bóng dây điện, đánh giá tác động tới an toàn giao thông và kiến nghị phương án xử lý công trình phù hợp (bơm keo epoxy trám kín, trám matit nóng, bọc phủ lớp mặt hay đục thay thế tấm đan).

BẮT BUỘC trả về định dạng JSON thuần túy theo cấu trúc:
{{
  "is_valid": true,
  "fine_tag": "crack_longitudinal",
  "crack_width": "3-6mm",
  "severity": "MEDIUM",
  "reasoning": "Đoạn văn phân tích kỹ thuật chuyên sâu bằng tiếng Việt do bạn tự suy luận"
}}
"""

    def inspect_crop(
        self,
        crop_path: Path | str,
        base_class: str = "crack",
        confidence: float = 0.5
    ) -> Dict[str, Any]:
        """
        Gửi 1 ảnh crop tới Model KTV (gpt-5.4) để thẩm định và phân loại chuyên sâu.
        """
        crop_path = Path(crop_path)
        b64_img = self._encode_image_b64(crop_path)

        if not b64_img:
            return {
                "inspector": "KTV (Lỗi nạp ảnh)",
                "is_valid": False,
                "status": "ERROR",
                "tag_category": "error",
                "fine_tag": "Không tìm thấy file ảnh",
                "severity": "NONE",
                "confidence_verified": 0.0,
                "reasoning": f"Không thể đọc file ảnh: {crop_path.name}",
                "yolo_class_id": -1
            }

        # Nếu không có OpenAI client -> Fallback sang Heuristic CV + CrackAnalyzer
        if not self.is_available:
            return self._heuristic_fallback(crop_path, base_class, confidence, "OpenAI client chưa được cấu hình")

        prompt_text = self._build_prompt(base_class, confidence)

        for attempt in range(1, self.max_retries + 1):
            try:
                res = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt_text},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                            ]
                        }
                    ],
                    max_tokens=1024
                )
                raw_text = (res.choices[0].message.content or "").strip()

                if "lỗi nội bộ" in raw_text.lower():
                    time.sleep(1.2 * attempt)
                    continue

                parsed = self._extract_json(raw_text)
                if parsed:
                    is_valid = bool(parsed.get("is_valid", False))
                    raw_fine_tag = str(parsed.get("fine_tag", "crack_longitudinal"))
                    severity = str(parsed.get("severity", "MEDIUM" if is_valid else "NONE")).upper()
                    if severity not in ["LOW", "MEDIUM", "CRITICAL", "NONE"]:
                        severity = "MEDIUM" if is_valid else "NONE"
                    crack_width = str(parsed.get("crack_width", "3-6mm"))
                    reasoning = str(parsed.get("reasoning", "Được thẩm định bởi KTV AI."))

                    friendly_tag = TAG_MAP.get(raw_fine_tag, raw_fine_tag)

                    if not is_valid:
                        yolo_cls = -1
                    elif "pothole" in raw_fine_tag:
                        yolo_cls = 0
                    else:
                        yolo_cls = 1

                    # Lấy thông số kỹ thuật chuẩn hóa nếu là vết nứt
                    meta_risk = ""
                    meta_recom = ""
                    if is_valid and yolo_cls == 1:
                        c_meta = CRACK_CLASSES.get(raw_fine_tag, CRACK_CLASSES["crack_longitudinal"])
                        meta_risk = c_meta["default_risk"]
                        meta_recom = c_meta["default_recommendation"]

                    return {
                        "inspector": f"KTV ({self.model})",
                        "is_valid": is_valid,
                        "status": "VERIFIED" if is_valid else "FALSE_ALARM",
                        "tag_category": "positive_defect" if is_valid else "hard_negative",
                        "fine_tag": friendly_tag,
                        "fine_tag_code": raw_fine_tag,
                        "severity": severity,
                        "crack_width_level": crack_width,
                        "structural_risk": meta_risk,
                        "recommendation": meta_recom,
                        "confidence_verified": round(confidence, 2),
                        "reasoning": reasoning,
                        "yolo_class_id": yolo_cls
                    }

            except Exception as e:
                if attempt == self.max_retries:
                    return self._heuristic_fallback(crop_path, base_class, confidence, f"Lỗi KTV API: {str(e)[:100]}")
                time.sleep(1.2 * attempt)

        return self._heuristic_fallback(crop_path, base_class, confidence, "KTV API quá tải sau nhiều lần thử lại")

    def inspect_with_context(
        self,
        overview_image: Any,
        defect_items: List[Dict[str, Any]],
        road_metadata: Optional[Dict[str, Any]] = None,
        batch_size: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Thẩm định khuyết tật với cơ chế DUAL-VIEW CONTEXT (Góc nhìn Kép: Ngữ cảnh Toàn cảnh + Cận cảnh Phóng to):
        - Ảnh Toàn Cảnh (Overview Frame): Bao quát toàn tuyến đường, vẽ Bounding Box dạ quang neon và đánh số [#1], [#2]...
          giúp KTV Vision nhìn thấy tim đường, mép lề đường, chuỗi khe co giãn tấm đan bê tông, bóng dây điện và vật thể lề đường.
        - Ảnh Cận Cảnh (Zoom-in Crops): Các lát cắt chi tiết độ nét cao để thẩm định vi cấu trúc vết nứt.
        - Output văn bản thuần túy: Cho phép GPT-5.4 Vision tự do suy luận và lập luận chuyên gia, không gò bó khuôn mẫu.
        """
        if not defect_items:
            return []

        # Nạp và chuẩn bị ảnh toàn cảnh Overview
        overview_cv = None
        if isinstance(overview_image, (str, Path)):
            p = Path(overview_image)
            if p.exists():
                try:
                    overview_cv = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
                except Exception:
                    overview_cv = None
        elif isinstance(overview_image, np.ndarray):
            overview_cv = overview_image.copy()

        # Nếu không có OpenAI client -> Fallback heuristic cho toàn bộ items
        if not self.is_available:
            results = []
            for it in defect_items:
                c_path = Path(it.get("crop_path") or it.get("crop_file") or "")
                b_cls = it.get("class_name", "crack")
                conf = float(it.get("confidence", 0.5))
                fb = self._heuristic_fallback(c_path, b_cls, conf, "KTV AI ngoại tuyến (Chế độ Fallback CV Chuyên sâu)")
                results.append({**it, **fb})
            return results

        all_results = []
        total_items = len(defect_items)

        # Trích xuất metadata con đường do BE cung cấp
        meta = road_metadata or {}
        road_name = meta.get("road_name", "Tuyến đường bê tông xi măng")
        road_width = meta.get("road_width_m", 5.0)
        pavement_type = meta.get("pavement_type", "Bê tông xi măng có khe co giãn định kỳ")

        # Xử lý theo từng mini-batch tối ưu (mặc định 6 items/request để model tập trung cao độ)
        for b_start in range(0, total_items, batch_size):
            chunk_items = defect_items[b_start:b_start + batch_size]
            c_count = len(chunk_items)
            start_num = b_start + 1
            end_num = b_start + c_count

            # Tạo ảnh overview có chú thích đánh số Bounding Box ROI
            annotated_overview_b64 = None
            if overview_cv is not None and overview_cv.size > 0:
                vis_img = overview_cv.copy()
                h_orig, w_orig = vis_img.shape[:2]

                for idx_in_chunk, it in enumerate(chunk_items):
                    num = start_num + idx_in_chunk
                    bbox = it.get("bbox") or it.get("xyxy")
                    if bbox and len(bbox) >= 4:
                        x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
                        # Đảm bảo tọa độ nằm trong khung ảnh
                        x1, y1 = max(0, x1), max(0, y1)
                        x2, y2 = min(w_orig - 1, x2), min(h_orig - 1, y2)

                        # Vẽ hộp Bounding Box neon xanh vàng nổi bật
                        cv2.rectangle(vis_img, (x1, y1), (x2, y2), (0, 240, 255), 3)

                        # Vẽ nhãn số thứ tự [#idx] có nền đen viền vàng
                        label_txt = f"#{num}"
                        (tw, th), _ = cv2.getTextSize(label_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                        cv2.rectangle(vis_img, (x1, max(0, y1 - th - 8)), (x1 + tw + 10, y1), (0, 0, 0), -1)
                        cv2.rectangle(vis_img, (x1, max(0, y1 - th - 8)), (x1 + tw + 10, y1), (0, 240, 255), 1)
                        cv2.putText(vis_img, label_txt, (x1 + 4, max(th + 2, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                # Giảm độ phân giải nhẹ nếu ảnh quá lớn để tiết kiệm token nhưng vẫn sắc nét (max dimension 1600px)
                max_dim = max(h_orig, w_orig)
                if max_dim > 1600:
                    scale = 1600.0 / max_dim
                    vis_img = cv2.resize(vis_img, (int(w_orig * scale), int(h_orig * scale)), interpolation=cv2.INTER_AREA)

                ret, buf = cv2.imencode(".jpg", vis_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    annotated_overview_b64 = base64.b64encode(buf).decode("utf-8")

            # Xây dựng prompt cho Dual-View Context
            prompt_dual = f"""Bạn là KTV (Kỹ Thuật Viên Giám Định) - Chuyên gia Cao cấp Giám định Mặt đường Giao thông của dự án RoadGuard.
Dưới đây là DỮ LIỆU KHẢO SÁT MẶT ĐƯỜNG BẰNG FLYCAM gồm 2 thành phần:
1. ẢNH TOÀN CẢNH BỐI CẢNH (Overview Frame): Góc nhìn thẳng đứng vuông góc (Nadir 90°), hiển thị toàn bộ con đường và các vị trí nghi vấn được đóng khung Bounding Box kèm số thứ tự từ #{start_num} đến #{end_num}.
2. CÁC ẢNH CẬN CẢNH PHÓNG TO (Zoom-in Crops): Tương ứng với từng số thứ tự #{start_num} đến #{end_num}.

THÔNG TIN TUYẾN ĐƯỜNG TỪ HỆ THỐNG QUẢN TRỊ (BE):
- Tên tuyến: {road_name}
- Chiều rộng mặt đường bê tông: {road_width} mét
- Đặc điểm kết cấu: {pavement_type}

NHIỆM VỤ THẨM ĐỊNH HAI TẦNG (TWO-STAGE DUAL-VIEW INSPECTION):
A. ĐỐI CHIẾU BỐI CẢNH TOÀN CỤC (Từ Ảnh Overview):
   - Quan sát vị trí khuyết tật: Nằm trong lòng mặt đường bê tông chính hay ngoài lề cỏ/vệ đường?
   - PHÂN BIỆT KHE CO GIÃN THIẾT KẾ: Mặt đường bê tông xi măng có các khe co giãn/khe nối thi công cắt ngang thẳng tắp, cách đều nhau ~4m đến 5m. Nếu vị trí nghi vấn trùng với mạch khe này -> Phán quyết BÁO ĐỘNG GIẢ (is_valid: false, fine_tag: "false_alarm_joint").
   - PHÂN BIỆT BÓNG DÂY ĐIỆN / BÓNG CÂY: Dây điện mảnh giăng trên cao hoặc bóng cây ven đường rọi xiên xuống tạo thành các vệt đen dài cắt chéo lòng đường -> Phán quyết BÁO ĐỘNG GIẢ (is_valid: false, fine_tag: "false_alarm_cable_shadow").
   - LOẠI BỎ TẠP VẬT NGOÀI ĐƯỜNG: Thùng rác ở lề đường, nắp cống ven đường, vật liệu rơi vãi -> Phán quyết BÁO ĐỘNG GIẢ (is_valid: false, fine_tag: "false_alarm_object").

B. THẨM ĐỊNH VI CẤU TRÚC (Từ Ảnh Crop Cận Cảnh):
   - Nếu là khuyết tật kết cấu thật (Vết nứt hoặc Ổ gà): Xác định hình thái (nứt dọc tim đường "crack_longitudinal", nứt ngang "crack_transverse", nứt lưới mai rùa "crack_alligator", nứt mép tấm đan "crack_edge", nứt khối "crack_block", ổ gà nông "pothole_shallow", ổ gà sâu "pothole_deep").
   - Đánh giá độ mở: "<3mm" (nhỏ), "3-6mm" (trung bình), ">6mm" (nghiêm trọng).
   - Mức độ nguy cơ: "LOW", "MEDIUM", "CRITICAL".

C. NHẬN ĐỊNH CHUYÊN MÔN THUẦN TÚY (reasoning):
   - Đưa ra phân tích kỹ thuật tự nhiên, sắc sảo bằng tiếng Việt do chính bạn suy luận: Miêu tả chi tiết hình thái hư hại, vị trí trên tấm đan bê tông (góc tấm, giữa tấm, gần mép lề), giải thích lý do xác nhận lỗi hoặc lý do loại trừ (khe co giãn / bóng dây điện), và đề xuất giải pháp xử lý công trình (trám matit bitum nóng, bơm keo epoxy, hay đục thay tấm đan). Tuyệt đối không sao chép khuôn mẫu.

BẮT BUỘC chỉ trả về 1 mảng JSON chứa đúng {c_count} phần tử từ #{start_num} đến #{end_num}:
[
  {{
    "index": {start_num},
    "is_valid": true,
    "action": "KEEP",
    "fine_tag": "crack_longitudinal",
    "crack_width": "3-6mm",
    "severity": "MEDIUM",
    "reasoning": "Văn bản phân tích kỹ thuật tự nhiên do KTV tự suy luận"
  }},
  ...
]
"""
            content_parts = [{"type": "text", "text": prompt_dual}]

            # Đính kèm ảnh Overview bối cảnh nếu có
            if annotated_overview_b64:
                content_parts.append({
                    "type": "text",
                    "text": "=== ẢNH TOÀN CẢNH BỐI CẢNH (OVERVIEW FRAME) ==="
                })
                content_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{annotated_overview_b64}",
                        "detail": "high"
                    }
                })

            # Đính kèm từng ảnh Crop chi tiết tương ứng với các số thứ tự
            for idx_in_chunk, it in enumerate(chunk_items):
                num = start_num + idx_in_chunk
                c_path = it.get("crop_path") or it.get("crop_file")
                b64_crop = None
                if c_path and Path(c_path).exists():
                    b64_crop = self._encode_image_b64(c_path)
                elif "crop_img" in it and isinstance(it["crop_img"], np.ndarray):
                    ret, c_buf = cv2.imencode(".jpg", it["crop_img"], [cv2.IMWRITE_JPEG_QUALITY, 90])
                    if ret:
                        b64_crop = base64.b64encode(c_buf).decode("utf-8")

                if b64_crop:
                    content_parts.append({
                        "type": "text",
                        "text": f"--- ẢNH CẬN CẢNH PHÓNG TO KHUYẾT TẬT #{num} ---"
                    })
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64_crop}",
                            "detail": "high"
                        }
                    })

            # Gửi request tới GPT-5.4 Vision
            eval_map = {}
            for attempt in range(1, self.max_retries + 1):
                try:
                    res = self._client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": content_parts}],
                        max_tokens=4096
                    )
                    raw_text = (res.choices[0].message.content or "").strip()
                    if "lỗi nội bộ" in raw_text.lower():
                        time.sleep(1.5 * attempt)
                        continue

                    parsed_list = self._extract_json_list(raw_text)
                    if parsed_list and isinstance(parsed_list, list):
                        for entry in parsed_list:
                            idx = entry.get("index")
                            if idx is not None:
                                try:
                                    eval_map[int(idx)] = entry
                                except Exception:
                                    pass
                        if len(eval_map) >= int(c_count * 0.7):
                            break
                except Exception:
                    time.sleep(1.5 * attempt)

            # Ghép kết quả đánh giá vào từng khuyết tật
            for idx_in_chunk, it in enumerate(chunk_items):
                num = start_num + idx_in_chunk
                c_path = Path(it.get("crop_path") or it.get("crop_file") or "")
                b_cls = it.get("class_name", "crack")
                conf = float(it.get("confidence", 0.5))

                if num in eval_map:
                    entry = eval_map[num]
                    is_valid = bool(entry.get("is_valid", False))
                    raw_fine_tag = str(entry.get("fine_tag", "crack_longitudinal"))
                    severity = str(entry.get("severity", "MEDIUM" if is_valid else "NONE")).upper()
                    if severity not in ["LOW", "MEDIUM", "CRITICAL", "NONE"]:
                        severity = "MEDIUM" if is_valid else "NONE"
                    crack_width = str(entry.get("crack_width", "3-6mm"))
                    action = str(entry.get("action", "KEEP" if is_valid else "DISCARD")).upper()
                    reasoning = str(entry.get("reasoning", "Thẩm định bối cảnh hoàn tất."))

                    friendly_tag = TAG_MAP.get(raw_fine_tag, raw_fine_tag)
                    if not is_valid:
                        yolo_cls = -1
                    elif "pothole" in raw_fine_tag:
                        yolo_cls = 0
                    else:
                        yolo_cls = 1

                    meta_risk = ""
                    meta_recom = ""
                    if is_valid and yolo_cls == 1:
                        c_meta = CRACK_CLASSES.get(raw_fine_tag, CRACK_CLASSES.get("crack_longitudinal", {}))
                        meta_risk = c_meta.get("default_risk", "")
                        meta_recom = c_meta.get("default_recommendation", "")

                    kdv_res = {
                        "inspector": f"KTV Context ({self.model})",
                        "is_valid": is_valid,
                        "action": action,
                        "status": "VERIFIED" if is_valid else "FALSE_ALARM",
                        "tag_category": "positive_defect" if is_valid else "hard_negative",
                        "fine_tag": friendly_tag,
                        "fine_tag_code": raw_fine_tag,
                        "severity": severity,
                        "crack_width_level": crack_width,
                        "structural_risk": meta_risk,
                        "recommendation": meta_recom,
                        "confidence_verified": round(conf, 2),
                        "reasoning": reasoning,
                        "yolo_class_id": yolo_cls
                    }
                else:
                    kdv_res = self._heuristic_fallback(c_path, b_cls, conf, "KTV Context Fallback")

                all_results.append({**it, **kdv_res})

        return all_results

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Trích xuất dictionary từ văn bản trả về của LLM."""
        try:
            return json.loads(text)
        except Exception:
            pass

        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except Exception:
                pass

        return None

    def _extract_json_list(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """Trích xuất mảng JSON từ phản hồi LLM."""
        try:
            val = json.loads(text)
            if isinstance(val, list):
                return val
        except Exception:
            pass

        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if match:
            try:
                val = json.loads(match.group(1))
                if isinstance(val, list):
                    return val
            except Exception:
                pass

        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                val = json.loads(text[start:end+1])
                if isinstance(val, list):
                    return val
            except Exception:
                pass

        return None

    def _create_mosaic_grid(
        self,
        chunk_items: List[Dict[str, Any]],
        start_index: int,
        cell_size: int = 180
    ) -> Optional[str]:
        """Tạo ảnh ghép mosaic cho một nhóm ảnh crop (tối đa 25 ảnh / bảng lưới 5x5)."""
        if not chunk_items:
            return None
        n = len(chunk_items)
        cols = min(5, n)
        rows = int(math.ceil(n / cols))
        mosaic = np.zeros((rows * cell_size, cols * cell_size, 3), dtype=np.uint8)

        for i, it in enumerate(chunk_items):
            item_num = start_index + i
            r = i // cols
            c = i % cols

            c_path = it.get("crop_path") or it.get("crop_file")
            img = None
            if c_path and Path(c_path).exists():
                try:
                    img = cv2.imdecode(np.fromfile(str(c_path), dtype=np.uint8), cv2.IMREAD_COLOR)
                except Exception:
                    img = None

            if img is None or img.size == 0:
                img = np.zeros((cell_size, cell_size, 3), dtype=np.uint8)
            else:
                img = cv2.resize(img, (cell_size, cell_size), interpolation=cv2.INTER_AREA)

            # Vẽ badge số thứ tự nổi bật ở góc trên bên trái
            cv2.rectangle(img, (0, 0), (64, 24), (0, 0, 0), -1)
            cv2.putText(img, f"#{item_num}", (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
            mosaic[r*cell_size:(r+1)*cell_size, c*cell_size:(c+1)*cell_size] = img

        ret, buf = cv2.imencode(".jpg", mosaic, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret:
            return base64.b64encode(buf).decode("utf-8")
        return None

    def inspect_batch_crops(
        self,
        items: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Thẩm định hàng loạt ảnh crop khuyết tật bằng 1 request cho mỗi 100 ảnh (Batching Mosaic).
        Đồng thời yêu cầu KTV phân loại chi tiết và nhận diện các đối tượng trùng lặp.
        """
        if not items:
            return []

        # Nếu không có OpenAI client -> Fallback sang Heuristic CV + CrackAnalyzer
        if not self.is_available:
            results = []
            for it in items:
                c_path = Path(it.get("crop_path") or it.get("crop_file") or "")
                b_cls = it.get("class_name", "crack")
                conf = float(it.get("confidence", 0.5))
                fb = self._heuristic_fallback(c_path, b_cls, conf, "OpenAI client chưa sẵn sàng")
                results.append({**it, **fb})
            return results

        all_results = []
        total_items = len(items)

        # Xử lý theo từng lô tối đa 100 ảnh / 1 request duy nhất
        for b_start in range(0, total_items, batch_size):
            batch_items = items[b_start:b_start + batch_size]
            b_count = len(batch_items)

            prompt = f"""Bạn là KTV (Kỹ Thuật Viên Giám Định) - Chuyên gia Cao cấp Giám định Mặt đường Giao thông của dự án RoadGuard.
Dưới đây là bảng ảnh ghép cận cảnh (Mosaic) gồm {b_count} ảnh khuyết tật được đánh số thứ tự từ #1 đến #{b_count}.
Model dò quét nhanh trước đó (YOLO) đã phát hiện các vị trí này. Tuy nhiên dữ liệu thực địa có thể chứa cả khuyết tật thật lẫn BÁO ĐỘNG GIẢ (khe co giãn / khe nối thi công tấm đan bê tông, bóng dây điện mảnh rọi xiên, bóng cây, thùng rác ven đường, đèn đường, nắp cống, rãnh biên, vệt lốp xe, mặt đường sạch...).

Nhiệm vụ của bạn cho TỪNG Ô TỪ #1 ĐẾN #{b_count}:
1. is_valid: true nếu là ổ gà thật hoặc vết nứt kết cấu thật; false nếu là BÁO ĐỘNG GIẢ.
2. fine_tag:
   - "crack_longitudinal": Vết nứt dọc theo tim tuyến đường
   - "crack_transverse": Vết nứt ngang cắt ngang tấm đan bê tông
   - "crack_alligator": Vết nứt chân chim / nứt lưới mai rùa đa giác
   - "crack_edge": Vết nứt mép tấm đan bê tông / vai đường
   - "crack_block": Vết nứt khối / ô bàn cờ
   - "pothole_shallow": Ổ gà nông bề mặt (< 3cm)
   - "pothole_deep_water": Ổ gà sâu hoặc đọng nước nguy hiểm
   - "pothole_deep": Ổ gà sâu (> 5cm)
   - "false_alarm_joint": Báo động giả do khe co giãn / khe thi công tiêu chuẩn giữa các tấm đan bê tông xi măng
   - "false_alarm_cable_shadow": Báo động giả do bóng dây điện mảnh trên cao rọi chéo xuống hoặc bóng cây
   - "false_alarm_object": Báo động giả do vật thể ngoại lai ven đường (thùng rác lề đường, nắp cống, rãnh, xe cộ)
   - "false_alarm_debris": Báo động giả do vệt sơn, rác, vệt dầu mỡ, bùn bẩn
3. crack_width: "<3mm" (nhỏ), "3-6mm" (trung bình), ">6mm" (toác rộng) - chỉ áp dụng nếu là vết nứt.
4. severity: LOW, MEDIUM, CRITICAL (hoặc NONE nếu false alarm).
5. duplicate_of: null (nếu là khuyết tật độc nhất) hoặc ghi số thứ tự index gốc (ví dụ: 1) nếu ô này chụp CÙNG MỘT khuyết tật với ô trước đó.
6. reasoning: Nhận định kỹ thuật thuần túy, sắc sảo bằng tiếng Việt tự nhiên do chính bạn suy luận: nêu rõ hình thái mép nứt/bề mặt, giải thích cặn kẽ tại sao xác nhận lỗi hoặc tại sao loại trừ (do khe co giãn bê tông / bóng dây điện) và đề xuất hướng xử lý kỹ thuật. Tuyệt đối không viết khuôn mẫu.

BẮT BUỘC chỉ trả về 1 mảng JSON chứa đúng {b_count} phần tử tương ứng thứ tự index từ 1 đến {b_count}:
[
  {{"index": 1, "is_valid": true, "fine_tag": "crack_longitudinal", "crack_width": "3-6mm", "severity": "MEDIUM", "duplicate_of": null, "reasoning": "Vết nứt dọc mở rộng dọc theo dải vệt bánh xe, mép nứt có dấu hiệu bong nhẹ, cần xử lý trám khe bitum nóng để ngăn nước thâm nhập xuống móng đường."}},
  ...
]
"""
            content_parts = [{"type": "text", "text": prompt}]

            # Chia lô 100 ảnh thành các bảng con 25 ảnh (5x5) để giữ độ phân giải sắc nét
            sub_chunk_size = 25
            for sub_idx in range(0, b_count, sub_chunk_size):
                sub_items = batch_items[sub_idx:sub_idx + sub_chunk_size]
                start_num = sub_idx + 1
                end_num = sub_idx + len(sub_items)
                b64_mosaic = self._create_mosaic_grid(sub_items, start_index=start_num)
                if b64_mosaic:
                    content_parts.append({
                        "type": "text",
                        "text": f"=== BẢNG LƯỚI KHUYẾT TẬT: #{start_num} ĐẾN #{end_num} ==="
                    })
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64_mosaic}",
                            "detail": "high"
                        }
                    })

            batch_eval_map = {}
            for attempt in range(1, self.max_retries + 1):
                try:
                    res = self._client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": content_parts}],
                        max_tokens=8192
                    )
                    raw_text = (res.choices[0].message.content or "").strip()
                    if "lỗi nội bộ" in raw_text.lower():
                        time.sleep(1.5 * attempt)
                        continue

                    parsed_list = self._extract_json_list(raw_text)
                    if parsed_list and isinstance(parsed_list, list):
                        for entry in parsed_list:
                            idx = entry.get("index")
                            if idx is not None:
                                try:
                                    batch_eval_map[int(idx)] = entry
                                except Exception:
                                    pass
                        if len(batch_eval_map) >= int(b_count * 0.7):
                            break
                except Exception:
                    time.sleep(1.5 * attempt)

            # Ghép kết quả vào từng item trong batch
            for i, it in enumerate(batch_items, start=1):
                c_path = Path(it.get("crop_path") or it.get("crop_file") or "")
                b_cls = it.get("class_name", "crack")
                conf = float(it.get("confidence", 0.5))

                if i in batch_eval_map:
                    entry = batch_eval_map[i]
                    is_valid = bool(entry.get("is_valid", False))
                    raw_fine_tag = str(entry.get("fine_tag", "crack_longitudinal"))
                    severity = str(entry.get("severity", "MEDIUM" if is_valid else "NONE")).upper()
                    if severity not in ["LOW", "MEDIUM", "CRITICAL", "NONE"]:
                        severity = "MEDIUM" if is_valid else "NONE"
                    crack_width = str(entry.get("crack_width", "3-6mm"))
                    dup_of = entry.get("duplicate_of")
                    reasoning = str(entry.get("reasoning", "Thẩm định tự động bởi KTV."))

                    friendly_tag = TAG_MAP.get(raw_fine_tag, raw_fine_tag)
                    if not is_valid:
                        yolo_cls = -1
                    elif "pothole" in raw_fine_tag:
                        yolo_cls = 0
                    else:
                        yolo_cls = 1

                    meta_risk = ""
                    meta_recom = ""
                    if is_valid and yolo_cls == 1:
                        c_meta = CRACK_CLASSES.get(raw_fine_tag, CRACK_CLASSES["crack_longitudinal"])
                        meta_risk = c_meta["default_risk"]
                        meta_recom = c_meta["default_recommendation"]

                    kdv_res = {
                        "inspector": f"KTV ({self.model} • Batch 100)",
                        "is_valid": is_valid,
                        "status": "VERIFIED" if is_valid else "FALSE_ALARM",
                        "tag_category": "positive_defect" if is_valid else "hard_negative",
                        "fine_tag": friendly_tag,
                        "fine_tag_code": raw_fine_tag,
                        "severity": severity,
                        "crack_width_level": crack_width,
                        "structural_risk": meta_risk,
                        "recommendation": meta_recom,
                        "confidence_verified": round(conf, 2),
                        "reasoning": reasoning,
                        "duplicate_of": dup_of,
                        "yolo_class_id": yolo_cls
                    }
                else:
                    # Dự phòng cho item đơn lẻ bị thiếu
                    kdv_res = self._heuristic_fallback(c_path, b_cls, conf, "KTV Batch Fallback")

                all_results.append({**it, **kdv_res})

        return all_results

    def _heuristic_fallback(
        self,
        crop_path: Path,
        base_class: str,
        confidence: float,
        reason_msg: str
    ) -> Dict[str, Any]:
        """Dự phòng khi API Vision ngoại tuyến: Phân tích kết hợp Heuristic & CrackAnalyzer."""
        try:
            img = cv2.imdecode(np.fromfile(str(crop_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        except Exception:
            img = None

        if img is None:
            return {
                "inspector": "Fallback Heuristic",
                "is_valid": False,
                "status": "ERROR",
                "tag_category": "error",
                "fine_tag": "Lỗi đọc ảnh",
                "severity": "NONE",
                "confidence_verified": 0.0,
                "reasoning": f"Fallback: Không đọc được ảnh ({reason_msg})",
                "yolo_class_id": -1
            }

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = img.shape[:2]
        edges = cv2.Canny(gray, 40, 130)
        edge_ratio = float(np.count_nonzero(edges) / max(1, h * w))
        std_brightness = float(np.std(gray))
        mean_brightness = float(np.mean(gray))

        # Nhận diện vùng phẳng / bóng râm / bóng dây điện mờ
        is_false = (edge_ratio < 0.015 and std_brightness < 10.0)
        if is_false:
            return {
                "inspector": "KTV (Heuristic Fallback)",
                "is_valid": False,
                "status": "FALSE_ALARM",
                "tag_category": "hard_negative",
                "fine_tag": TAG_MAP["false_alarm_shadow"],
                "fine_tag_code": "false_alarm_shadow",
                "severity": "NONE",
                "confidence_verified": round(min(confidence, 0.35), 2),
                "reasoning": f"[KTV Phân tích Hình thái] Bề mặt tương đối đồng nhất (độ lệch chuẩn độ sáng sigma={std_brightness:.1f}, tỷ lệ biên={edge_ratio*100:.2f}%), không phát hiện gãy vỡ hay khe hở vật lý trên kết cấu bê tông. Kết luận là bóng râm hoặc vệt quang học ngoài đường ({reason_msg}).",
                "yolo_class_id": -1
            }

        if base_class == "pothole":
            # Phân tích độ trũng tối và viền hố ổ gà
            dark_pixels = np.count_nonzero(gray < (mean_brightness - 25))
            dark_ratio = float(dark_pixels / max(1, h * w))
            if dark_ratio > 0.20:
                fine_tag_code = "pothole_deep"
                sev = "CRITICAL"
                depth_desc = "khoét sâu (>5cm) có nguy cơ ảnh hưởng lớp móng"
                recom = "Cần cắt vuông góc mép hố, đầm lèn móng và hoàn trả bê tông mác cao ngay."
            else:
                fine_tag_code = "pothole_shallow"
                sev = "MEDIUM"
                depth_desc = "nông (<3cm) do bong bật lớp vữa mặt"
                recom = "Cần vệ sinh thổi bụi và trám vá nguội hoặc bitum chuyên dụng."

            return {
                "inspector": "KTV (Heuristic Fallback)",
                "is_valid": True,
                "status": "VERIFIED",
                "tag_category": "positive_defect",
                "fine_tag": TAG_MAP[fine_tag_code],
                "fine_tag_code": fine_tag_code,
                "severity": sev,
                "confidence_verified": round(confidence, 2),
                "reasoning": f"[KTV Đánh giá Kết cấu] Phát hiện hố sụt {depth_desc} với tỷ lệ vùng trũng tối {dark_ratio*100:.1f}%. Thành mép hố có dấu hiệu vỡ vụn dưới tác động xe cộ. Khuyến nghị: {recom} ({reason_msg})",
                "yolo_class_id": 0
            }

        # Nếu là vết nứt -> Chạy phân tích chuyên sâu từ CrackAnalyzer
        crack_analysis = CrackAnalyzer.analyze_crop_image(img, confidence=confidence)
        crack_analysis["inspector"] = "KTV (CrackAnalyzer Fallback)"
        crack_analysis["reasoning"] = f"[KTV Chẩn đoán Nứt] {crack_analysis['reasoning']} ({reason_msg})"
        return crack_analysis

    def inspect_batch(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Thẩm định hàng loạt ảnh crop được chọn."""
        results = []
        for item in items:
            crop_path = item.get("crop_path") or item.get("crop_file")
            base_cls = item.get("class_name", "crack")
            conf = float(item.get("confidence", 0.5))

            curation_res = self.inspect_crop(crop_path, base_cls, conf)
            merged = {**item, **curation_res}
            results.append(merged)
        return results
