"""
DJI Mini 2 SE — SRT Telemetry Parser & GPS Extractor
=====================================================
Đọc file .SRT từ DJI Mini 2 SE, extract:
  - Tọa độ GPS (latitude, longitude)
  - Độ cao bay (rel_alt) → dùng tính GSD realtime
  - Timestamp mỗi frame
  - Tính GSD (mm/pixel) cho từng frame

Dùng lệnh:
  python srt_gps_parser.py --srt DJI_0001.SRT --fps 30 --output gps_data.json

Hoặc import module:
  from srt_gps_parser import DJISRTParser
"""

import re
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional

# ─── Thông số DJI Mini 2 SE (fixed) ──────────────────────────────────────────
DJI_MINI_2_SE = {
    "sensor_width_mm": 6.17,       # 1/2.3" CMOS physical width
    "sensor_height_mm": 4.55,      # 1/2.3" CMOS physical height
    "focal_length_actual_mm": 4.26, # 24mm equiv / crop factor 5.64
    "image_width_px": 2720,        # 2.7K video width
    "image_height_px": 1530,       # 2.7K video height
}

# ─── Dataclass cho mỗi frame ──────────────────────────────────────────────────
@dataclass
class FrameTelemetry:
    frame_index: int           # Frame số bao nhiêu (0-indexed)
    srt_block: int             # Block SRT tương ứng
    timestamp_ms: float        # Thời gian (ms) từ đầu video
    timestamp_str: str         # "00:00:01,033"
    latitude: float            # WGS84 latitude
    longitude: float           # WGS84 longitude
    rel_alt_m: float           # Độ cao tương đối (m)
    abs_alt_m: float           # Độ cao tuyệt đối (m)
    gsd_mm_per_px: float       # Ground Sampling Distance (mm/pixel)
    iso: Optional[int] = None
    shutter: Optional[str] = None
    focal_len_mm: Optional[float] = None


