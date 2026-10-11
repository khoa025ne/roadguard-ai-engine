"""
src/pipeline/stages/03_filter.py — Giai đoạn 3: Lọc Bounding Box Theo Mask & Ngưỡng Kỹ Thuật
=============================================================================================
Nhiệm vụ:
  - Lọc theo ngưỡng confidence tối thiểu.
  - Lọc theo diện tích Bounding Box tối thiểu (loại bỏ hạt nhiễu nhỏ vài pixel) và tối đa.
  - Lọc theo tỷ lệ giao cắt với Mặt Nạ Mặt Đường (Road Surface Mask Intersection):
    Loại bỏ triệt để các phát hiện nằm ngoài lòng đường (cây cối, bóng râm lề cỏ, nhà cửa).
  - Phân loại & lọc theo TargetBand (SURFACE / LEFT_EDGE / RIGHT_EDGE).

Interface:
  def run(ctx: dict) -> dict
"""

import numpy as np
from typing import Dict, Any, List
from src.inference.tiling_engine import TargetBandClassifier


def check_mask_overlap(box: List[int], mask: np.ndarray, threshold: float = 0.35) -> bool:
    """
    Kiểm tra xem Bounding Box có giao cắt với vùng mặt nạ đường (mask > 0) tối thiểu threshold hay không.
    """
    if mask is None:
        return True

    H, W = mask.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in box]
    x1 = max(0, min(W - 1, x1))
    y1 = max(0, min(H - 1, y1))
    x2 = max(0, min(W, x2))
    y2 = max(0, min(H, y2))

    box_area = (x2 - x1) * (y2 - y1)
    if box_area <= 0:
        return False

    box_mask = mask[y1:y2, x1:x2]
    road_pixels = np.count_nonzero(box_mask)
    overlap_ratio = road_pixels / float(box_area)

    return overlap_ratio >= threshold


def run(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Thực thi Stage 03: Filter.
    """
    cfg = ctx.get("config", {}).get("stages", {}).get("03_filter", {})
    if not cfg.get("enabled", True):
        ctx["filtered_detections"] = ctx.get("raw_detections", [])
        return ctx

    min_conf = float(cfg.get("min_confidence", 0.25))
    min_area = int(cfg.get("min_box_area_px", 64))
    max_area_ratio = float(cfg.get("max_box_area_ratio", 0.50))
    mask_threshold = float(cfg.get("mask_intersection_threshold", 0.35))
    target_band_req = str(cfg.get("target_band", "SURFACE")).upper()

    all_filtered: List[Dict[str, Any]] = []
    frames_data = ctx.get("frames", [])

    for f_info in frames_data:
        raw_dets = f_info.get("raw_detections", [])
        road_mask = f_info.get("road_mask")
        frame_shape = f_info.get("image").shape if f_info.get("image") is not None else (1530, 2720)
        total_frame_area = frame_shape[0] * frame_shape[1]

        f_filtered = []
        for det in raw_dets:
            # 1. Kiểm tra confidence
            if det.get("confidence", 0.0) < min_conf:
                continue

            # 2. Kiểm tra diện tích Box
            box = det.get("box", [0, 0, 0, 0])
            bw = abs(box[2] - box[0])
            bh = abs(box[3] - box[1])
            area = bw * bh
            if area < min_area:
                continue
            if area > (total_frame_area * max_area_ratio):
                continue

            # 3. Kiểm tra giao cắt với Road Mask
            if road_mask is not None and not check_mask_overlap(box, road_mask, threshold=mask_threshold):
                continue

            # 4. Gán và lọc TargetBand
            band = TargetBandClassifier.classify(box, frame_width=frame_shape[1], is_forward=True)
            det["target_band"] = band
            if target_band_req not in ["ALL", "ANY"] and band != target_band_req:
                continue

            f_filtered.append(det)

        f_info["filtered_detections"] = f_filtered
        all_filtered.extend(f_filtered)

    ctx["filtered_detections"] = all_filtered
    ctx["stage_03_completed"] = True
    return ctx
