"""
tests/test_curation.py — Unit test cho Module Curation & Dataset Exporter
========================================================================
"""

import unittest
import shutil
import numpy as np
import cv2
from pathlib import Path
from src.curation import AIAutoTagger, DatasetExporter


class TestCurationPipeline(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path("F:/train AI đồ án/results/test_curation_tmp")
        self.test_dir.mkdir(parents=True, exist_ok=True)

        # Tạo ảnh crop giả lập: 1 ổ gà (tối lõi, có viền) và 1 nền phẳng (nhẵn)
        self.pothole_crop = self.test_dir / "crop_pothole_mock.jpg"
        img_pothole = np.ones((100, 100, 3), dtype=np.uint8) * 150
        cv2.circle(img_pothole, (50, 50), 30, (30, 30, 30), -1)  # Vùng lõi tối
        cv2.circle(img_pothole, (50, 50), 32, (10, 10, 10), 2)   # Viền sắc nét
        ret, buf = cv2.imencode(".jpg", img_pothole)
        buf.tofile(str(self.pothole_crop))

        self.clean_crop = self.test_dir / "crop_clean_mock.jpg"
        img_clean = np.ones((100, 100, 3), dtype=np.uint8) * 140  # Bề mặt phẳng đồng màu
        ret, buf = cv2.imencode(".jpg", img_clean)
        buf.tofile(str(self.clean_crop))

        # Tạo frame gốc 640x640
        self.mock_frame = self.test_dir / "frame_0001_mock.jpg"
        img_frame = np.ones((640, 640, 3), dtype=np.uint8) * 128
        ret, buf = cv2.imencode(".jpg", img_frame)
        buf.tofile(str(self.mock_frame))

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_auto_tagger_pothole_heuristic(self):
        tagger = AIAutoTagger(provider="builtin_cv_expert")
        res = tagger.analyze_crop(self.pothole_crop, base_class="pothole", confidence=0.85)

        self.assertTrue(res["is_valid"])
        self.assertEqual(res["status"], "VERIFIED")
        self.assertEqual(res["yolo_class_id"], 0)
        self.assertIn("Ổ gà", res["fine_tag"])
        self.assertIn(res["severity"], ["MEDIUM", "CRITICAL"])

    def test_auto_tagger_false_alarm_heuristic(self):
        tagger = AIAutoTagger(provider="builtin_cv_expert")
        res = tagger.analyze_crop(self.clean_crop, base_class="crack", confidence=0.25)

        self.assertFalse(res["is_valid"])
        self.assertEqual(res["status"], "FALSE_ALARM")
        self.assertEqual(res["tag_category"], "hard_negative")
        self.assertEqual(res["yolo_class_id"], -1)

    def test_kdv_inspector_init_and_fallback(self):
        from src.curation.kdv_inspector import KDVInspector
        inspector = KDVInspector()
        self.assertTrue(inspector.is_available)
        self.assertEqual(inspector.model, "gpt-5.4")

        # Test fallback khi file không tồn tại
        res = inspector.inspect_crop("non_existent_file.jpg", "crack", 0.9)
        self.assertFalse(res["is_valid"])
        self.assertEqual(res["status"], "ERROR")

    def test_dataset_exporter(self):
        exporter = DatasetExporter(base_export_dir=self.test_dir / "exports")
        curated_items = [
            {
                "crop_path": str(self.pothole_crop),
                "frame_path": str(self.mock_frame),
                "frame_index": 1,
                "box": [100, 100, 200, 200],
                "class_name": "pothole",
                "yolo_class_id": 0,
                "is_valid": True,
                "status": "VERIFIED",
                "fine_tag": "Ổ gà sâu"
            },
            {
                "crop_path": str(self.clean_crop),
                "frame_path": str(self.mock_frame),
                "frame_index": 1,
                "box": [300, 300, 400, 400],
                "class_name": "crack",
                "yolo_class_id": -1,
                "is_valid": False,
                "status": "FALSE_ALARM",
                "fine_tag": "Báo động giả"
            }
        ]

        res = exporter.export_yolo_dataset(
            curated_items=curated_items,
            frames_lookup={"1": str(self.mock_frame)},
            export_name="test_batch"
        )

        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(Path(res["zip_file"]).exists())
        self.assertGreater(res["zip_size_bytes"], 0)
        self.assertEqual(res["summary"]["pothole_count"], 1)
        self.assertEqual(res["summary"]["hard_negatives_count"], 1)


if __name__ == "__main__":
    unittest.main()
