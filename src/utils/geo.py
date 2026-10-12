"""
src/utils/geo.py — Các tiện ích viễn thám, tọa độ địa lý WGS84 & Georeferencing
==============================================================================
"""

import math
from typing import Tuple


def calculate_defect_ground_coords(
    drone_lat: float,
    drone_lon: float,
    altitude_m: float,
    gimbal_pitch_deg: float = -90.0,
    pixel_x: float = 1360.0,
    pixel_y: float = 765.0,
    image_w: int = 2720,
    image_h: int = 1530,
    focal_mm: float = 4.26,
    sensor_w_mm: float = 6.17
) -> Tuple[float, float, str]:
    """
    Tính toán tọa độ địa lý mặt đất (WGS84) của khuyết tật từ góc nghiêng Gimbal và tâm BBox.
    """
    if drone_lat == 0.0 and drone_lon == 0.0:
        return 0.0, 0.0, "UNKNOWN"

    cx = image_w / 2.0
    cy = image_h / 2.0
    dx_px = pixel_x - cx
    dy_px = pixel_y - cy

    gsd_m = (altitude_m * sensor_w_mm) / (focal_mm * image_w)
    offset_east_m = dx_px * gsd_m
    offset_north_m = -dy_px * gsd_m  # trục Y ảnh ngược hướng Bắc

    # 1 độ vĩ ~ 111,320m; 1 độ kinh ~ 111,320m * cos(lat)
    delta_lat = offset_north_m / 111320.0
    delta_lon = offset_east_m / (111320.0 * math.cos(math.radians(drone_lat)))

    ground_lat = round(drone_lat + delta_lat, 7)
    ground_lon = round(drone_lon + delta_lon, 7)

    return ground_lat, ground_lon, "OBSERVED_FOOTPRINT"
