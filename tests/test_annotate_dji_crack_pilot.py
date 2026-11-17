import csv
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tools.annotate_dji_crack_pilot import (
    create_server, latest_annotation, load_pilot, normalized_boxes, quick_save_payload,
    save_revision, validate_annotation,
)


def source(index=1):
    return {
        "image": f"images/DJI_9901_f{index:06d}_t{index:09d}ms.jpg",
        "image_sha256": "image-hash", "source_video": "fixtures/DJI_9901.MP4",
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
    def test_quick_save_forces_pending_and_keeps_quality_provenance(self):
        old = {"status": "approved", "reviewer": "Engineer", "boxes_xyxy_px": [[1, 2, 9, 10]]}
        incoming = {"annotator": "Pilot", "status": "approved", "quality_decision": "accept",
                    "reviewer": "Impostor", "explicit_review_confirmation": True,
                    "boxes": [{"id": "legacy-1", "label": "crack", "xyxy_px": [1, 2, 9, 10],
                               "review_status": "approved"}]}
        prepared = quick_save_payload(incoming, old)
        self.assertEqual(prepared["status"], "pending_review")
        self.assertEqual(prepared["quality_decision"], "accept")
        self.assertEqual(prepared["reviewer"], "")
        row = validate_annotation(prepared, source(), previous=old)
        self.assertEqual(row["boxes"][0]["approved_by"], "Engineer")
        rejected_quality = quick_save_payload({"annotator": "Pilot", "boxes": []},
                                              {"quality_decision": "reject"})
        self.assertEqual(rejected_quality["quality_decision"], "reject")
        self.assertEqual(validate_annotation(rejected_quality, source())["status"], "pending_review")

    def test_validation_and_approval_gate(self):
        row = validate_annotation(draft(), source())
        self.assertEqual(row["status"], "draft")
        self.assertFalse(row["review_confirmation"])
        self.assertEqual(row["source_video"], "DJI_9901.MP4")
        with self.assertRaises(ValueError):
            validate_annotation(draft(boxes=[[-1, 0, 5, 5]]), source())
        with self.assertRaises(ValueError):
            validate_annotation(draft(status="uncertain", notes=""), source())
        with self.assertRaises(ValueError):
            validate_annotation(draft(status="approved", quality_decision="accept"), source())
        with self.assertRaises(ValueError):
            validate_annotation(draft(status="approved", quality_decision="accept", reviewer="Engineer",
                                      explicit_review_confirmation=True), source(), "provisional_reject")
        approved_box = {"id": "box-1", "label": "crack", "xyxy_px": [1, 2, 9, 10],
                        "review_status": "approved"}
        approved = validate_annotation(draft(status="approved", quality_decision="accept", boxes=[approved_box],
                                             reviewer="Engineer", explicit_review_confirmation=True), source())
        self.assertTrue(approved["review_confirmation"])
        self.assertEqual(approved["boxes_xyxy_px"], [[1.0, 2.0, 9.0, 10.0]])
        with self.assertRaises(ValueError):
            validate_annotation(draft(status="approved", quality_decision="accept", boxes=[],
                                      reviewer="Engineer", explicit_review_confirmation=True), source())

    def test_mixed_labels_ambiguity_and_legacy_preservation(self):
        mixed = draft(status="pending_review", quality_decision="accept", boxes=[
            {"id": "crack-1", "label": "crack", "xyxy_px": [1, 2, 9, 10], "review_status": "draft"},
            {"id": "shadow-1", "label": "tree_shadow", "xyxy_px": [20, 20, 40, 40], "review_status": "draft"},
            {"id": "joint-1", "label": "concrete_joint", "xyxy_px": [45, 20, 60, 30], "review_status": "draft"},
            {"id": "ambiguous-1", "label": "needs_review", "xyxy_px": [60, 50, 80, 60], "review_status": "needs_review"},
        ])
        result = validate_annotation(mixed, source())
        self.assertEqual([box["label"] for box in result["boxes"]],
                         ["crack", "tree_shadow", "concrete_joint", "needs_review"])
        self.assertEqual(result["boxes_xyxy_px"], [[1.0, 2.0, 9.0, 10.0]])
        with self.assertRaises(ValueError):
            validate_annotation(draft(boxes=[{"id": "ambiguous", "label": "needs_review",
                    "xyxy_px": [1, 2, 9, 10], "review_status": "approved"}]), source())
        legacy = {"schema_version": 1, "status": "approved", "reviewer": "Original engineer",
                  "boxes_xyxy_px": [[1, 2, 9, 10]]}
        self.assertEqual(normalized_boxes(legacy)[0]["label"], "crack")
        preserved = validate_annotation(draft(quality_decision="accept", boxes=[
            {"id": "legacy-1", "label": "crack", "xyxy_px": [1, 2, 9, 10], "review_status": "approved"},
            {"id": "shadow-1", "label": "tree_shadow", "xyxy_px": [20, 20, 40, 40], "review_status": "draft"},
        ]), source(), previous=legacy)
        self.assertEqual(len(preserved["boxes"]), 2)
        self.assertEqual(preserved["boxes"][0]["review_status"], "approved")
        self.assertEqual(preserved["boxes"][0]["approved_by"], "Original engineer")
        with self.assertRaises(ValueError):
            validate_annotation(draft(boxes=[]), source(), previous=legacy)
        with self.assertRaises(ValueError):
            validate_annotation(draft(boxes=[{"id": "legacy-1", "label": "crack",
                    "xyxy_px": [1, 2, 9, 10], "review_status": "draft"}]), source(), previous=legacy)
        with self.assertRaises(ValueError):
            validate_annotation(draft(boxes=[{"id": "legacy-1", "label": "concrete_joint",
                    "xyxy_px": [1, 2, 9, 10], "review_status": "needs_review"}]), source(), previous=legacy)
        changed = validate_annotation(draft(boxes=[{"id": "legacy-1", "label": "concrete_joint",
                    "xyxy_px": [1, 2, 9, 10], "review_status": "needs_review"}],
                    reviewer="Engineer", notes="Full-resolution review: clean joint",
                    explicit_review_confirmation=True, allow_reclassify_confirmed=True), source(), previous=legacy)
        self.assertEqual(changed["boxes"][0]["label"], "concrete_joint")
        self.assertEqual(legacy["boxes_xyxy_px"], [[1, 2, 9, 10]])

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
                                     "visual_triage": "provisional_reject" if frame is frames[2] else "provisional_keep",
                                     "review_note": "test"})
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
                mixed = draft(status="pending_review", quality_decision="accept", boxes=[
                    {"id": "crack-1", "label": "crack", "xyxy_px": [1, 2, 9, 10], "review_status": "draft"},
                    {"id": "shadow-1", "label": "tree_shadow", "xyxy_px": [20, 20, 40, 40], "review_status": "draft"},
                ])
                request = Request(base + "/api/annotation/" + name,
                                  data=json.dumps(mixed).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(request) as response:
                    self.assertEqual(response.status, 201)
                with urlopen(base + "/api/annotation/" + name) as response:
                    saved = json.load(response)
                    self.assertEqual([box["label"] for box in saved["boxes"]], ["crack", "tree_shadow"])
                with urlopen(base + "/api/export.json") as response:
                    exported = json.load(response)
                    self.assertEqual(len(exported["boxes"]), 2)
                    self.assertEqual({box["label"] for box in exported["boxes"]}, {"crack", "tree_shadow"})
                with urlopen(base + "/api/export.csv") as response:
                    csv_rows = list(csv.DictReader(response.read().decode("utf-8-sig").splitlines()))
                    self.assertEqual(len(csv_rows), 2)
                    self.assertEqual(csv_rows[1]["image_review_status"], "pending_review")
                with urlopen(base + "/api/history/" + name) as response:
                    history = json.load(response)
                    self.assertEqual(len(history), 3)
                with urlopen(base + "/api/revision/" + name + "/" + history[0]["revision"]) as response:
                    self.assertEqual(json.load(response)["schema_version"], 2)
                old_name = Path(frames[1]["image"]).name
                old = {"schema_version": 1, "status": "approved", "reviewer": "Original engineer",
                       "boxes_xyxy_px": [[1, 2, 9, 10]]}
                old_path = save_revision(pilot, old_name, old)
                old_bytes = old_path.read_bytes()
                addition = draft(status="pending_review", quality_decision="accept", boxes=[
                    {"id": "legacy-1", "label": "crack", "xyxy_px": [1, 2, 9, 10], "review_status": "approved"},
                    {"id": "shadow-1", "label": "tree_shadow", "xyxy_px": [20, 20, 40, 40], "review_status": "draft"},
                ])
                request = Request(base + "/api/annotation/" + old_name,
                                  data=json.dumps(addition).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(request) as response:
                    self.assertEqual(response.status, 201)
                with urlopen(base + "/api/annotation/" + old_name) as response:
                    reopened = json.load(response)
                    self.assertEqual(reopened["boxes"][0]["approved_by"], "Original engineer")
                    self.assertEqual(reopened["boxes"][1]["label"], "tree_shadow")
                self.assertEqual(old_path.read_bytes(), old_bytes)
                quick = Request(base + "/api/save-labels/" + old_name,
                                data=json.dumps({"annotator": "Labeler", "status": "approved",
                                  "reviewer": "Spoofed", "explicit_review_confirmation": True,
                                  "boxes": reopened["boxes"]}).encode(),
                                headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(quick) as response:
                    self.assertEqual(json.load(response)["status"], "pending_review")
                self.assertEqual(old_path.read_bytes(), old_bytes)
                self.assertEqual(latest_annotation(pilot, old_name)["boxes"][0]["approved_by"],
                                 "Original engineer")
                self.assertEqual(latest_annotation(pilot, old_name)["reviewer"], None)
                oblique_name = Path(frames[2]["image"]).name
                oblique = Request(base + "/api/save-labels/" + oblique_name,
                                  data=json.dumps({"annotator": "Labeler", "boxes": [
                                    {"id": "shadow-2", "label": "tree_shadow", "xyxy_px": [20, 20, 40, 40],
                                     "review_status": "draft"}]}).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(oblique) as response:
                    self.assertEqual(json.load(response)["status"], "pending_review")
                self.assertFalse(latest_annotation(pilot, oblique_name)["nadir_branch_eligible"])
                invalid_review = Request(base + "/api/annotation/" + oblique_name,
                    data=json.dumps(draft(status="approved", quality_decision="accept", reviewer="Engineer",
                                          explicit_review_confirmation=True,
                                          boxes=[{"id": "shadow-2", "label": "tree_shadow",
                                                  "xyxy_px": [20, 20, 40, 40], "review_status": "approved"}])).encode(),
                    headers={"Content-Type": "application/json"}, method="POST")
                with self.assertRaises(HTTPError) as error:
                    urlopen(invalid_review)
                self.assertEqual(error.exception.code, 400)
                self.assertEqual(latest_annotation(pilot, oblique_name)["status"], "pending_review")
                new_approval = Request(base + "/api/save-labels/" + name,
                    data=json.dumps({"annotator": "Labeler", "boxes": [
                        {"id": "new-approved", "label": "crack", "xyxy_px": [1, 2, 9, 10],
                         "review_status": "approved"}]}).encode(),
                    headers={"Content-Type": "application/json"}, method="POST")
                with self.assertRaises(HTTPError) as error:
                    urlopen(new_approval)
                self.assertEqual(error.exception.code, 400)
                bad = Request(base + "/api/annotation/not-in-batch.jpg",
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
