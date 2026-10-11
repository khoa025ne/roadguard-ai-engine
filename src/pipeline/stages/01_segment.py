"""
src/pipeline/stages/01_segment.py — Giai đoạn 1: Phân Đoạn & Tạo Mask Mặt Đường (Road Surface Segmentation)
========================================================================================================
Nhiệm vụ:
  - Tách nền lòng đường, tạo mặt nạ nhị phân (Binary Road Mask: 255 = mặt đường, 0 = ngoại cảnh).
  - Lọc bỏ vùng ngoại vi (chân trời, cây cối, vỉa hè) để chuẩn bị ROI sạch cho giai đoạn nhận diện.

Interface:
  def run(ctx: dict) -> dict
"""

import cv2
import numpy as np
from typing import Dict, Any


def generate_road_mask(
    frame: np.ndarray,
    method: str = "adaptive_otsu",
    top_crop_ratio: float = 0.15,
    bottom_crop_ratio: float = 0.98,
    blur_kernel: int = 5
) -> np.ndarray:
    """
    Tạo mặt nạ nhị phân xác định vùng lòng đường thực tế.
    """
    H, W = frame.shape[:2]
    mask = np.zeros((H, W), dtype=np.uint8)

    y1 = int(H * max(0.0, top_crop_ratio))
    y2 = int(H * min(1.0, bottom_crop_ratio))
    roi = frame[y1:y2, :]

    if roi.size == 0:
        mask[:] = 255
        return mask

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (blur_kernel, blur_kernel), 0)

    if method == "adaptive_otsu":
        # Mặt đường bê tông / nhựa thường có độ xám đồng nhất trong dải trung tính
        _, otsu_mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # Sử dụng phép toán hình thái học (Morphological Closing) để lấp các lỗ rỗng
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        closed = cv2.morphologyEx(otsu_mask, cv2.MORPH_CLOSE, kernel)
        mask[y1:y2, :] = closed
    elif method == "hsv_road":
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        # Lòng đường: Độ bão hòa thấp (S thấp)
        lower_gray = np.array([0, 0, 40])
        upper_gray = np.array([180, 80, 220])
        road_bin = cv2.inRange(hsv, lower_gray, upper_gray)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
        mask[y1:y2, :] = cv2.morphologyEx(road_bin, cv2.MORPH_CLOSE, kernel)
    else:
        # Fallback: Coi toàn bộ ROI hợp lệ là mặt đường
        mask[y1:y2, :] = 255

    return mask


def run(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Thực thi Stage 01: Segment.
    """
    cfg = ctx.get("config", {}).get("stages", {}).get("01_segment", {})
    if not cfg.get("enabled", True):
        return ctx

    method = cfg.get("method", "adaptive_otsu")
    top_ratio = float(cfg.get("roi_crop_top_ratio", 0.15))
    bottom_ratio = float(cfg.get("roi_crop_bottom_ratio", 0.98))
    blur_k = int(cfg.get("blur_kernel_size", 5))

    frames_data = ctx.get("frames", [])
    for f_info in frames_data:
        frame_mat = f_info.get("image")
        if frame_mat is not None and isinstance(frame_mat, np.ndarray):
            mask = generate_road_mask(
                frame_mat,
                method=method,
                top_crop_ratio=top_ratio,
                bottom_crop_ratio=bottom_ratio,
                blur_kernel=blur_k
            )
            f_info["road_mask"] = mask

    ctx["stage_01_completed"] = True
    return ctx
