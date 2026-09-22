"""
src/contracts/mock_ai_adapter.py — Giả lập kết quả AI phục vụ nghiệm thu sớm Backend
===================================================================================
Tạo dữ liệu AIDetection mẫu có tọa độ hợp lệ để đội Backend ASP.NET Core kiểm thử hợp đồng.
"""

import uuid
import time
from typing import Dict, Any, List
from .aidetection_schema import AIDetectionPayloadFormatter


class MockAIAdapter:
    """Mock Adapter giả lập AI Service cho giai đoạn Phase 1 / Kiểm thử."""

    def __init__(self, model_version_id: str = "mock-yolo11n-v1.0"):
        self.model_version_id = model_version_id

    def process_mock_job(
        self,
        processing_job_id: str,
        start_lat: float = 10.762622,
        start_lon: float = 106.660172,
        num_mock_defects: int = 3
    ) -> Dict[str, Any]:
        """Tạo kết quả giả lập trả về cho Backend trong < 100ms."""
        start_time = time.time()
        detections = []

        mock_types = ["pothole", "longitudinal_crack", "alligator_crack"]

        for i in range(num_mock_defects):
            d_lat = start_lat + (i * 0.00015)
            d_lon = start_lon + (i * 0.00010)
            det_type = mock_types[i % len(mock_types)]

            rec = AIDetectionPayloadFormatter.create_detection_record(
                processing_job_id=processing_job_id,
                model_version_id=self.model_version_id,
                defect_type_code=det_type,
                confidence=0.88 - (i * 0.05),
                estimated_width_mm=320.0 + (i * 40.0),
                estimated_length_m=0.45 + (i * 0.20),
                aircraft_lat=d_lat - 0.00001,
                aircraft_lon=d_lon - 0.00001,
                defect_lat=d_lat,
                defect_lon=d_lon,
                location_method="OBSERVED_FOOTPRINT",
                camera_pose={
                    "altitude_m": 8.5,
                    "gimbal_pitch": -90.0,
                    "gsd_mm_per_px": 1.21,
                    "frame_index": 15 * (i + 1),
                    "timestamp_ms": 500 * (i + 1)
                },
                raw_box=[200 + i * 50, 300 + i * 50, 280 + i * 50, 390 + i * 50],
                crop_uri=f"mock://crops/mock_{i}.jpg"
            )
            detections.append(rec)

        duration = time.time() - start_time
        response = AIDetectionPayloadFormatter.format_job_response(
            processing_job_id=processing_job_id,
            model_version_id=self.model_version_id,
            detections=detections,
            execution_time_seconds=duration,
            status="COMPLETED"
        )
        response["is_mock"] = True
        return response
