"""
tests/test_ui_curation_endpoints.py — Unit test cho API Curation & Crack Assessment & Deduplication
===================================================================================================
"""

import unittest
import shutil
import json
from pathlib import Path
import cv2
import numpy as np
from fastapi.testclient import TestClient

from src.api.ui_server import app, RESULTS_DIR


class TestUICurationEndpoints(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.task_id = "test_curation_task_999"
        self.task_dir = RESULTS_DIR / self.task_id
        self.crops_dir = self.task_dir / "crops"
        self.crops_dir.mkdir(parents=True, exist_ok=True)

        # Tạo ảnh crop giả lập vết nứt
        self.crop1 = self.crops_dir / "crop_test_0001.jpg"
        img1 = np.ones((100, 100, 3), dtype=np.uint8) * 150
        cv2.line(img1, (50, 10), (50, 90), (20, 20, 20), 4)
        cv2.imencode(".jpg", img1)[1].tofile(str(self.crop1))

        # Tạo ảnh crop thứ 2 là trùng lặp của crop1 (cách 0.5s)
        self.crop2 = self.crops_dir / "crop_test_0002.jpg"
        img2 = np.ones((100, 100, 3), dtype=np.uint8) * 150
        cv2.line(img2, (52, 12), (52, 92), (20, 20, 20), 4)
        cv2.imencode(".jpg", img2)[1].tofile(str(self.crop2))

        # Tạo ảnh crop thứ 3 độc lập (cách 10.0s)
        self.crop3 = self.crops_dir / "crop_test_0003.jpg"
        img3 = np.ones((100, 100, 3), dtype=np.uint8) * 150
        cv2.circle(img3, (50, 50), 25, (20, 20, 20), -1)
        cv2.imencode(".jpg", img3)[1].tofile(str(self.crop3))

    def tearDown(self):
        if self.task_dir.exists():
            shutil.rmtree(self.task_dir, ignore_errors=True)

    def test_filter_and_tag_with_batching_and_deduplication(self):
        payload = {
            "task_id": self.task_id,
            "items": [
                {
                    "crop_id": "c1",
                    "class_name": "crack",
                    "confidence": 0.88,
                    "timestamp_s": 1.0,
                    "frame_index": 2,
                    "box": [100, 100, 200, 200],
                    "crop_path": str(self.crop1)
                },
                {
                    "crop_id": "c2",
                    "class_name": "crack",
                    "confidence": 0.82,
                    "timestamp_s": 1.5,
                    "frame_index": 3,
                    "box": [105, 105, 205, 205],
                    "crop_path": str(self.crop2)
                },
                {
                    "crop_id": "c3",
                    "class_name": "pothole",
                    "confidence": 0.85,
                    "timestamp_s": 10.0,
                    "frame_index": 20,
                    "box": [300, 300, 400, 400],
                    "crop_path": str(self.crop3)
                }
            ],
            "batch_size": 100,
            "apply_dedup": True
        }

        res = self.client.post("/api/curation/filter-and-tag", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["total_items"], 3)
        # 3 ảnh nhưng crop1 và crop2 trùng lặp -> unique_count = 2
        self.assertEqual(data["unique_count"], 2)
        self.assertEqual(data["duplicate_count"], 1)
        # Số request sử dụng: 3 ảnh gom trong 1 batch 100 -> 1 request
        self.assertEqual(data["requests_used"], 1)

        # File curated_results.json phải được lưu
        cur_file = self.task_dir / "curated_results.json"
        self.assertTrue(cur_file.exists())

    def test_assess_cracks_endpoint(self):
        payload = {
            "task_id": self.task_id,
            "items": [
                {
                    "crop_id": "c1",
                    "class_name": "crack",
                    "confidence": 0.88,
                    "timestamp_s": 1.0,
                    "frame_index": 2,
                    "crop_path": str(self.crop1)
                }
            ]
        }
        res = self.client.post("/api/curation/assess-cracks", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        item = data["curated_items"][0]
        self.assertIn("crack", item["fine_tag_code"])
        self.assertIn("crack_width_level", item)
        self.assertIn("recommendation", item)
        self.assertIn("structural_risk", item)

    def test_update_item_persistence(self):
        # Thiết lập sẵn file curated_results.json
        cur_file = self.task_dir / "curated_results.json"
        initial_items = [
            {
                "crop_id": "c1",
                "fine_tag": "Vết nứt dọc tuyến",
                "severity": "MEDIUM",
                "reasoning": "Đánh giá ban đầu của AI",
                "is_valid": True
            }
        ]
        with open(cur_file, "w", encoding="utf-8") as f:
            json.dump(initial_items, f, ensure_ascii=False)

        # Người dùng chỉnh sửa nhận định
        updated_item = {
            "crop_id": "c1",
            "fine_tag": "Vết nứt chân chim / nứt lưới",
            "severity": "CRITICAL",
            "reasoning": "Kỹ sư giám định: Nứt lưới mai rùa nguy hiểm, cần cắt vá khẩn cấp",
            "recommendation": "Cắt bóc toàn bộ móng đường và thảm lại",
            "is_valid": True
        }
        update_payload = {
            "task_id": self.task_id,
            "item_index": 0,
            "updated_item": updated_item
        }

        res = self.client.post("/api/curation/update-item", json=update_payload)
        self.assertEqual(res.status_code, 200)

        # Đọc lại từ endpoint GET /api/curation/results/{task_id}
        get_res = self.client.get(f"/api/curation/results/{self.task_id}")
        self.assertEqual(get_res.status_code, 200)
        saved_items = get_res.json()["curated_items"]
        self.assertEqual(len(saved_items), 1)
        self.assertEqual(saved_items[0]["severity"], "CRITICAL")
        self.assertTrue(saved_items[0]["user_edited"])
        self.assertIn("Kỹ sư giám định", saved_items[0]["reasoning"])
