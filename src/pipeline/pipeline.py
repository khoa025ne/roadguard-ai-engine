"""
src/pipeline/pipeline.py — Master Coordinator cho Pipeline Tuyến Tính Kiến Trúc A
===================================================================================
Điều phối tuần tự 7 giai đoạn:
  01_segment -> 02_detect -> 03_filter -> 04_dedup -> 05_measure -> 06_inspect -> 07_report

Quy ước:
  - Mọi cấu hình, ngưỡng, bật/tắt đọc từ configs/pipeline.yaml.
  - Mỗi stage tuân thủ giao thức: def run(ctx: dict) -> dict.
  - Cung cấp run_video_analysis_task(...) làm API thống nhất cho Web UI và CLI.
"""

import os
import sys
import time
import yaml
import cv2
from pathlib import Path
from typing import Dict, Any, Optional, List

from src.ingestion.srt_parser import DJISRTParser
from src.ingestion.video_extractor import VideoFrameExtractor
from src.pipeline.stages import STAGES


DEFAULT_CONFIG_PATH = Path("configs/pipeline.yaml")


def load_pipeline_config(config_path: Optional[str | Path] = None) -> Dict[str, Any]:
    """Tải cấu hình từ configs/pipeline.yaml."""
    cfg_file = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not cfg_file.is_absolute():
        # Tìm theo root dự án
        for candidate in [cfg_file, Path(__file__).resolve().parents[2] / cfg_file]:
            if candidate.exists():
                cfg_file = candidate
                break

    if cfg_file.exists():
        with open(cfg_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


class LinearPipeline:
    """Bộ điều phối Pipeline tuyến tính 7 giai đoạn."""

    def __init__(self, config_path: Optional[str | Path] = None, config_dict: Optional[Dict[str, Any]] = None):
        self.config = config_dict or load_pipeline_config(config_path)
        self.stages = STAGES

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Thực thi tuần tự 7 giai đoạn của pipeline.
        """
        if "config" not in ctx:
            ctx["config"] = self.config
        if "start_time" not in ctx:
            ctx["start_time"] = time.time()

        for stage_name, stage_fn in self.stages:
            stage_cfg = ctx.get("config", {}).get("stages", {}).get(stage_name, {})
            if not stage_cfg.get("enabled", True):
                continue

            t0 = time.perf_counter()
            try:
                ctx = stage_fn(ctx)
            except Exception as e:
                ctx["status"] = "FAILED"
                ctx["error"] = f"Lỗi tại giai đoạn {stage_name}: {str(e)}"
                raise e
            t1 = time.perf_counter()
            ctx[f"timing_{stage_name}_ms"] = round((t1 - t0) * 1000.0, 2)

        return ctx


def run_video_analysis_task(
    video_path: str | Path,
    model_path: Optional[str | Path] = None,
    task_id: Optional[str] = None,
    output_dir: Optional[str | Path] = None,
    srt_path: Optional[str | Path] = None,
    conf_threshold: float = 0.25,
    max_duration_seconds: int = 30,
    sampling_rate_fps: int = 2,
    use_tiling: bool = True,
    config_path: Optional[str | Path] = None,
    progress_callback: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Hàm API chuẩn hóa dùng chung cho Web UI (ui_server.py) và CLI:
    1. Trích xuất frames và đọc telemetry SRT.
    2. Khởi tạo context.
    3. Chạy LinearPipeline 7 stages.
    4. Trả về kết quả báo cáo inspection_report.json và GeoJSON.
    """
    v_path = Path(video_path)
    if not v_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file video: {v_path}")

    t_id = task_id or f"task_{int(time.time())}"
    out_dir = Path(output_dir) if output_dir else Path(f"outputs/reports/{t_id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Đọc phụ đề SRT nếu có
    telemetries = []
    if srt_path and Path(srt_path).exists():
        srt_parser = DJISRTParser()
        telemetries = srt_parser.parse_file(str(srt_path))

    # Đọc video với OpenCV
    cap = cv2.VideoCapture(str(v_path))
    if not cap.isOpened():
        raise IOError(f"Không thể mở file video: {v_path}")

    orig_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_vid_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    target_fps = max(1, sampling_rate_fps)
    frame_step = max(1, int(round(orig_fps / target_fps)))

    if max_duration_seconds > 0:
        max_frames_to_read = min(total_vid_frames, int(max_duration_seconds * orig_fps))
    else:
        max_frames_to_read = total_vid_frames

    frames_data: List[Dict[str, Any]] = []
    processed_count = 0

    for frame_idx in range(0, max_frames_to_read, frame_step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        processed_count += 1
        timestamp_s = round(frame_idx / orig_fps, 2)
        timestamp_ms = int(timestamp_s * 1000)

        # Lấy telemetry gần nhất
        matched_telem = None
        if telemetries:
            matched_telem = min(telemetries, key=lambda t: abs(t.timestamp_ms - timestamp_ms))

        gps_info = {}
        if matched_telem:
            gps_info = {
                "latitude": matched_telem.latitude,
                "longitude": matched_telem.longitude,
                "rel_alt_m": matched_telem.rel_alt_m,
                "gsd_mm_per_px": matched_telem.gsd_mm_per_px
            }

        frames_data.append({
            "frame_index": processed_count,
            "raw_frame_idx": frame_idx,
            "timestamp_s": timestamp_s,
            "filename": f"frame_{processed_count:04d}_{timestamp_s}s.jpg",
            "image": frame,
            "gps": gps_info
        })

    cap.release()

    # Chuẩn bị Context
    cfg = load_pipeline_config(config_path)
    if model_path:
        cfg.setdefault("stages", {}).setdefault("02_detect", {})["model_path"] = str(model_path)
    if conf_threshold:
        cfg.setdefault("stages", {}).setdefault("02_detect", {})["conf_threshold"] = conf_threshold
        cfg.setdefault("stages", {}).setdefault("03_filter", {})["min_confidence"] = conf_threshold

    ctx = {
        "task_id": t_id,
        "video_path": str(v_path),
        "srt_path": str(srt_path) if srt_path else None,
        "model_path": str(model_path) if model_path else cfg.get("general", {}).get("default_weights"),
        "conf_threshold": conf_threshold,
        "use_tiling": use_tiling,
        "output_dir": str(out_dir),
        "frames": frames_data,
        "telemetries": telemetries,
        "config": cfg,
        "start_time": time.time()
    }

    # Chạy Pipeline
    pipeline = LinearPipeline(config_dict=cfg)
    result_ctx = pipeline.run(ctx)

    return result_ctx.get("final_report", {})
