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

import math
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

    # Camera specs là cấu hình; tuyệt đối không coi target altitude/default GSD là phép đo.
    sensor_w = float(cfg.get("sensor_width_mm", 6.17))
    # TẠM — chờ thông số camera thật (tiêu cự ống kính mặc định: 4.26 mm)
    focal_len = float(cfg.get("focal_length_mm", 4.26))
    do_geo = bool(cfg.get("calculate_georeference", True))

    estimator = MetricEstimator()
    items = ctx.get("deduped_detections", [])
    frames_dict = {f.get("frame_index"): f for f in ctx.get("frames", [])}

    measured_items: List[Dict[str, Any]] = []

    for det in items:
        f_idx = det.get("frame_index", 0)
        f_info = frames_dict.get(f_idx, {})
        gps_info = f_info.get("gps") or {}

        # Chỉ số đo AGL/pitch đã xác minh độc lập mới cho phép tính GSD.
        alt = gps_info.get("agl_altitude_m") if gps_info.get("agl_status") == "verified" else None
        pitch = gps_info.get("gimbal_pitch") if gps_info.get("gimbal_pitch_status") == "verified" else None
        valid_pose = (isinstance(alt, (int, float)) and math.isfinite(alt) and alt > 0 and
                      isinstance(pitch, (int, float)) and math.isfinite(pitch) and abs(pitch + 90) <= 2)
        gsd = None
        gsd_source = None
        if valid_pose and gps_info.get("gsd_status") == "verified":
            candidate = gps_info.get("gsd_mm_per_px")
            if isinstance(candidate, (int, float)) and math.isfinite(candidate) and candidate > 0:
                gsd = candidate
                gsd_source = "verified_external"
        if gsd is None and valid_pose:
            image = f_info.get("image")
            image_w = image.shape[1] if image is not None else None
            if image_w and sensor_w > 0 and focal_len > 0:
                gsd = (alt * 1000.0 * sensor_w) / (focal_len * image_w)
                gsd_source = "calculated_from_verified_agl_pose"
        box = det.get("box", [0, 0, 0, 0])
        class_name = det.get("class_name", "pothole")

        # 2. Đo đạc kích thước 2D và xếp loại Severity
        metrics = estimator.estimate_dimensions(box, gsd, class_name) if gsd is not None else {
            "is_2d_estimate": False,
            "estimated_width_mm": None,
            "estimated_length_m": None,
            "severity": "NEEDS_REVIEW",
            "gsd_used": None,
            "min_measurable_width_mm": None,
            "is_sub_resolution": None,
            "standard_rules": None,
        }
        det.update(metrics)
        det["measurement_status"] = "estimated" if gsd is not None else "not_measurable"
        det["gsd_source"] = gsd_source
        det["telemetry_status"] = gps_info.get("gps_status", "missing")
        det["aircraft_latitude"] = gps_info.get("latitude")
        det["aircraft_longitude"] = gps_info.get("longitude")
        det["reported_h_m"] = gps_info.get("reported_h_m")
        det["reported_d_m"] = gps_info.get("reported_d_m")
        det["telemetry_provenance"] = {
            "srt_path": ctx.get("srt_path"),
            "source_timestamp_ms": gps_info.get("source_timestamp_ms"),
            "raw_srt_text": gps_info.get("raw_srt_text"),
            "gps_status": gps_info.get("gps_status", "missing"),
            "altitude_status": gps_info.get("altitude_status", "missing"),
            "gimbal_pitch_status": gps_info.get("gimbal_pitch_status", "missing"),
            "gps_third_value": gps_info.get("gps_third_value"),
        }

        # 3. Tính toán tọa độ WGS84 mặt đất
        # Phép chiếu hiện tại giả định ảnh có hướng Bắc lên trên; cần xác minh
        # thêm orientation trước khi xuất tọa độ khuyết tật mặt đất.
        if (do_geo and valid_pose and gps_info.get("image_north_up_verified") is True and
                gps_info.get("gps_status") == "verified" and
                isinstance(gps_info.get("latitude"), (int, float)) and
                isinstance(gps_info.get("longitude"), (int, float))):
            drone_lat = gps_info["latitude"]
            drone_lon = gps_info["longitude"]
            img_shape = det.get("raw_image_shape") or (
                f_info["image"].shape[:2] if f_info.get("image") is not None else None)
            if img_shape is None:
                det["ground_latitude"] = None
                det["ground_longitude"] = None
                det["location_method"] = "UNREFERENCED"
                measured_items.append(det)
                continue

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
            det["ground_latitude"] = None
            det["ground_longitude"] = None
            det["location_method"] = "UNREFERENCED"

        measured_items.append(det)

    ctx["measured_detections"] = measured_items
    ctx["stage_05_completed"] = True
    return ctx
