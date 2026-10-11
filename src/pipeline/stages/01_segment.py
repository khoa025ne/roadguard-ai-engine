"""
src/pipeline/stages/01_segment.py — Giai đoạn 1: Phân Đoạn & Tạo Mask Mặt Đường (Road Surface Segmentation)
========================================================================================================
Nhiệm vụ:
  - Tách nền lòng đường bằng mô hình Deep Learning (YOLOv11-seg Road Model) kết hợp dự phòng Heuristic.
  - Tạo mặt nạ nhị phân (Binary Road Mask: 255 = mặt đường, 0 = ngoại cảnh).
  - Lọc bỏ vùng ngoại cảnh (lề cỏ, cây cối, ruộng vườn, vỉa hè) chuẩn bị ROI cho các giai đoạn tiếp theo.

Interface:
  def run(ctx: dict) -> dict
"""

from pathlib import Path
from typing import Dict, Any, Optional
import cv2
import numpy as np

# Cache model toàn cục tránh tải lại trọng số cho từng khung hình
_CACHED_SEG_MODEL = None
_CACHED_SEG_PATH = None


def get_segmentation_model(model_path: str | Path):
    """Tải và lưu đệm mô hình YOLO segmentation."""
    global _CACHED_SEG_MODEL, _CACHED_SEG_PATH
    p = Path(model_path)
    if not p.exists():
        return None
    if _CACHED_SEG_MODEL is not None and _CACHED_SEG_PATH == str(p):
        return _CACHED_SEG_MODEL

    try:
        from ultralytics import YOLO
        _CACHED_SEG_MODEL = YOLO(str(p))
        _CACHED_SEG_PATH = str(p)
        return _CACHED_SEG_MODEL
    except Exception as e:
        print(f"⚠️ Không thể khởi tạo mô hình YOLO-seg từ {p}: {e}")
        return None


def generate_road_mask_yolo(
    frame: np.ndarray,
    model,
    conf_threshold: float = 0.25,
    morph_kernel_size: int = 15
) -> np.ndarray:
    """
    Sinh mask mặt đường bằng mô hình YOLO Segmentation.
    """
    H, W = frame.shape[:2]
    mask = np.zeros((H, W), dtype=np.uint8)

    try:
        preds = model(frame, conf=conf_threshold, imgsz=640, verbose=False)
        if not preds or preds[0].masks is None or len(preds[0].masks) == 0:
            return mask

        r = preds[0]
        # Hợp nhất tất cả các masks thuộc lớp road (class_id == 0)
        for m_idx, cls_tensor in enumerate(r.boxes.cls):
            cls_id = int(cls_tensor.cpu().numpy())
            if cls_id == 0 or len(model.names) == 1:
                m_data = r.masks.data[m_idx].cpu().numpy()
                m_resized = cv2.resize(m_data, (W, H), interpolation=cv2.INTER_NEAREST)
                mask = np.maximum(mask, (m_resized > 0.5).astype(np.uint8) * 255)

        # Phép toán hình thái học (Morphological Closing) để làm mịn viền mép đường
        if morph_kernel_size > 0 and np.any(mask > 0):
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (morph_kernel_size, morph_kernel_size))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    except Exception as e:
        print(f"⚠️ Lỗi trong quá trình suy luận mask mặt đường: {e}")

    return mask


def generate_road_mask_heuristic(
    frame: np.ndarray,
    method: str = "adaptive_otsu",
    top_crop_ratio: float = 0.10,
    bottom_crop_ratio: float = 0.98,
    blur_kernel: int = 5
) -> np.ndarray:
    """
    Dự phòng heuristic (Otsu / HSV) khi chưa nạp được mô hình Deep Learning.
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
        _, otsu_mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        closed = cv2.morphologyEx(otsu_mask, cv2.MORPH_CLOSE, kernel)
        mask[y1:y2, :] = closed
    elif method == "hsv_road":
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        lower_gray = np.array([0, 0, 40])
        upper_gray = np.array([180, 80, 220])
        road_bin = cv2.inRange(hsv, lower_gray, upper_gray)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
        mask[y1:y2, :] = cv2.morphologyEx(road_bin, cv2.MORPH_CLOSE, kernel)
    else:
        mask[y1:y2, :] = 255

    return mask


def run(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Thực thi Stage 01: Segment.
    """
    cfg = ctx.get("config", {}).get("stages", {}).get("01_segment", {})
    if not cfg.get("enabled", True):
        return ctx

    method = cfg.get("method", "yolo_seg")
    model_path = cfg.get("model_path", "weights/pretrained/yolo11m-road-seg.pt")
    conf_thresh = float(cfg.get("conf_threshold", 0.25))
    min_road_ratio = float(cfg.get("min_road_area_ratio", 0.10))

    seg_model = None
    if method == "yolo_seg":
        seg_model = get_segmentation_model(model_path)
        if seg_model is None:
            print(f"ℹ️ [Stage 01] Không thể nạp model {model_path}, chuyển sang dự phòng heuristic adaptive_otsu.")
            method = "adaptive_otsu"

    frames_data = ctx.get("frames", [])
    for f_info in frames_data:
        frame_mat = f_info.get("image")
        if frame_mat is not None and isinstance(frame_mat, np.ndarray):
            H, W = frame_mat.shape[:2]
            if method == "yolo_seg" and seg_model is not None:
                mask = generate_road_mask_yolo(frame_mat, seg_model, conf_threshold=conf_thresh)
            else:
                top_ratio = float(cfg.get("roi_crop_top_ratio", 0.10))
                bottom_ratio = float(cfg.get("roi_crop_bottom_ratio", 0.98))
                blur_k = int(cfg.get("blur_kernel_size", 5))
                mask = generate_road_mask_heuristic(
                    frame_mat,
                    method=method,
                    top_crop_ratio=top_ratio,
                    bottom_crop_ratio=bottom_ratio,
                    blur_kernel=blur_k
                )

            # Tính toán tỷ lệ diện tích lòng đường
            road_pixels = np.count_nonzero(mask)
            road_ratio = road_pixels / (H * W)

            # Nếu mask quá nhỏ (dưới ngưỡng min_road_ratio), fallback an toàn tránh làm mất toàn bộ phát hiện
            if road_ratio < min_road_ratio:
                # Fallback trung tâm
                y1 = int(H * 0.10)
                y2 = int(H * 0.95)
                mask[y1:y2, :] = 255
                road_ratio = np.count_nonzero(mask) / (H * W)

            f_info["road_mask"] = mask
            f_info["road_area_ratio"] = round(road_ratio, 4)

    ctx["stage_01_completed"] = True
    return ctx
