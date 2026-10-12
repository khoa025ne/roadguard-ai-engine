"""
tests/test_dataset_scanner.py — Unit test cho Module DatasetScanner
==================================================================
"""

import unittest
import shutil
import zipfile
from pathlib import Path
import numpy as np
import cv2

from src.ingestion.dataset_scanner import DatasetScanner, safe_imread, safe_imwrite


class MockPredictor:
    """Mock predictor giả lập kết quả inference."""
    def predict_tile(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if np.std(gray) > 5.0:
            return [{
                "class_id": 1,
                "class_name": "crack",
                "confidence": 0.88,
                "box": [50, 50, 150, 150]
            }]
        return []

    def predict_full_frame(self, img, use_tiling=True):
        return self.predict_tile(img)


class TestDatasetScanner(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path("results/test_dataset_scanner_tmp")
        self.test_dir.mkdir(parents=True, exist_ok=True)

        # 1. Tạo 2 ảnh test: 1 ảnh có khuyết tật và 1 ảnh sạch
        self.img_defect = self.test_dir / "road_crack_sample.jpg"
        img1 = np.ones((200, 200, 3), dtype=np.uint8) * 120
        img1[50:150, 50:150] = 20  # Vùng khuyết tật lớn
        safe_imwrite(self.img_defect, img1)

        self.img_clean = self.test_dir / "road_clean_sample.jpg"
        img2 = np.ones((200, 200, 3), dtype=np.uint8) * 128  # Mặt đường phẳng
        safe_imwrite(self.img_clean, img2)

        # 2. Đóng gói thành file .ZIP
        self.mock_zip = self.test_dir / "test_road_dataset.zip"
        with zipfile.ZipFile(str(self.mock_zip), "w") as zf:
            zf.write(str(self.img_defect), arcname="data/crack_01.jpg")
            zf.write(str(self.img_clean), arcname="data/clean_01.jpg")

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_extract_and_find_images(self):
        scanner = DatasetScanner()
        extract_dir = self.test_dir / "extracted"
        images = scanner.extract_zip(self.mock_zip, extract_dir)

        self.assertEqual(len(images), 2)
        self.assertTrue(all(p.exists() for p in images))

    def test_scan_dataset_and_eval_metrics(self):
        scanner = DatasetScanner()
        extract_dir = self.test_dir / "extracted_eval"
        images = scanner.extract_zip(self.mock_zip, extract_dir)

        out_eval = self.test_dir / "eval_results"
        mock_model = MockPredictor()

        report = scanner.scan_images(
            image_paths=images,
            output_dir=out_eval,
            predictor=mock_model
        )

        self.assertEqual(report["status"], "COMPLETED")
        summary = report["summary"]
        self.assertEqual(summary["total_images"], 2)
        self.assertEqual(summary["defect_images"], 1)
        self.assertEqual(summary["clean_images"], 1)
        self.assertEqual(summary["hit_rate_pct"], 50.0)
        self.assertEqual(summary["crack_count"], 1)
        self.assertEqual(summary["total_crops_generated"], 1)

        # Kiểm tra file report JSON
        self.assertTrue(Path(report["report_file"]).exists())
        # Kiểm tra ảnh visualization và crop
        self.assertTrue(len(list((out_eval / "visualizations").glob("*.jpg"))) == 2)
        self.assertTrue(len(list((out_eval / "crops").glob("*.jpg"))) == 1)


if __name__ == "__main__":
    unittest.main()
