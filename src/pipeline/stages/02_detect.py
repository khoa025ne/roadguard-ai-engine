"""
src/pipeline/stages/02_detect.py — Giai đoạn 2: Nhận Diện Khuyết Tật Đối Tượng (YOLO Object Detection)
=====================================================================================================
Nhiệm vụ:
  - Nạp mô hình YOLO từ file trọng số được chỉ định trong config hoặc context.
  - Thực hiện inference theo kỹ thuật Tiling 640x640 gối đầu 20% hoặc toàn khung hình.
  - Ánh xạ class ID sang tên chuẩn hóa dựa trên class_map.json.

Interface:
  def run(ctx: dict) -> dict
"""

from pathlib import Path
from typing import Dict, Any, List
import numpy as np
from src.inference.predictor import RoadDefectPredictor


def run(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Thực thi Stage 02: Detect.
    """
    cfg = ctx.get("config", {}).get("stages", {}).get("02_detect", {})
    if not cfg.get("enabled", True):
        return ctx

    # Ưu tiên lấy model_path từ runtime ctx (ví dụ người dùng chọn trên Web UI)
    model_path = ctx.get("model_path") or cfg.get("model_path") or "weights/trained/roadguard_best_15k.pt"
    conf_threshold = float(ctx.get("conf_threshold") or cfg.get("conf_threshold", 0.25))
    use_tiling = bool(ctx.get("use_tiling", cfg.get("use_tiling", True)))
    class_map_path = ctx.get("class_map_path") or ctx.get("config", {}).get("general", {}).get("class_map_path", "class_map.json")

    predictor = ctx.get("predictor")
    if predictor is None or str(predictor.model_path) != str(Path(model_path)):
        predictor = RoadDefectPredictor(
            model_path=model_path,
            conf_threshold=conf_threshold,
            class_map_path=class_map_path
        )
        ctx["predictor"] = predictor

    frames_data = ctx.get("frames", [])
    all_raw_detections: List[Dict[str, Any]] = []

    for f_info in frames_data:
        frame_mat = f_info.get("image")
        if frame_mat is None or not isinstance(frame_mat, np.ndarray):
            continue

        dets = predictor.predict_full_frame(frame_mat, use_tiling=use_tiling)
        f_idx = f_info.get("frame_index", 0)
        t_sec = f_info.get("timestamp_s", 0.0)

        for d in dets:
            d["frame_index"] = f_idx
            d["timestamp_s"] = t_sec
            d["frame_file"] = f_info.get("filename", "")
            d["raw_image_shape"] = frame_mat.shape[:2]

        f_info["raw_detections"] = dets
        all_raw_detections.extend(dets)

    ctx["raw_detections"] = all_raw_detections
    ctx["stage_02_completed"] = True
    return ctx
