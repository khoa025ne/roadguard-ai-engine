import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from tools.prepare_dji_crack_pilot import extract, sha256, validate_selection


class CrackPilotTest(unittest.TestCase):
    def test_limits_duplicates_bounds(self):
        registry = {"DJI_X": {"video_metadata": {"frame_count": 4}}}
        validate_selection([{"video": "DJI_X", "frame_index": 1}], registry, True)
        for bad in ([{"video": "DJI_X", "frame_index": 4}],
                    [{"video": "DJI_X", "frame_index": 1}] * 2,
                    [{"video": "DJI_X", "frame_index": 0}] * 21):
            with self.assertRaises(ValueError):
                validate_selection(bad, registry, True)

    def test_extract_provenance_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            video = root / "DJI_X.avi"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 5, (64, 48))
            self.assertTrue(writer.isOpened())
            for index in range(4):
                writer.write(np.full((48, 64, 3), 30 + index * 40, dtype=np.uint8))
            writer.release()
            srt = root / "DJI_X.SRT"
            srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nGPS (1, 2)\n", encoding="utf-8")
            audit = root / "audit.json"
            audit.write_text(json.dumps({"videos": [{
                "basename": "DJI_X", "video": str(video), "srt": str(srt),
                "video_size_bytes": video.stat().st_size, "video_sha256": sha256(video),
                "srt_sha256": sha256(srt), "video_metadata": {"frame_count": 4, "fps": 5.0},
            }]}), encoding="utf-8")
            selection = root / "selection.json"
            selection.write_text(json.dumps({"frames": [{"video": "DJI_X", "frame_index": 2}]}), encoding="utf-8")
            output = root / "pilot"
            manifest = extract(selection, audit, output)
            row = manifest["frames"][0]
            self.assertEqual(row["timestamp_ms_from_fps"], 400)
            self.assertEqual(row["bbox_status"], "unlabeled")
            self.assertEqual(row["annotation_review_status"], "pending_review")
            self.assertIsNone(row["annotation_minutes_actual"])
            self.assertEqual(row["image_sha256"], sha256(output / row["image"]))
            with self.assertRaises(FileExistsError):
                extract(selection, audit, output)

    def test_source_change_fails_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            video = root / "DJI_X.avi"
            srt = root / "DJI_X.SRT"
            video.write_bytes(b"changed")
            srt.write_bytes(b"x")
            audit = root / "audit.json"
            audit.write_text(json.dumps({"videos": [{"basename": "DJI_X", "video": str(video),
                "srt": str(srt), "video_size_bytes": 7, "video_sha256": "wrong",
                "srt_sha256": sha256(srt), "video_metadata": {"frame_count": 1, "fps": 1}}]}), encoding="utf-8")
            selection = root / "selection.json"
            selection.write_text(json.dumps({"frames": [{"video": "DJI_X", "frame_index": 0}]}), encoding="utf-8")
            output = root / "pilot"
            with self.assertRaises(ValueError):
                extract(selection, audit, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
