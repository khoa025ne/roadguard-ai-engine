"""Regression checks for DJI subtitle telemetry and measurement provenance."""

import importlib
import json
import tempfile
import unittest
from pathlib import Path

from src.ingestion.srt_parser import DJISRTParser
from src.pipeline.pipeline import run_video_analysis_task


SRT_LINE = (
    "F/2.8, SS 918.89, ISO 100, EV 0, DZOOM 1.000, "
    "GPS (106.8276, 10.8402, 9), D 4.11m, H 1.10m, "
    "H.S 0.00m/s, V.S -0.00m/s"
)


class TestDJITelemetrySafety(unittest.TestCase):
    def test_real_dji_order_and_unverified_fields(self):
        row = DJISRTParser().parse_srt_block(SRT_LINE, 0)
        self.assertEqual((row.latitude, row.longitude), (10.8402, 106.8276))
        self.assertEqual(row.gps_status, "present_unverified")
        self.assertEqual(row.reported_h_m, 1.1)
        self.assertEqual(row.reported_d_m, 4.11)
        self.assertEqual(row.gps_third_value, 9.0)
        self.assertIsNone(row.rel_alt_m)
        self.assertIsNone(row.abs_alt_m)
        self.assertIsNone(row.gimbal_pitch)
        self.assertIsNone(row.gsd_mm_per_px)
        self.assertEqual(row.raw_text, SRT_LINE)

    def test_missing_and_invalid_gps_are_not_invented(self):
        parser = DJISRTParser()
        missing = parser.parse_srt_block("H 2.0m, D 5.0m", 1000)
        self.assertIsNone(missing.latitude)
        self.assertEqual(missing.gps_status, "missing")
        invalid = parser.parse_srt_block("GPS (190.0, 10.0, 9)", 2000)
        self.assertIsNone(invalid.longitude)
        self.assertEqual(invalid.gps_status, "invalid")

    def test_explicit_lat_lon_and_pitch_do_not_create_agl(self):
        row = DJISRTParser().parse_srt_block(
            "[latitude: 10.8402] [longitude: 106.8276] "
            "[gimbal_pitch: -89.5] [rel_alt: 10m]", 0
        )
        self.assertEqual((row.latitude, row.longitude), (10.8402, 106.8276))
        self.assertEqual(row.gimbal_pitch, -89.5)
        self.assertEqual(row.rel_alt_m, 10.0)
        self.assertIsNone(row.gsd_mm_per_px)

    def test_srt_file_preserves_cue_without_gps(self):
        body = ("1\n00:00:00,000 --> 00:00:01,000\n" + SRT_LINE +
                "\n\n2\n00:00:01,000 --> 00:00:02,000\nH 2.0m\n")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.SRT"
            path.write_text(body, encoding="utf-8")
            rows = DJISRTParser().parse_file(path)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1].timestamp_ms, 1000)
        self.assertEqual(rows[1].gps_status, "missing")
        self.assertIsNone(rows[1].latitude)

    def test_video_srt_basename_must_match_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "DJI_9901.MP4"
            video.touch()
            with self.assertRaisesRegex(ValueError, "basename"):
                run_video_analysis_task(video, srt_path=Path(tmp) / "DJI_9902.SRT")

    def test_measure_stage_does_not_invent_dimensions_or_ground_gps(self):
        stage = importlib.import_module("src.pipeline.stages.05_measure")
        det = {"frame_index": 1, "box": [10, 20, 40, 80], "class_name": "pothole"}
        ctx = {"deduped_detections": [det], "frames": [{"frame_index": 1,
            "gps": {"latitude": 10.8402, "longitude": 106.8276,
                    "reported_h_m": 1.1, "gimbal_pitch": None}}]}
        result = stage.run(ctx)["measured_detections"][0]
        self.assertIsNone(result["estimated_width_mm"])
        self.assertIsNone(result["estimated_length_m"])
        self.assertIsNone(result["gsd_used"])
        self.assertIsNone(result["ground_latitude"])
        self.assertIsNone(result["ground_longitude"])
        self.assertEqual(result["measurement_status"], "not_measurable")

    def test_legacy_numeric_altitude_and_gsd_without_verification_are_rejected(self):
        stage = importlib.import_module("src.pipeline.stages.05_measure")
        ctx = {"deduped_detections": [{"frame_index": 1, "box": [0, 0, 20, 30]}],
               "frames": [{"frame_index": 1, "gps": {"latitude": 10.8402,
                   "longitude": 106.8276, "rel_alt_m": 10.0,
                   "gimbal_pitch": -90.0, "gsd_mm_per_px": 5.325}}]}
        result = stage.run(ctx)["measured_detections"][0]
        self.assertIsNone(result["gsd_used"])
        self.assertIsNone(result["ground_latitude"])

    def test_verified_agl_and_pose_can_estimate_but_not_fake_location(self):
        import numpy as np
        stage = importlib.import_module("src.pipeline.stages.05_measure")
        ctx = {"deduped_detections": [{"frame_index": 1, "box": [0, 0, 20, 30]}],
               "frames": [{"frame_index": 1, "image": np.zeros((1080, 1920, 3)),
                   "gps": {"latitude": 10.8402, "longitude": 106.8276,
                           "gps_status": "present_unverified",
                           "agl_altitude_m": 10.0, "agl_status": "verified",
                           "gimbal_pitch": -90.0, "gimbal_pitch_status": "verified"}}]}
        result = stage.run(ctx)["measured_detections"][0]
        self.assertEqual(result["measurement_status"], "estimated")
        self.assertAlmostEqual(result["gsd_used"], 7.543, delta=0.01)
        self.assertIsNone(result["ground_latitude"])

    def test_report_keeps_null_dimensions_and_no_ground_geometry(self):
        stage = importlib.import_module("src.pipeline.stages.07_report")
        with tempfile.TemporaryDirectory() as tmp:
            ctx = {"task_id": "telemetry-test", "output_dir": tmp,
                   "video_path": "DJI_9901.MP4", "model_path": "model.pt",
                   "config": {"stages": {"07_report": {"save_crops": False,
                        "save_annotated_frames": False, "save_inspection_pdf": False}}},
                   "inspected_detections": [{"class_name": "pothole", "confidence": 0.8,
                        "estimated_width_mm": None, "estimated_length_m": None,
                        "ground_latitude": None, "ground_longitude": None,
                        "measurement_status": "not_measurable", "telemetry_status": "missing"}]}
            result = stage.run(ctx)["final_report"]
            saved = json.loads((Path(tmp) / "inspection_report.json").read_text(encoding="utf-8"))
            geojson = json.loads((Path(tmp) / "inspection_layer.geojson").read_text(encoding="utf-8"))
        record = result["detections"][0]
        self.assertIsNone(record["estimated_width"])
        self.assertIsNone(record["geometry"])
        self.assertFalse(record["is_2d_estimate"])
        self.assertEqual(saved["detections"][0]["telemetry_status"], "missing")
        self.assertEqual(geojson["features"], [])


if __name__ == "__main__":
    unittest.main()