# ─── Core Parser ──────────────────────────────────────────────────────────────
class DJISRTParser:
    """
    Parser cho file .SRT của DJI Mini 2 SE.
    
    SRT format mỗi block:
    ┌─────────────────────────────────────────────────────────┐
    │ 1                                                        │
    │ 00:00:00,000 --> 00:00:00,033                           │
    │ <font size="28">SrtCnt : 1, DiffTime : 33ms            │
    │ 2024-01-15 08:30:00.000                                  │
    │ [iso : 100] [shutter : 1/1000.0] [fnum : 280] ...      │
    │ [latitude: 10.762622] [longitude: 106.660172]           │
    │ [rel_alt: 30.000 abs_alt: 130.000]                      │
    │ </font>                                                  │
    └─────────────────────────────────────────────────────────┘
    """

    # Regex patterns để extract từng trường
    _RE_TIMECODE  = re.compile(r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})')
    _RE_LAT       = re.compile(r'\[latitude:\s*([-\d.]+)\]')
    _RE_LON       = re.compile(r'\[longitude:\s*([-\d.]+)\]')
    _RE_REL_ALT   = re.compile(r'\[rel_alt:\s*([-\d.]+)')
    _RE_ABS_ALT   = re.compile(r'abs_alt:\s*([-\d.]+)\]')
    _RE_ISO       = re.compile(r'\[iso\s*:\s*(\d+)\]')
    _RE_SHUTTER   = re.compile(r'\[shutter\s*:\s*([\d/\.]+)\]')
    _RE_FOCAL     = re.compile(r'\[focal_len\s*:\s*(\d+)\]')  # DJI stores ×10

    def __init__(self, drone_specs: dict = None):
        self.specs = drone_specs or DJI_MINI_2_SE

    def parse_srt_file(self, srt_path: str | Path) -> List[FrameTelemetry]:
        """Parse toàn bộ file SRT, trả về list FrameTelemetry."""
        srt_path = Path(srt_path)
        if not srt_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file SRT: {srt_path}")

        content = srt_path.read_text(encoding='utf-8', errors='ignore')
        blocks = self._split_blocks(content)

        results = []
        for i, block in enumerate(blocks):
            try:
                telemetry = self._parse_block(i, block)
                if telemetry:
                    results.append(telemetry)
            except Exception as e:
                print(f"  ⚠️  Block {i}: lỗi parse — {e}")

        print(f"✅ Đã parse {len(results)}/{len(blocks)} blocks từ {srt_path.name}")
        return results

    def _split_blocks(self, content: str) -> List[str]:
        """Tách SRT thành các blocks riêng biệt."""
        # Blocks phân cách bởi dòng trắng hoặc số thứ tự
        blocks = re.split(r'\n\s*\n', content.strip())
        return [b.strip() for b in blocks if b.strip()]

    def _parse_block(self, idx: int, block: str) -> Optional[FrameTelemetry]:
        """Parse 1 block SRT thành FrameTelemetry."""

        # Timecode
        tc_match = self._RE_TIMECODE.search(block)
        if not tc_match:
            return None
        ts_str = tc_match.group(1)
        ts_ms = self._timecode_to_ms(ts_str)

        # GPS coordinates
        lat_match = self._RE_LAT.search(block)
        lon_match = self._RE_LON.search(block)
        if not lat_match or not lon_match:
            return None  # Skip block không có GPS
        lat = float(lat_match.group(1))
        lon = float(lon_match.group(1))

        # Altitude
        rel_alt = float(self._RE_REL_ALT.search(block).group(1)) if self._RE_REL_ALT.search(block) else 0.0
        abs_alt = float(self._RE_ABS_ALT.search(block).group(1)) if self._RE_ABS_ALT.search(block) else 0.0

        # Optional fields
        iso_m = self._RE_ISO.search(block)
        sht_m = self._RE_SHUTTER.search(block)
        foc_m = self._RE_FOCAL.search(block)

        iso = int(iso_m.group(1)) if iso_m else None
        shutter = sht_m.group(1) if sht_m else None
        focal_len_mm = float(foc_m.group(1)) / 10.0 if foc_m else None  # DJI ×10

        # Tính GSD realtime từ rel_alt
        gsd = self._calc_gsd(rel_alt)

        return FrameTelemetry(
            frame_index=idx,
            srt_block=idx + 1,
            timestamp_ms=ts_ms,
            timestamp_str=ts_str,
            latitude=lat,
            longitude=lon,
            rel_alt_m=rel_alt,
            abs_alt_m=abs_alt,
            gsd_mm_per_px=round(gsd, 4),
            iso=iso,
            shutter=shutter,
            focal_len_mm=focal_len_mm,
        )

    def _timecode_to_ms(self, tc: str) -> float:
        """Chuyển '00:01:23,456' → milliseconds."""
        hh, mm, rest = tc.split(':')
        ss, ms = rest.split(',')
        return (int(hh) * 3600 + int(mm) * 60 + int(ss)) * 1000 + int(ms)

    def _calc_gsd(self, altitude_m: float) -> float:
        """
        Tính GSD (mm/pixel) dựa trên độ cao bay.
        
        Công thức:
            GSD = (H × Sw) / (f × W)
        
        Trong đó:
            H  = altitude_m × 1000 (mm)
            Sw = sensor_width_mm
            f  = focal_length_actual_mm
            W  = image_width_px
        """
        if altitude_m <= 0:
            return 0.0

        H_mm = altitude_m * 1000  # meters → mm
        Sw   = self.specs["sensor_width_mm"]
        f    = self.specs["focal_length_actual_mm"]
        W    = self.specs["image_width_px"]

        gsd_mm_per_px = (H_mm * Sw) / (f * W)
        return gsd_mm_per_px

    def export_json(self, telemetries: List[FrameTelemetry], output_path: str | Path):
        """Export sang JSON file."""
        data = {
            "drone": "DJI Mini 2 SE",
            "total_frames": len(telemetries),
            "specs": self.specs,
            "gsd_summary": self._gsd_summary(telemetries),
            "frames": [asdict(t) for t in telemetries],
        }
        Path(output_path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"💾 Đã xuất JSON: {output_path}")

    def export_geojson(self, telemetries: List[FrameTelemetry], output_path: str | Path):
        """Export sang GeoJSON (dùng với Leaflet.js / QGIS)."""
        features = []
        for t in telemetries:
            if t.latitude and t.longitude:
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [t.longitude, t.latitude]  # GeoJSON: [lon, lat]
                    },
                    "properties": {
                        "frame": t.frame_index,
                        "timestamp_ms": t.timestamp_ms,
                        "rel_alt_m": t.rel_alt_m,
                        "gsd_mm_per_px": t.gsd_mm_per_px,
                    }
                })

        geojson = {
            "type": "FeatureCollection",
            "name": "DJI_Mini_2_SE_Flight_Path",
            "features": features
        }
        Path(output_path).write_text(json.dumps(geojson, indent=2), encoding='utf-8')
        print(f"🗺️  Đã xuất GeoJSON: {output_path}")

    def _gsd_summary(self, telemetries: List[FrameTelemetry]) -> dict:
        """Tính thống kê GSD và độ cao trong toàn chuyến bay."""
        altitudes = [t.rel_alt_m for t in telemetries if t.rel_alt_m > 0]
        gsds = [t.gsd_mm_per_px for t in telemetries if t.gsd_mm_per_px > 0]
        if not altitudes:
            return {}
        return {
            "avg_altitude_m": round(sum(altitudes) / len(altitudes), 2),
            "min_altitude_m": round(min(altitudes), 2),
            "max_altitude_m": round(max(altitudes), 2),
            "avg_gsd_mm_per_px": round(sum(gsds) / len(gsds), 4),
            "min_crack_detectable_mm": round(min(gsds) * 3, 2),  # 3px minimum
            "recommendation": (
                "✅ Tốt cho crack detection"
                if min(altitudes) <= 15
                else "⚠️ Bay quá cao, chỉ thấy ổ gà lớn"
            )
        }

    def get_frame_gps(self, telemetries: List[FrameTelemetry],
                       frame_idx: int, video_fps: float = 30.0) -> Optional[FrameTelemetry]:
        """
        Lấy GPS data cho một frame cụ thể từ video.
        
        Args:
            telemetries: List đã parse từ SRT
            frame_idx: Frame index trong video (0-indexed)
            video_fps: FPS của video (DJI Mini 2 SE = 30fps)
        
        Returns:
            FrameTelemetry gần nhất với thời điểm frame đó
        """
        target_ms = (frame_idx / video_fps) * 1000
        closest = min(telemetries, key=lambda t: abs(t.timestamp_ms - target_ms))
        return closest


