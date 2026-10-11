"""
src/pipeline/stages/05_measure.py — Giai đoạn 5: Đo Đạc Kích Thước Vật Lý 2D & Định Vị WGS84
=============================================================================================
Nhiệm vụ:
  - Tính toán GSD (Ground Sampling Distance: mm/pixel) theo độ cao bay thực tế từ Telemetry.
  - Ước lượng kích thước thực tế (chiều dài m, chiều rộng mm) theo BBox và GSD.
  - Phân loại mức độ nghiêm trọng (Severity: LOW, MEDIUM, HIGH, CRITICAL).
  - Chiếu tâm khuyết tật xuống tọa độ mặt đất chuẩn WGS84 (Georeferencing).

Interface:
  def run(ctx: dict) -> dict
"""

from typing import Dict, Any, List
from src.measurement.metric_estimator import MetricEstimator
from src.utils.geo import calculate_defect_ground_coords


def run(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Thực thi Stage 05: Measure.
    """
    cfg = ctx.get("config", {}).get("stages", {}).get("05_measure", {})
    if not cfg.get("enabled", True):
        ctx["measured_detections"] = ctx.get("deduped_detections", [])
        return ctx

    default_alt = float(cfg.get("default_altitude_m", 10.0))
    default_gsd = float(cfg.get("default_gsd_mm_per_px", 5.325))
    sensor_w = float(cfg.get("sensor_width_mm", 6.17))
    focal_len = float(cfg.get("focal_length_mm", 4.26))
    do_geo = bool(cfg.get("calculate_georeference", True))

    estimator = MetricEstimator()
    items = ctx.get("deduped_detections", [])
    telemetries = ctx.get("telemetries", [])
    frames_dict = {f.get("frame_index"): f for f in ctx.get("frames", [])}

    measured_items: List[Dict[str, Any]] = []

    for det in items:
        f_idx = det.get("frame_index", 0)
        f_info = frames_dict.get(f_idx, {})
        gps_info = f_info.get("gps") or {}

        # 1. Xác định GSD
        alt = gps_info.get("rel_alt_m") or gps_info.get("altitude") or default_alt
        gsd = gps_info.get("gsd_mm_per_px")
        if gsd is None or gsd <= 0:
            gsd = (alt * 1000.0 * sensor_w) / (focal_len * 2720.0) if alt > 0 else default_gsd

        box = det.get("box", [0, 0, 0, 0])
        class_name = det.get("class_name", "pothole")

        # 2. Đo đạc kích thước 2D và xếp loại Severity
        metrics = estimator.estimate_dimensions(box, gsd, class_name)
        det.update(metrics)

        # 3. Tính toán tọa độ WGS84 mặt đất
        if do_geo:
            drone_lat = gps_info.get("latitude", 0.0)
            drone_lon = gps_info.get("longitude", 0.0)
            img_shape = det.get("raw_image_shape", (1530, 2720))

            cx = (box[0] + box[2]) / 2.0
            cy = (box[1] + box[3]) / 2.0

            glat, glon, loc_method = calculate_defect_ground_coords(
                drone_lat=drone_lat,
                drone_lon=drone_lon,
                altitude_m=alt,
                pixel_x=cx,
                pixel_y=cy,
                image_w=img_shape[1],
                image_h=img_shape[0],
                focal_mm=focal_len,
                sensor_w_mm=sensor_w
            )
            det["ground_latitude"] = glat
            det["ground_longitude"] = glon
            det["location_method"] = loc_method
        else:
            det["ground_latitude"] = 0.0
            det["ground_longitude"] = 0.0
            det["location_method"] = "UNREFERENCED"

        measured_items.append(det)

    ctx["measured_detections"] = measured_items
    ctx["stage_05_completed"] = True
    return ctx
