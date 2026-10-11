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
from src.utils.geo import calculate_defect_ground_coords
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
        """Kiểm tra quy đổi pixel sang mm và phân cấp severity theo quy chuẩn FHWA."""
        estimator = MetricEstimator()
        box = [100, 100, 400, 500]
        gsd = 1.5  # mm/px
        res = estimator.estimate_dimensions(box, gsd, "pothole")

        self.assertTrue(res["is_2d_estimate"])
        self.assertAlmostEqual(res["estimated_width_mm"], 300 * 1.5, delta=1.0)
        self.assertEqual(res["severity"], "CRITICAL")
        self.assertEqual(res["min_measurable_width_mm"], 3.0)

        # Kiểm tra nứt dọc FHWA: <3mm LOW, 3-13mm MEDIUM, >=13mm HIGH
        box_crack_low = [0, 0, 2, 100]  # width = 2 * 1.0 = 2.0 mm (<3mm)
        res_long_low = estimator.estimate_dimensions(box_crack_low, 1.0, "crack_longitudinal")
        self.assertEqual(res_long_low["severity"], "LOW")

        box_crack_med = [0, 0, 5, 100]  # width = 5 * 1.0 = 5.0 mm (3-13mm)
        res_long_med = estimator.estimate_dimensions(box_crack_med, 1.0, "crack_longitudinal")
        self.assertEqual(res_long_med["severity"], "MEDIUM")

        box_crack_high = [0, 0, 15, 100]  # width = 15 * 1.0 = 15.0 mm (>=13mm)
        res_long_high = estimator.estimate_dimensions(box_crack_high, 1.0, "crack_longitudinal")
        self.assertEqual(res_long_high["severity"], "HIGH")

        # Kiểm tra nứt ngang FHWA: <3mm LOW, 3-6mm MEDIUM, >=6mm HIGH
        box_trans_med = [0, 0, 100, 4]  # width = 4 * 1.0 = 4.0 mm (3-6mm)
        res_trans_med = estimator.estimate_dimensions(box_trans_med, 1.0, "crack_transverse")
        self.assertEqual(res_trans_med["severity"], "MEDIUM")

        box_trans_high = [0, 0, 100, 8]  # width = 8 * 1.0 = 8.0 mm (>=6mm)
        res_trans_high = estimator.estimate_dimensions(box_trans_high, 1.0, "crack_transverse")
        self.assertEqual(res_trans_high["severity"], "HIGH")

        # Quy tắc GSD: chi tiết nhỏ nhất đo được ≈ 2 x GSD
        # Khi GSD = 2.5 mm/px, min_measurable = 5.0 mm. Với box 3mm -> is_sub_resolution = True
        res_gsd_limit = estimator.estimate_dimensions([0, 0, 1, 50], 2.5, "crack_longitudinal")
        self.assertTrue(res_gsd_limit["is_sub_resolution"])


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
        lat, lon, method = calculate_defect_ground_coords(
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

    def test_target_band_classifier(self):
        """Kiểm tra phân loại TargetBand theo chiều bay xuôi và bay ngược."""
        from src.inference.tiling_engine import TargetBandClassifier

        # 1. Bay xuôi chiều lý trình
        box_left = [50, 100, 150, 200]    # x_center = 100 / 2720 = 0.036 (< 0.15)
        box_center = [1200, 100, 1400, 200] # x_center = 1300 / 2720 = 0.477
        box_right = [2500, 100, 2650, 200] # x_center = 2575 / 2720 = 0.946 (> 0.85)

        self.assertEqual(TargetBandClassifier.classify(box_left, is_forward=True), "LEFT_EDGE")
        self.assertEqual(TargetBandClassifier.classify(box_center, is_forward=True), "SURFACE")
        self.assertEqual(TargetBandClassifier.classify(box_right, is_forward=True), "RIGHT_EDGE")

        # 2. Bay ngược chiều lý trình: Quy ước không đổi -> Mép trái camera thành RIGHT_EDGE, mép phải thành LEFT_EDGE
        self.assertEqual(TargetBandClassifier.classify(box_left, is_forward=False), "RIGHT_EDGE")
        self.assertEqual(TargetBandClassifier.classify(box_center, is_forward=False), "SURFACE")
        self.assertEqual(TargetBandClassifier.classify(box_right, is_forward=False), "LEFT_EDGE")

        # 3. Kiểm tra tính chiều bay theo góc azimuth
        # Tuyến đường hướng Đông (90 độ), Drone bay hướng Đông (85 độ) -> Chênh 5 độ <= 90 -> Xuôi
        self.assertTrue(TargetBandClassifier.is_forward_flight(flight_heading_deg=85.0, road_azimuth_deg=90.0))
        # Drone bay ngược lại hướng Tây (270 độ) -> Chênh 180 độ > 90 -> Ngược
        self.assertFalse(TargetBandClassifier.is_forward_flight(flight_heading_deg=270.0, road_azimuth_deg=90.0))

    def test_context_overlap_handler(self):
        """Kiểm tra phát hiện vùng đệm biên giữa các ProcessingBlock."""
        from src.inference.tiling_engine import ContextOverlapHandler

        # Phạm vi chính của Block: [0.0m - 500.0m]
        # Khuyết tật ở lý trình 250m -> Nằm trong phạm vi chính -> Không phải overlap
        self.assertFalse(ContextOverlapHandler.is_overlap_detection(250.0, 0.0, 500.0))

        # Khuyết tật ở lý trình 520m -> Vượt ngoài phạm vi chính -> Là context overlap
        self.assertTrue(ContextOverlapHandler.is_overlap_detection(520.0, 0.0, 500.0))
        # Khuyết tật ở lý trình -15m -> Trước điểm đầu -> Là context overlap
        self.assertTrue(ContextOverlapHandler.is_overlap_detection(-15.0, 0.0, 500.0))

    def test_idempotency_and_error_classification(self):
        """Kiểm tra cơ chế Idempotency SHA256 và phân loại lỗi chuẩn hợp đồng."""
        from src.contracts.idempotency import IdempotencyManager, ErrorClassifier

        mgr = IdempotencyManager()
        key1 = mgr.generate_key("block-1", "v1.0", "chk-abc")
        key2 = mgr.generate_key("block-1", "v1.0", "chk-abc")
        key3 = mgr.generate_key("block-2", "v1.0", "chk-abc")

        self.assertEqual(key1, key2)
        self.assertNotEqual(key1, key3)

        # Lưu và lấy cache
        mgr.save_result(key1, {"status": "COMPLETED", "detections": []})
        cached = mgr.get_cached_result(key1)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["result"]["status"], "COMPLETED")

        # Phân loại lỗi
        err_infra = ErrorClassifier.format_error_response("job-1", "GPU_OUT_OF_MEMORY")
        self.assertEqual(err_infra["error_type"], "INFRASTRUCTURE_ERROR")
        self.assertTrue(err_infra["retryable"])

        err_data = ErrorClassifier.format_error_response("job-2", "LOW_QUALITY_BLUR")
        self.assertEqual(err_data["error_type"], "DATA_ERROR")
        self.assertFalse(err_data["retryable"])

    def test_api_worker_endpoints(self):
        """Kiểm tra các endpoints của FastAPI Worker Service."""
        from fastapi.testclient import TestClient
        from src.api.worker_service import app

        client = TestClient(app)

        # Test health check
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "healthy")

        # Test submit mock job
        manifest_payload = {
            "manifest_id": "test-manifest-001",
            "processing_job_id": "test-job-unit-001",
            "processing_block_id": "test-block-001",
            "target_band": "SURFACE",
            "road_width_m": 3.5,
            "is_mock": True
        }
        submit_resp = client.post("/api/v1/jobs/submit", json=manifest_payload)
        self.assertEqual(submit_resp.status_code, 202)
        self.assertEqual(submit_resp.json()["processing_job_id"], "test-job-unit-001")
        self.assertIn("idempotency_key", submit_resp.json())

        # Test query job status
        status_resp = client.get("/api/v1/jobs/test-job-unit-001/status")
        self.assertEqual(status_resp.status_code, 200)
        self.assertIn(status_resp.json()["status"], ["QUEUED", "RUNNING", "COMPLETED"])

    def test_predictor_multiclass_graceful_fallback(self):
        """
        Kiểm tra predictor nạp checkpoint 2-class cũ + class_map 3-class:
        - get_class_name(2) phải trả về 'bong_troc' (không crash)
        - get_class_name_vn(2) trả về 'Bong tróc'
        - get_class_name(99) fallback gracefully 'class_99'
        """
        from src.inference.predictor import RoadDefectPredictor
        model_p = Path(__file__).parent.parent / "weights" / "trained" / "roadguard_best_15k.pt"
        if model_p.exists():
            predictor = RoadDefectPredictor(model_path=model_p)
            # Check model only has 2 classes internally
            self.assertEqual(len(predictor.model.names), 2)
            # Check class_map has 3 classes
            self.assertEqual(predictor.get_class_name(0), "pothole")
            self.assertEqual(predictor.get_class_name(1), "crack")
            self.assertEqual(predictor.get_class_name(2), "bong_troc")
            self.assertEqual(predictor.get_class_name_vn(2), "Bong tróc")
            # Graceful fallback for non-existent class
            self.assertEqual(predictor.get_class_name(99), "class_99")
            self.assertEqual(predictor.get_class_name_vn(99), "class_99")

    def test_stage_01_road_segmentation(self):
        """
        Kiểm tra Stage 01 Road Segmentation:
        - Sinh road_mask nhị phân (H, W)
        - road_area_ratio nằm trong khoảng [0.0, 1.0]
        - stage_01_completed = True
        """
        import importlib
        mod_seg = importlib.import_module("src.pipeline.stages.01_segment")
        dummy_frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        ctx = {
            "config": {
                "stages": {
                    "01_segment": {
                        "enabled": True,
                        "method": "yolo_seg",
                        "model_path": "weights/pretrained/yolo11m-road-seg.pt",
                        "min_road_area_ratio": 0.10
                    }
                }
            },
            "frames": [{"frame_id": 0, "image": dummy_frame}]
        }
        res = mod_seg.run(ctx)
        self.assertTrue(res.get("stage_01_completed"))
        mask = res["frames"][0].get("road_mask")
        self.assertIsNotNone(mask)
        self.assertEqual(mask.shape, (480, 640))
        area_ratio = res["frames"][0].get("road_area_ratio")
        self.assertGreaterEqual(area_ratio, 0.0)
        self.assertLessEqual(area_ratio, 1.0)


if __name__ == "__main__":
    unittest.main()

