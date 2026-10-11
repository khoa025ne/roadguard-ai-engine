"""
tests/test_crack_and_dedup.py — Unit test cho CrackAnalyzer & DefectDeduplicator
================================================================================
"""

import unittest
import numpy as np
import cv2
from pathlib import Path
import shutil

from src.curation.crack_analyzer import CrackAnalyzer, CRACK_CLASSES
from src.curation.deduplicator import DefectDeduplicator
from src.curation.auto_tagger import AIAutoTagger


class TestCrackAndDedup(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path("results/test_crack_dedup_tmp")
        self.test_dir.mkdir(parents=True, exist_ok=True)

        # Tạo ảnh vết nứt dọc (đường nứt đen dọc giữa ảnh)
        self.long_crack = self.test_dir / "crop_long_crack.jpg"
        img_long = np.ones((120, 120, 3), dtype=np.uint8) * 160
        cv2.line(img_long, (60, 10), (60, 110), (20, 20, 20), 4)  # vệt nứt dọc
        cv2.line(img_long, (58, 20), (62, 90), (10, 10, 10), 2)
        cv2.imencode(".jpg", img_long)[1].tofile(str(self.long_crack))

        # Tạo ảnh vết nứt ngang (đường nứt đen ngang)
        self.trans_crack = self.test_dir / "crop_trans_crack.jpg"
        img_trans = np.ones((120, 120, 3), dtype=np.uint8) * 160
        cv2.line(img_trans, (10, 60), (110, 60), (20, 20, 20), 4)  # vệt nứt ngang
        cv2.imencode(".jpg", img_trans)[1].tofile(str(self.trans_crack))

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_crack_analyzer_longitudinal(self):
        res = CrackAnalyzer.analyze_crop_image(self.long_crack, confidence=0.88)
        self.assertTrue(res["is_valid"])
        self.assertEqual(res["status"], "VERIFIED")
        self.assertEqual(res["yolo_class_id"], 1)
        self.assertIn("crack", res["fine_tag_code"])
        self.assertIn("crack_width_level", res)
        self.assertIn("recommendation", res)
        self.assertIn("structural_risk", res)

    def test_defect_deduplicator(self):
        dedup = DefectDeduplicator()

        # Giả lập 3 item: 2 item đầu là cùng 1 ổ gà ở 2 frame liên tiếp (t=1.0s và t=1.5s)
        items = [
            {
                "crop_id": "c1",
                "class_name": "pothole",
                "confidence": 0.90,
                "timestamp_s": 1.0,
                "frame_index": 2,
                "box": [100, 200, 160, 260],
                "crop_path": str(self.long_crack)
            },
            {
                "crop_id": "c2",
                "class_name": "pothole",
                "confidence": 0.82,
                "timestamp_s": 1.5,
                "frame_index": 3,
                "box": [105, 220, 165, 280],
                "crop_path": str(self.long_crack)
            },
            {
                "crop_id": "c3",
                "class_name": "crack",
                "confidence": 0.85,
                "timestamp_s": 8.0,
                "frame_index": 16,
                "box": [400, 500, 480, 580],
                "crop_path": str(self.trans_crack)
            }
        ]

        res = dedup.deduplicate(items)
        # Kỳ vọng: 3 ảnh đầu vào nhưng chỉ có 2 khuyết tật độc nhất (1 pothole + 1 crack)
        self.assertEqual(res["total_items"], 3)
        self.assertEqual(res["unique_count"], 2)
        self.assertEqual(res["duplicate_count"], 1)

        # Item c1 là primary và có duplicate_views chứa c2
        unique_items = res["unique_items"]
        pothole_item = next(it for it in unique_items if it["crop_id"] == "c1")
        self.assertTrue(pothole_item["is_primary"])
        self.assertFalse(pothole_item["is_duplicate"])
        self.assertEqual(len(pothole_item["duplicate_views"]), 1)
        self.assertEqual(pothole_item["duplicate_views"][0]["crop_id"], "c2")

    def test_auto_tagger_batch_curate(self):
        tagger = AIAutoTagger(provider="builtin_cv_expert")
        items = [
            {
                "crop_id": "c_crack_1",
                "class_name": "crack",
                "confidence": 0.85,
                "timestamp_s": 2.0,
                "frame_index": 4,
                "crop_path": str(self.long_crack)
            },
            {
                "crop_id": "c_crack_2",
                "class_name": "crack",
                "confidence": 0.75,
                "timestamp_s": 2.5,
                "frame_index": 5,
                "crop_path": str(self.long_crack)
            }
        ]

        curated = tagger.curate_batch(items, batch_size=100, apply_dedup=True)
        self.assertEqual(len(curated), 2)
        # Sau khi khử trùng lặp, c_crack_1 là primary và c_crack_2 là duplicate
        self.assertTrue(curated[0]["is_primary"])
        self.assertFalse(curated[0]["is_duplicate"])
        self.assertTrue(curated[1]["is_duplicate"])
