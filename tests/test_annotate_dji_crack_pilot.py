import csv
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tools.annotate_dji_crack_pilot import (
    create_server, latest_annotation, load_pilot, validate_annotation,
)


def source(index=1):
    return {
        "image": f"images/DJI_0059_f{index:06d}_t{index:09d}ms.jpg",
        "image_sha256": "image-hash", "source_video": "F:/private/DJI_0059.MP4",
        "source_video_sha256": "video-hash", "source_srt_sha256": "srt-hash",
        "frame_index_zero_based": index, "timestamp_ms_from_fps": index,
        "width_px": 100, "height_px": 80,
    }


def draft(**overrides):
    value = {"status": "draft", "quality_decision": "uncertain", "annotator": "Tester",
             "reviewer": "", "notes": "", "boxes": [[1, 2, 9, 10]],
             "negative_reviewed": False, "explicit_review_confirmation": False,
             "annotation_minutes_actual": 1.5}
    value.update(overrides)
    return value


class AnnotationTest(unittest.TestCase):
    def test_validation_and_approval_gate(self):
        row = validate_annotation(draft(), source())
        self.assertEqual(row["status"], "draft")
        self.assertFalse(row["review_confirmation"])
        self.assertEqual(row["source_video"], "DJI_0059.MP4")
        with self.assertRaises(ValueError):
            validate_annotation(draft(boxes=[[-1, 0, 5, 5]]), source())
        with self.assertRaises(ValueError):
            validate_annotation(draft(status="uncertain", notes=""), source())
        with self.assertRaises(ValueError):
            validate_annotation(draft(status="approved", quality_decision="accept"), source())
        with self.assertRaises(ValueError):
            validate_annotation(draft(status="approved", quality_decision="accept", reviewer="Engineer",
                                      explicit_review_confirmation=True), source(), "provisional_reject")
        approved = validate_annotation(draft(status="approved", quality_decision="accept",
                                             reviewer="Engineer", explicit_review_confirmation=True), source())
        self.assertTrue(approved["review_confirmation"])
        with self.assertRaises(ValueError):
            validate_annotation(draft(status="approved", quality_decision="accept", boxes=[],
                                      reviewer="Engineer", explicit_review_confirmation=True), source())

    def test_local_ui_and_versioned_save(self):
        with tempfile.TemporaryDirectory() as temp:
            pilot = Path(temp)
            (pilot / "images").mkdir()
            frames = [source(i) for i in range(20)]
            for frame in frames:
                (pilot / frame["image"]).write_bytes(b"test-jpeg")
            (pilot / "manifest.json").write_text(json.dumps({"frames": frames}), encoding="utf-8")
            with (pilot / "visual_triage.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["image", "visual_triage", "review_note"])
                writer.writeheader()
                for frame in frames:
                    writer.writerow({"image": Path(frame["image"]).name,
                                     "visual_triage": "provisional_keep", "review_note": "test"})
            load_pilot(pilot)
            server = create_server(pilot, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            name = Path(frames[0]["image"]).name
            try:
                with urlopen(base + "/") as response:
                    self.assertIn(b"RoadGuard", response.read())
                with urlopen(base + "/api/items") as response:
                    self.assertEqual(len(json.load(response)), 20)
                request = Request(base + "/api/annotation/" + name,
                                  data=json.dumps(draft()).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(request) as response:
                    self.assertEqual(response.status, 201)
                with urlopen(request) as response:
                    self.assertEqual(response.status, 201)
                self.assertEqual(len(list((pilot / "annotations" / "revisions").glob("*.json"))), 2)
                self.assertEqual(latest_annotation(pilot, name)["status"], "draft")
                bad = Request(base + "/api/annotation/../../secret",
                              data=json.dumps(draft()).encode(), method="POST")
                with self.assertRaises(HTTPError) as error:
                    urlopen(bad)
                self.assertEqual(error.exception.code, 404)
                foreign = Request(base + "/api/items", headers={"Origin": "https://elsewhere.test"})
                with self.assertRaises(HTTPError) as error:
                    urlopen(foreign)
                self.assertEqual(error.exception.code, 403)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
