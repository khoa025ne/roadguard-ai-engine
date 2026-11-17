"""
src/ingestion/srt_parser.py — Bóc tách Telemetry DJI SRT & Tính toán GSD
=======================================================================
Hỗ trợ dòng drone DJI Mini 2 SE và tương thích với định dạng phụ đề viễn thám.
"""

import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class FrameTelemetry:
    """Telemetry data cho một khung hình hoặc mốc thời gian."""
    timestamp_ms: int           # Thời gian video tính bằng milliseconds
    latitude: Optional[float]   # GPS ghi trong SRT; chưa xác minh độ chính xác
    longitude: Optional[float]
    rel_alt_m: Optional[float]  # Chỉ có khi nguồn ghi rõ rel_alt; KHÔNG phải AGL
    abs_alt_m: Optional[float]  # Chỉ có khi nguồn ghi rõ abs_alt
    iso: Optional[int] = None
    shutter: Optional[str] = None
    fnum: Optional[float] = None
    ev: Optional[float] = None
    focal_len_mm: Optional[float] = None
    gimbal_pitch: Optional[float] = None  # Góc nghiêng gimbal (độ)
    gimbal_roll: Optional[float] = None
    gimbal_yaw: Optional[float] = None
    gsd_mm_per_px: Optional[float] = None # Ground Sampling Distance (mm/pixel)
    gps_status: str = "missing"
    altitude_status: str = "missing"
    gimbal_pitch_status: str = "missing"
    reported_h_m: Optional[float] = None  # H nguyên dạng DJI, chưa xác minh hệ quy chiếu
    reported_d_m: Optional[float] = None  # D nguyên dạng DJI, không phải độ cao
    gps_third_value: Optional[float] = None  # Thành phần thứ ba GPS(...), chưa rõ datum
    raw_text: str = ""


class DJISRTParser:
    """
    Parser phụ đề viễn thám DJI SRT.
    Giữ telemetry theo đúng những gì SRT ghi; không tự suy AGL, nadir hoặc GSD.
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
        number = r"([-+]?\d+(?:\.\d+)?)"
        labelled_lat = re.search(r"\[(?:latitude|lat)\s*:\s*" + number + r"\]", content, re.I)
        labelled_lon = re.search(r"\[(?:longitude|lon)\s*:\s*" + number + r"\]", content, re.I)
        gps = re.search(r"GPS\s*\(\s*" + number + r"\s*,\s*" + number +
                        r"(?:\s*,\s*" + number + r")?\s*\)", content, re.I)
        lat = lon = third = None
        gps_status = "missing"
        if labelled_lat and labelled_lon:
            lat, lon = float(labelled_lat.group(1)), float(labelled_lon.group(1))
        elif gps:
            # Format DJI đã đối chiếu với SRT thật: GPS (longitude, latitude, value).
            lon, lat = float(gps.group(1)), float(gps.group(2))
            third = float(gps.group(3)) if gps.group(3) is not None else None
        if lat is not None and lon is not None:
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                gps_status = "present_unverified"
            else:
                lat = lon = None
                gps_status = "invalid"
        elif labelled_lat or labelled_lon or "GPS" in content.upper():
            gps_status = "invalid"

        def field(pattern: str) -> Optional[float]:
            match = re.search(pattern + r"\s*[: ]\s*" + number + r"\s*m?\b", content, re.I)
            return float(match.group(1)) if match else None

        rel_alt_m = field(r"\brel_alt\b")
        abs_alt_m = field(r"\babs_alt\b")
        reported_h_m = field(r"\bH\b")
        reported_d_m = field(r"\bD\b")
        gimbal_pitch = field(r"\b(?:gimbal_pitch|gimbal\s+pitch|pitch)\b")

        return FrameTelemetry(
            timestamp_ms=start_ms,
            latitude=lat,
            longitude=lon,
            rel_alt_m=rel_alt_m,
            abs_alt_m=abs_alt_m,
            gimbal_pitch=gimbal_pitch,
            gps_status=gps_status,
            altitude_status="reported_relative_unverified" if rel_alt_m is not None else
                            "reported_absolute_unverified" if abs_alt_m is not None else
                            "reported_h_unverified" if reported_h_m is not None else "missing",
            gimbal_pitch_status="present_unverified" if gimbal_pitch is not None else "missing",
            reported_h_m=reported_h_m,
            reported_d_m=reported_d_m,
            gps_third_value=third,
            raw_text=content.strip(),
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
