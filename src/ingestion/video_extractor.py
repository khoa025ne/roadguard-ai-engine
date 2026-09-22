"""
src/ingestion/video_extractor.py — Trích xuất lấy mẫu khung hình & Lọc mờ
========================================================================
Quản lý sampling rate (mặc định 2fps) và kiểm định chất lượng mờ (KS08).
"""

import cv2
import json
import numpy as np
from pathlib import Path
from tqdm import tqdm
from typing import List, Optional
from .srt_parser import DJISRTParser, FrameTelemetry


class VideoFrameExtractor:
    """Trích xuất khung hình từ video 2.7K, lọc rung mờ và gắn metadata định vị."""

    DEFAULT_CONFIG = {
        "sample_every_n_frames": 15,    # 1 frame / 15 frames = 2fps từ 30fps
        "blur_threshold": 100.0,        # Laplacian variance < 100 coi là mờ
        "output_quality": 95,           # JPEG quality 95%
    }

    def __init__(self, config: dict = None):
        self.cfg = {**self.DEFAULT_CONFIG, **(config or {})}

    def calc_blur_score(self, frame: np.ndarray) -> float:
        """
        Tính điểm sắc nét bằng phương sai toán tử Laplace.
        Score < 100: Ảnh bị rung lắc / mờ (bỏ qua).
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    def extract_frames(
        self,
        video_path: str | Path,
        output_dir: str | Path,
        telemetries: Optional[List[FrameTelemetry]] = None,
        sample_every_n_frames: Optional[int] = None,
        max_frames: Optional[int] = None
    ) -> List[dict]:
        """
        Trích xuất frame từ video, lọc mờ, lưu ảnh và ghi file frame_metadata.json.
        """
        video_path = Path(video_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Không thể mở file video: {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Tự động điều chỉnh sample_rate theo fps nếu không truyền vào (mặc định lấy ~2fps)
        step = sample_every_n_frames or self.cfg.get("sample_every_n_frames") or int(fps / 2)
        step = max(1, step)

        srt_parser = DJISRTParser() if telemetries else None
        frame_metadata = []
        frame_idx = 0
        saved_count = 0
        blurry_count = 0

        pbar = tqdm(total=total_frames, desc=f"🎬 Extracting {video_path.name}", unit="frames")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Kiểm tra giới hạn max_frames
            if max_frames and saved_count >= max_frames:
                break

            # Lấy mẫu theo chu kỳ
            if frame_idx % step == 0:
                blur_score = self.calc_blur_score(frame)
                is_blurry = blur_score < self.cfg["blur_threshold"]

                if is_blurry:
                    blurry_count += 1
                else:
                    gps_data = None
                    if telemetries and srt_parser:
                        matched = srt_parser.get_frame_gps(telemetries, frame_idx, fps)
                        if matched:
                            gps_data = {
                                "latitude": matched.latitude,
                                "longitude": matched.longitude,
                                "rel_alt_m": matched.rel_alt_m,
                                "gimbal_pitch": matched.gimbal_pitch,
                                "gsd_mm_per_px": matched.gsd_mm_per_px,
                                "timestamp_ms": matched.timestamp_ms
                            }

                    frame_name = f"frame_{frame_idx:06d}.jpg"
                    frame_path = output_dir / frame_name
                    cv2.imwrite(
                        str(frame_path),
                        frame,
                        [cv2.IMWRITE_JPEG_QUALITY, self.cfg["output_quality"]]
                    )

                    frame_metadata.append({
                        "frame_index": frame_idx,
                        "filename": frame_name,
                        "blur_score": round(blur_score, 2),
                        "timestamp_ms": int((frame_idx / fps) * 1000),
                        "gps": gps_data
                    })
                    saved_count += 1

            frame_idx += 1
            pbar.update(1)

        pbar.close()
        cap.release()

        # Ghi file metadata
        meta_file = output_dir / "frame_metadata.json"
        summary = {
            "video_file": str(video_path),
            "resolution": f"{width}x{height}",
            "fps": fps,
            "total_frames_in_video": total_frames,
            "extracted_frames": saved_count,
            "skipped_blurry_frames": blurry_count,
            "blur_rate_percent": round((blurry_count / max(1, saved_count + blurry_count)) * 100, 1),
            "frames": frame_metadata
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        return frame_metadata
