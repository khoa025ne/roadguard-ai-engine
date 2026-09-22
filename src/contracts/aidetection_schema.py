"""
src/contracts/aidetection_schema.py — Định dạng JSON Payload bất biến AIDetection
==============================================================================
Tuân thủ 100% trường dữ liệu theo RoadGuard_Data_Dictionary_v1.md.
"""

import uuid
from typing import Dict, Any, List, Optional


class AIDetectionPayloadFormatter:
    """Format kết quả AI thành JSON Payload chuẩn hóa cho Backend ASP.NET Core."""

    @staticmethod
    def create_detection_record(
        processing_job_id: str,
        model_version_id: str,
        defect_type_code: str,
        confidence: float,
        estimated_width_mm: float,
        estimated_length_m: float,
        aircraft_lat: Optional[float] = None,
        aircraft_lon: Optional[float] = None,
        defect_lat: Optional[float] = None,
        defect_lon: Optional[float] = None,
        location_method: str = "OBSERVED_FOOTPRINT",
        camera_pose: Optional[Dict[str, Any]] = None,
        raw_box: Optional[List[int]] = None,
        crop_uri: Optional[str] = None
    ) -> Dict[str, Any]:
        """Tạo 1 bản ghi AIDetection chuẩn hóa."""
        det_id = str(uuid.uuid4())

        aircraft_geom = f"POINT({aircraft_lon} {aircraft_lat})" if aircraft_lat and aircraft_lon else None
        defect_geom = f"POINT({defect_lon} {defect_lat})" if defect_lat and defect_lon else None

        return {
            "id": det_id,
            "processing_job_id": processing_job_id,
            "model_version_id": model_version_id,
            "defect_type_code": defect_type_code,
            "confidence": round(float(confidence), 4),
            "is_2d_estimate": True,
            "estimated_width": estimated_width_mm,
            "estimated_length": estimated_length_m,
            "defect_location_method": location_method,
            "geometry": defect_geom,
            "aircraft_location": aircraft_geom,
            "location_uncertainty_m": 1.5 if defect_geom else None,
            "camera_pose_json": camera_pose or {},
            "raw_payload": {
                "detection_id": det_id,
                "box_xyxy": raw_box or [],
                "crop_artifact_uri": crop_uri or ""
            }
        }

    @staticmethod
    def format_job_response(
        processing_job_id: str,
        model_version_id: str,
        detections: List[Dict[str, Any]],
        execution_time_seconds: float,
        status: str = "COMPLETED"
    ) -> Dict[str, Any]:
        """Tạo payload phản hồi đầy đủ cho Backend."""
        return {
            "processing_job_id": processing_job_id,
            "model_version_id": model_version_id,
            "status": status,
            "total_detections": len(detections),
            "execution_time_seconds": round(execution_time_seconds, 2),
            "detections": detections
        }

    @staticmethod
    def format_geojson(detections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Xuất dữ liệu theo chuẩn GeoJSON FeatureCollection cho Leaflet.js / GIS."""
        features = []
        for det in detections:
            geom_wkt = det.get("geometry")
            if not geom_wkt or "POINT" not in geom_wkt:
                continue

            # Parse "POINT(lon lat)"
            try:
                coords_str = geom_wkt.replace("POINT(", "").replace(")", "").strip()
                lon_str, lat_str = coords_str.split()
                lon, lat = float(lon_str), float(lat_str)
            except Exception:
                continue

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat]
                },
                "properties": {
                    "detection_id": det.get("id"),
                    "defect_type_code": det.get("defect_type_code"),
                    "confidence": det.get("confidence"),
                    "estimated_width_mm": det.get("estimated_width"),
                    "estimated_length_m": det.get("estimated_length"),
                    "severity": det.get("severity", "MEDIUM"),
                    "location_method": det.get("defect_location_method"),
                    "camera_pose": det.get("camera_pose_json"),
                    "crop_artifact_uri": det.get("raw_payload", {}).get("crop_artifact_uri")
                }
            }
            features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features
        }

