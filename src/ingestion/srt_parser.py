"""
src/ingestion/srt_parser.py — Bóc tách Telemetry DJI SRT & Tính toán GSD
=======================================================================
Hỗ trợ dòng drone DJI Mini 2 SE và tương thích với định dạng phụ đề viễn thám.
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple


@dataclass
class FrameTelemetry:
    """Telemetry data cho một khung hình hoặc mốc thời gian."""
    timestamp_ms: int           # Thời gian video tính bằng milliseconds
    latitude: float             # Vĩ độ (WGS84)
    longitude: float            # Kinh độ (WGS84)
    rel_alt_m: float            # Độ cao tương đối so với điểm cất cánh (mét)
    abs_alt_m: float            # Độ cao tuyệt đối so với mực nước biển (mét)
    iso: Optional[int] = None
    shutter: Optional[str] = None
    fnum: Optional[float] = None
    ev: Optional[float] = None
    focal_len_mm: Optional[float] = None
    gimbal_pitch: Optional[float] = None  # Góc nghiêng gimbal (độ)
    gimbal_roll: Optional[float] = None
    gimbal_yaw: Optional[float] = None
    gsd_mm_per_px: Optional[float] = None # Ground Sampling Distance (mm/pixel)


class DJISRTParser:
    """
    Parser phụ đề viễn thám DJI SRT.
    Trích xuất GPS (lat, lon, alt) và góc Gimbal mỗi ~33ms.
    """

    DJI_MINI_2_SE = {
        "sensor_width_mm": 6.17,
        "sensor_height_mm": 4.55,
        "focal_length_actual_mm": 4.26,
        "image_width_px": 2720,
        "image_height_px": 1530,
    }

    # Regex patterns cho các định dạng DJI SRT khác nhau
    PATTERN_V1 = re.compile(
        r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n'
        r'(?:<font[^>]*>)?'
        r'.*?GPS\s*\(([-+]?\d+\.\d+),\s*([-+]?\d+\.\d+)(?:,\s*[-+]?\d+\.?\d*)?\)'
        r'.*?(?:BAROMETER|ALT|altitude):\s*([-+]?\d+\.?\d*)m?'
        r'.*?(?:rel_alt|relative_altitude):\s*([-+]?\d+\.?\d*)m?',
        re.DOTALL | re.IGNORECASE
    )

    PATTERN_SIMPLE = re.compile(
        r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n'
        r'(.*?)(?=\n\n|\Z)',
        re.DOTALL
    )

    def __init__(self, drone_specs: dict = None):
        self.specs = drone_specs or self.DJI_MINI_2_SE

    def parse_timestamp_ms(self, ts_str: str) -> int:
        """Đổi format HH:MM:SS,mmm thành milliseconds."""
        h, m, rest = ts_str.split(':')
        s, ms = rest.split(',')
        return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)

    def calc_gsd(self, altitude_m: float) -> float:
        """Tính GSD (mm/pixel) từ độ cao bay tương đối."""
        if altitude_m <= 0:
            return 0.0
        return (altitude_m * 1000.0 * self.specs["sensor_width_mm"]) / \
               (self.specs["focal_length_actual_mm"] * self.specs["image_width_px"])

    def parse_srt_block(self, content: str, start_ms: int) -> Optional[FrameTelemetry]:
        """Parse nội dung text trong một block phụ đề SRT."""
        # Trích xuất GPS (lat, lon)
        gps_match = re.search(r'\[(?:latitude|lat)\s*:\s*([-+]?\d+\.\d+)\]\s*\[(?:longitude|lon)\s*:\s*([-+]?\d+\.\d+)\]', content, re.I)
        if not gps_match:
            gps_match = re.search(r'GPS\s*\(([-+]?\d+\.\d+),\s*([-+]?\d+\.\d+)', content, re.I)
        if not gps_match:
            gps_match = re.search(r'([-+]?\d+\.\d{5,}),\s*([-+]?\d+\.\d{5,})', content)

        if not gps_match:
            return None

        lat = float(gps_match.group(1))
        lon = float(gps_match.group(2))

        # Trích xuất độ cao
        rel_alt_m = 10.0  # default fallback nếu không tìm thấy
        rel_match = re.search(r'\[rel_alt:\s*([-+]?\d+\.?\d*)m?\]', content, re.I)
        if rel_match:
            rel_alt_m = float(rel_match.group(1))
        else:
            alt_match = re.search(r'(?:rel_alt|altitude|alt|barometer):\s*([-+]?\d+\.?\d*)m?', content, re.I)
            if alt_match:
                rel_alt_m = float(alt_match.group(1))

        # Góc Gimbal Pitch
        gimbal_pitch = -90.0
        pitch_match = re.search(r'\[(?:gimbal_pitch|pitch):\s*([-+]?\d+\.?\d*)\]', content, re.I)
        if pitch_match:
            gimbal_pitch = float(pitch_match.group(1))

        gsd = self.calc_gsd(rel_alt_m)

        return FrameTelemetry(
            timestamp_ms=start_ms,
            latitude=lat,
            longitude=lon,
            rel_alt_m=rel_alt_m,
            abs_alt_m=rel_alt_m,
            gimbal_pitch=gimbal_pitch,
            gsd_mm_per_px=round(gsd, 3)
        )

    def parse_file(self, srt_path: str | Path) -> List[FrameTelemetry]:
        """Đọc và parse toàn bộ file SRT thành danh sách FrameTelemetry."""
        srt_path = Path(srt_path)
        if not srt_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file SRT: {srt_path}")

        telemetries = []
        with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        blocks = self.PATTERN_SIMPLE.findall(content)
        for start_str, end_str, block_text in blocks:
            try:
                start_ms = self.parse_timestamp_ms(start_str.strip())
                parsed = self.parse_srt_block(block_text, start_ms)
                if parsed:
                    telemetries.append(parsed)
            except Exception:
                continue

        return telemetries

    def get_frame_gps(self, telemetries: List[FrameTelemetry], frame_idx: int, fps: float = 30.0) -> Optional[FrameTelemetry]:
        """Khớp frame_idx với mốc GPS gần nhất theo thời gian."""
        if not telemetries:
            return None
        target_ms = int((frame_idx / fps) * 1000)
        # Tìm phần tử có khoảng cách timestamp_ms nhỏ nhất
        best = min(telemetries, key=lambda t: abs(t.timestamp_ms - target_ms))
        if abs(best.timestamp_ms - target_ms) <= 500:  # dung sai 500ms
            return best
        return None
