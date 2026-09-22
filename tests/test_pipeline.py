"""
tests/test_pipeline.py — Kiểm thử tự động tính toàn vẹn của các module RoadGuard AI
"""

import sys
import unittest
import numpy as np
from pathlib import Path

# Thêm root vào sys.path
sys.path.append(str(Path(__file__).parent.parent))

from src.ingestion.srt_parser import DJISRTParser
from src.ingestion.video_extractor import VideoFrameExtractor
from src.ingestion.raw_video_analyzer import RawVideoAnalyzer
from src.inference.tiling_engine import TileSplitter
from src.measurement.metric_estimator import MetricEstimator
from src.measurement.spatial_tracker import SpatialTracker
from src.contracts.aidetection_schema import AIDetectionPayloadFormatter
from src.contracts.mock_ai_adapter import MockAIAdapter


class TestRoadGuardAIPipeline(unittest.TestCase):

    def test_gsd_calculation(self):
        """
        Kiểm tra công thức quang học tính GSD từ độ cao bay:
        GSD = (Altitude * 1000 * SensorWidth) / (FocalLength * ImageWidth)
        Tại 10m: (10 * 1000 * 6.17) / (4.26 * 2720) = 5.325 mm/pixel.
        """
        parser = DJISRTParser()
        gsd = parser.calc_gsd(10.0)
        self.assertAlmostEqual(gsd, 5.325, delta=0.05)

    def test_tile_splitter(self):
        """Kiểm tra thuật toán cắt tile 640x640 và padding."""
        tiler = TileSplitter(tile_size=640, overlap=0.2)
        dummy_img = np.zeros((1530, 2720, 3), dtype=np.uint8)
        tiles = tiler.split_frame(dummy_img)

        self.assertGreater(len(tiles), 10)
        for tile_img, coords in tiles:
            self.assertEqual(tile_img.shape[0], 640)
            self.assertEqual(tile_img.shape[1], 640)

    def test_metric_estimator(self):
        """Kiểm tra quy đổi pixel sang mm và phân cấp severity."""
        estimator = MetricEstimator()
        box = [100, 100, 400, 500]
        gsd = 1.5  # mm/px
        res = estimator.estimate_dimensions(box, gsd, "pothole")

        self.assertTrue(res["is_2d_estimate"])
        self.assertAlmostEqual(res["estimated_width_mm"], 300 * 1.5, delta=1.0)
        self.assertEqual(res["severity"], "CRITICAL")

    def test_mock_ai_adapter(self):
        """Kiểm tra Mock AI Adapter trả về đúng schema AIDetection."""
        adapter = MockAIAdapter()
        res = adapter.process_mock_job(processing_job_id="test-job-999")
        self.assertEqual(res["status"], "COMPLETED")
        self.assertGreater(len(res["detections"]), 0)
        self.assertIn("defect_type_code", res["detections"][0])
        self.assertIn("geometry", res["detections"][0])
        self.assertIn("aircraft_location", res["detections"][0])

    def test_geojson_export(self):
        """Kiểm tra tạo GeoJSON FeatureCollection."""
        sample_dets = [{
            "id": "det-1",
            "defect_type_code": "pothole",
            "confidence": 0.9,
            "estimated_width": 350.0,
            "estimated_length": 0.45,
            "severity": "CRITICAL",
            "defect_location_method": "OBSERVED_FOOTPRINT",
            "geometry": "POINT(106.660172 10.762622)"
        }]
        geojson = AIDetectionPayloadFormatter.format_geojson(sample_dets)
        self.assertEqual(geojson["type"], "FeatureCollection")
        self.assertEqual(len(geojson["features"]), 1)
        feat = geojson["features"][0]
        self.assertEqual(feat["geometry"]["type"], "Point")
        self.assertAlmostEqual(feat["geometry"]["coordinates"][0], 106.660172)
        self.assertAlmostEqual(feat["geometry"]["coordinates"][1], 10.762622)

    def test_defect_ground_coords_georeferencing(self):
        """Kiểm tra phép chiếu tâm BBox xuống tọa độ mặt đất WGS84."""
        lat, lon, method = RawVideoAnalyzer.calculate_defect_ground_coords(
            drone_lat=10.762622,
            drone_lon=106.660172,
            altitude_m=10.0,
            gimbal_pitch_deg=-90.0,
            pixel_x=1360.0,  # Đúng tâm ảnh (2720 / 2)
            pixel_y=765.0,   # Đúng tâm ảnh (1530 / 2)
            image_w=2720,
            image_h=1530
        )
        self.assertEqual(method, "OBSERVED_FOOTPRINT")
        # Đúng tâm ảnh thì ground lat/lon trùng với drone lat/lon
        self.assertAlmostEqual(lat, 10.762622, places=6)
        self.assertAlmostEqual(lon, 106.660172, places=6)


if __name__ == "__main__":
    unittest.main()