# ─── CLI Entry Point ──────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="DJI Mini 2 SE SRT Parser — Extract GPS & GSD data"
    )
    parser.add_argument('--srt',    required=True,  help='Đường dẫn tới file .SRT')
    parser.add_argument('--fps',    default=30.0,   type=float, help='FPS video (mặc định: 30)')
    parser.add_argument('--output', default='gps_data.json', help='File JSON output')
    parser.add_argument('--geojson', default=None, help='(optional) File GeoJSON output')
    parser.add_argument('--summary', action='store_true', help='In tóm tắt ra màn hình')
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"🛰️  DJI Mini 2 SE SRT Parser")
    print(f"{'='*60}")
    print(f"📄 File SRT  : {args.srt}")
    print(f"🎬 Video FPS : {args.fps}")
    print(f"{'='*60}\n")

    srt_parser = DJISRTParser()
    telemetries = srt_parser.parse_srt_file(args.srt)

    # Export JSON
    srt_parser.export_json(telemetries, args.output)

    # Export GeoJSON nếu yêu cầu
    if args.geojson:
        srt_parser.export_geojson(telemetries, args.geojson)

    # In summary
    if args.summary and telemetries:
        summary = srt_parser._gsd_summary(telemetries)
        print(f"\n Tóm Tắt Chuyến Bay:")
        print(f"   Tổng frames GPS    : {len(telemetries)}")
        print(f"   Độ cao TB          : {summary.get('avg_altitude_m')} m")
        print(f"   Độ cao min/max     : {summary.get('min_altitude_m')}m / {summary.get('max_altitude_m')}m")
        print(f"   GSD trung bình     : {summary.get('avg_gsd_mm_per_px')} mm/pixel")
        print(f"   Vết nứt nhỏ nhất   : {summary.get('min_crack_detectable_mm')} mm (3px threshold)")
        print(f"   Đánh giá           : {summary.get('recommendation')}")

    print(f"\n✅ Hoàn tất!\n")


if __name__ == '__main__':
    main()
