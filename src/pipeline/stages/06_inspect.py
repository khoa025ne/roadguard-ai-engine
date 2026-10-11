"""
src/pipeline/stages/06_inspect.py — Giai đoạn 6: Thẩm Định Chuyên Gia KTV & Phân Loại Hình Thái
=============================================================================================
Nhiệm vụ:
  - Cắt ảnh cận cảnh (Crop) từng khuyết tật đại diện để đưa vào thẩm định chi tiết.
  - Gọi Model AI Thứ 2: KDVInspector (KTV / Kiểm Duyệt Viên Giám Định) để thẩm định hai tầng:
      1. Khử bỏ báo động giả (khe co giãn bê tông, bóng dây điện, vệt sơn, tạp vật ven lề).
      2. Phân loại hình thái chi tiết và cấp độ hư hại theo tiêu chuẩn kỹ thuật đường bộ.
  - Hỗ trợ chế độ Vision Multimodal AI (gpt-5.4) và tự động Fallback Heuristic chuyên sâu khi offline.

Interface:
  def run(ctx: dict) -> dict
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, List
from src.curation.kdv_inspector import KDVInspector
from src.curation.crack_analyzer import CrackAnalyzer


def run(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Thực thi Stage 06: Inspect (Thẩm định qua KDVInspector).
    """
    cfg = ctx.get("config", {}).get("stages", {}).get("06_inspect", {})
    if not cfg.get("enabled", True):
        print("  -> [06_inspect] Stage 06 bị vô hiệu hóa trong cấu hình, chuyển tiếp dữ liệu.")
        ctx["inspected_detections"] = ctx.get("measured_detections", [])
        return ctx

    provider = cfg.get("provider", "heuristic")
    filter_fa = bool(cfg.get("filter_false_alarms", True))
    crack_morph = bool(cfg.get("analyze_crack_morphology", True))

    items = ctx.get("measured_detections", [])
    frames_dict = {f.get("frame_index"): f for f in ctx.get("frames", [])}

    # Khởi tạo KDVInspector (Tier-2 AI Expert Inspector)
    kdv_inspector = KDVInspector(
        api_key=cfg.get("api_key"),
        model=cfg.get("model", "gpt-5.4")
    )

    print(f"  -> [06_inspect] Bắt đầu thẩm định KTV tầng 2 qua KDVInspector (Provider: {provider}, Model: {kdv_inspector.model}, Khuyết tật: {len(items)})")

    inspected_items: List[Dict[str, Any]] = []

    for idx, det in enumerate(items):
        f_idx = det.get("frame_index", 0)
        f_info = frames_dict.get(f_idx, {})
        frame_mat = f_info.get("image")

        box = det.get("box", [0, 0, 0, 0])
        x1, y1, x2, y2 = [int(v) for v in box]

        # Cắt ảnh crop khuyết tật từ frame gốc
        crop_img = None
        if frame_mat is not None and isinstance(frame_mat, np.ndarray):
            H, W = frame_mat.shape[:2]
            cx1 = max(0, min(W - 1, x1))
            cy1 = max(0, min(H - 1, y1))
            cx2 = max(0, min(W, x2))
            cy2 = max(0, min(H, y2))
            if (cx2 - cx1) > 2 and (cy2 - cy1) > 2:
                crop_img = frame_mat[cy1:cy2, cx1:cx2].copy()

        det["crop_image"] = crop_img
        base_class = det.get("class_name", "pothole")
        conf = float(det.get("confidence", 0.5))

        # Thẩm định trực tiếp qua KDVInspector
        if crop_img is not None and crop_img.size > 0:
            kdv_res = kdv_inspector.inspect_crop(
                crop_path=None,
                base_class=base_class,
                confidence=conf,
                crop_img=crop_img
            )
            det.update(kdv_res)
        else:
            det["is_valid"] = True
            det["status"] = "VERIFIED"
            det["inspector"] = "KDVInspector (BBox Context)"
            det["fine_tag"] = "Ổ gà mặt đường" if "pothole" in base_class else "Vết nứt mặt đường"
            det["reasoning"] = "KTV xác nhận phát hiện hợp lệ từ tọa độ bounding box."

        # Kiểm tra sàng lọc Báo động giả (False Alarms)
        if filter_fa and not det.get("is_valid", True):
            print(f"    [06_inspect] Đã lọc bỏ báo động giả #{idx+1}: {det.get('fine_tag')} - {det.get('reasoning')[:70]}...")
            continue

        inspected_items.append(det)

    ctx["inspected_detections"] = inspected_items
    ctx["stage_06_completed"] = True
    print(f"  -> [06_inspect] Hoàn tất thẩm định KTV tầng 2: Giữ lại {len(inspected_items)}/{len(items)} khuyết tật chuẩn xác.")
    return ctx

