"""Local-only annotation UI for the existing 20-frame DJI crack pilot.

Run: python tools/annotate_dji_crack_pilot.py --pilot data/pilots/crack_dji_20261022_batch01
Open the printed 127.0.0.1 URL. Draft/review JSON revisions are saved only under the pilot.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote


STATUSES = {"draft", "pending_review", "uncertain", "reject", "approved"}
BOX_STATUSES = {"draft", "pending_review", "needs_review", "rejected", "approved"}
BOX_LABELS = {
    "crack": "Vết nứt", "concrete_joint": "Khe nối bê tông", "slab_edge": "Mép tấm bê tông",
    "needs_review": "Chưa rõ: nứt/khe/mép", "tree_shadow": "Bóng cây",
    "wire_shadow": "Bóng dây điện", "drone_shadow": "Bóng drone",
    "leaf": "Lá cây", "branch": "Cành cây", "grass": "Cỏ",
    "vegetation_occlusion": "Thực vật che mặt đường", "person": "Người",
    "motorbike": "Xe máy", "car": "Ô tô", "truck": "Xe tải",
    "object": "Vật dụng", "construction_material": "Vật liệu xây dựng",
    "obstacle": "Chướng ngại vật", "dirt_stain": "Vệt bẩn",
    "discoloration": "Vùng đổi màu", "water_stain": "Vệt nước",
}
IMAGE_ID = re.compile(r"DJI_\d{4}_f\d{6}_t\d{9}ms\.jpg\Z")
UI_PATH = Path(__file__).with_name("dji_crack_annotation_ui.html")
ROADMASK_UI_PATH = Path(__file__).with_name("dji_roadmask_review.html")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_pilot(pilot: Path) -> tuple[dict, dict, dict]:
    manifest = json.loads((pilot / "manifest.json").read_text(encoding="utf-8"))
    rows = manifest["frames"]
    if len(rows) != 20:
        raise ValueError("DATA-05 UI is restricted to the existing 20-frame batch")
    images = {Path(row["image"]).name: row for row in rows}
    if len(images) != 20 or not all(IMAGE_ID.fullmatch(name) for name in images):
        raise ValueError("Unexpected image ID or duplicate in pilot manifest")
    triage = {}
    with (pilot / "visual_triage.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            triage[row["image"]] = row
    if set(triage) != set(images):
        raise ValueError("Manifest and triage image lists differ")
    for name, row in images.items():
        if not (pilot / "images" / name).is_file() or row["image"] != f"images/{name}":
            raise FileNotFoundError(f"Missing or misplaced pilot image: {name}")
    return manifest, images, triage


def normalized_boxes(annotation: dict | None) -> list[dict]:
    """Read v1 crack-only revisions without rewriting their original JSON."""
    if not annotation:
        return []
    if "boxes" in annotation:
        return annotation["boxes"]
    status = "approved" if annotation.get("status") == "approved" else "draft"
    return [{"id": f"legacy-{index + 1}", "label": "crack", "xyxy_px": coords,
             "review_status": status,
             "approved_by": annotation.get("reviewer") if status == "approved" else None}
            for index, coords in enumerate(annotation.get("boxes_xyxy_px", []))]


def quick_save_payload(payload: dict, previous: dict | None) -> dict:
    """Create a pending revision without accepting client-supplied review decisions."""
    if not isinstance(payload, dict):
        raise ValueError("Annotation must be a JSON object")
    previous = previous or {}
    quality = previous.get("quality_decision")
    if quality not in {"accept", "uncertain", "reject"}:
        quality = "accept" if previous.get("status") == "approved" else "uncertain"
    return {
        "status": "pending_review", "quality_decision": quality,
        "annotator": payload.get("annotator"), "boxes": payload.get("boxes", []),
        "reviewer": "", "explicit_review_confirmation": False,
        "allow_reclassify_confirmed": False, "negative_reviewed": False,
        "notes": previous.get("notes") or "",
        "annotation_minutes_actual": previous.get("annotation_minutes_actual"),
    }


def validate_annotation(payload: dict, source: dict, visual_triage: str = "uncertain",
                        previous: dict | None = None) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Annotation must be a JSON object")
    status = payload.get("status")
    if status not in STATUSES:
        raise ValueError("Invalid status")
    quality = payload.get("quality_decision")
    if quality not in {"accept", "uncertain", "reject"}:
        raise ValueError("Choose a quality decision")
    annotator = str(payload.get("annotator", "")).strip()
    if not annotator or len(annotator) > 100:
        raise ValueError("Enter annotator name (maximum 100 characters)")
    reviewer = str(payload.get("reviewer", "")).strip()
    notes = str(payload.get("notes", "")).strip()
    if len(reviewer) > 100 or len(notes) > 2000:
        raise ValueError("Reviewer/notes too long")
    boxes = payload.get("boxes", [])
    if not isinstance(boxes, list) or len(boxes) > 200:
        raise ValueError("boxes must be a list of at most 200 labeled boxes")
    width, height = source["width_px"], source["height_px"]
    cleaned_boxes = []
    seen_ids = set()
    for index, raw_box in enumerate(boxes):
        # Keep the v1 API readable; new UI always sends typed box objects.
        box = ({"id": f"legacy-{index + 1}", "label": "crack", "xyxy_px": raw_box,
                "review_status": "draft"} if isinstance(raw_box, list) else raw_box)
        if not isinstance(box, dict):
            raise ValueError("Each box must be an object")
        box_id = box.get("id")
        if not isinstance(box_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", box_id) or box_id in seen_ids:
            raise ValueError("Box IDs must be unique and contain only letters, numbers, _ or -")
        seen_ids.add(box_id)
        label, box_status = box.get("label"), box.get("review_status")
        if label not in BOX_LABELS or box_status not in BOX_STATUSES:
            raise ValueError("Unknown box label or review status")
        if label == "needs_review" and box_status != "needs_review":
            raise ValueError("Ambiguous crack/joint/slab-edge box must be needs_review")
        coords = box.get("xyxy_px")
        if not isinstance(coords, list) or len(coords) != 4 or any(
            not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)
            for value in coords
        ):
            raise ValueError("Each box must contain four finite pixel coordinates")
        x1, y1, x2, y2 = [round(float(value), 2) for value in coords]
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError("Box must have positive area inside the source image")
        cleaned_boxes.append({"id": box_id, "label": label, "xyxy_px": [x1, y1, x2, y2],
                              "review_status": box_status})
    previous_boxes = {box["id"]: box for box in normalized_boxes(previous)}
    old_confirmed = [box for box in previous_boxes.values()
                     if box["label"] == "crack" and box["review_status"] == "approved"]
    for old in old_confirmed:
        matching = next((box for box in cleaned_boxes if box["id"] == old["id"]), None)
        if matching is None or matching["xyxy_px"] != old["xyxy_px"]:
            raise ValueError("Confirmed crack box coordinates/ID cannot be removed or changed")
        if matching["label"] == "crack" and matching["review_status"] != "approved":
            raise ValueError("Confirmed crack box cannot silently lose approved status")
        if matching["label"] != "crack" and not (
            payload.get("allow_reclassify_confirmed") is True and reviewer
            and payload.get("explicit_review_confirmation") is True and notes
        ):
            raise ValueError("Reclassifying confirmed crack needs reviewer, reason and explicit confirmation")
    negative_reviewed = payload.get("negative_reviewed") is True
    active_cracks = [box for box in cleaned_boxes if box["label"] == "crack"
                     and box["review_status"] != "rejected"]
    if negative_reviewed and active_cracks:
        raise ValueError("A frame with crack boxes cannot be marked crack-negative")
    for box in cleaned_boxes:
        old = previous_boxes.get(box["id"])
        approval_carried = (box["review_status"] == "approved" and old is not None
                            and old["review_status"] == "approved"
                            and old["label"] == box["label"] and old["xyxy_px"] == box["xyxy_px"])
        if box["review_status"] == "approved" and not approval_carried and not (
            reviewer and payload.get("explicit_review_confirmation") is True
        ):
            raise ValueError("Newly approved boxes require named reviewer and explicit confirmation")
        box["approved_by"] = ((old.get("approved_by") or (previous or {}).get("reviewer"))
                              if approval_carried else reviewer if box["review_status"] == "approved" else None)
    if any(box["review_status"] == "approved" for box in cleaned_boxes) and (
        visual_triage == "provisional_reject" or quality != "accept"
    ):
        raise ValueError("Box approval requires acceptable quality and non-oblique triage")
    if status == "approved":
        if visual_triage == "provisional_reject" or quality != "accept":
            raise ValueError("Oblique/quality-rejected frames cannot be approved for the nadir branch")
        if not reviewer or not payload.get("explicit_review_confirmation") is True:
            raise ValueError("Approval requires named reviewer and explicit confirmation")
        if any(box["review_status"] in {"draft", "pending_review", "needs_review"} for box in cleaned_boxes):
            raise ValueError("Resolve every box before approving the frame")
        if not active_cracks and not negative_reviewed:
            raise ValueError("Approving a frame without crack requires a full-frame negative review")
    if status in {"uncertain", "reject"} and not notes:
        raise ValueError("Uncertain/reject requires a reason in notes")
    minutes = payload.get("annotation_minutes_actual")
    if minutes is not None and (
        not isinstance(minutes, (int, float)) or isinstance(minutes, bool)
        or not math.isfinite(minutes) or minutes < 0 or minutes > 1440
    ):
        raise ValueError("Annotation minutes must be 0–1440 or null")
    return {
        "schema_version": 2,
        "image": source["image"],
        "image_sha256": source["image_sha256"],
        "source_video": Path(source["source_video"]).name,
        "source_video_sha256": source["source_video_sha256"],
        "source_srt_sha256": source["source_srt_sha256"],
        "frame_index_zero_based": source["frame_index_zero_based"],
        "timestamp_ms_from_fps": source["timestamp_ms_from_fps"],
        "width_px": width,
        "height_px": height,
        "boxes": cleaned_boxes,
        "boxes_xyxy_px": [box["xyxy_px"] for box in active_cracks],
        "status": status,
        "quality_decision": quality,
        "source_visual_triage": visual_triage,
        "nadir_branch_eligible": quality == "accept" and visual_triage != "provisional_reject",
        "negative_reviewed": negative_reviewed,
        "annotator": annotator,
        "reviewer": reviewer or None,
        "notes": notes,
        "annotation_minutes_actual": minutes,
        "saved_utc": datetime.now(timezone.utc).isoformat(),
        "review_confirmation": status == "approved",
        "mask_status": "not_started",
    }


def export_rows(pilot: Path, images: dict) -> list[dict]:
    rows = []
    for image_id, source in images.items():
        annotation = latest_annotation(pilot, image_id)
        if annotation is None:
            continue
        for box in normalized_boxes(annotation):
            x1, y1, x2, y2 = box["xyxy_px"]
            rows.append({
                "image_name": image_id, "image_sha256": source["image_sha256"],
                "source_video": Path(source["source_video"]).name,
                "frame_index_zero_based": source["frame_index_zero_based"],
                "timestamp_ms_from_fps": source["timestamp_ms_from_fps"],
                "box_id": box["id"], "label": box["label"],
                "x_min": x1, "y_min": y1, "x_max": x2, "y_max": y2,
                "box_review_status": box["review_status"],
                "image_review_status": annotation["status"],
                "box_reviewer": box.get("approved_by") or (annotation.get("reviewer") if box["review_status"] == "approved" else None),
                "image_reviewer": annotation.get("reviewer"),
                "nadir_branch_eligible": annotation.get("nadir_branch_eligible", False),
            })
    return rows


EXPORT_FIELDS = ("image_name", "image_sha256", "source_video", "frame_index_zero_based",
                 "timestamp_ms_from_fps", "box_id", "label", "x_min", "y_min", "x_max",
                 "y_max", "box_review_status", "image_review_status", "box_reviewer", "image_reviewer",
                 "nadir_branch_eligible")


def latest_annotation(pilot: Path, image_id: str) -> dict | None:
    versions = sorted((pilot / "annotations" / "revisions").glob(f"{Path(image_id).stem}__r*.json"))
    return json.loads(versions[-1].read_text(encoding="utf-8")) if versions else None


def save_revision(pilot: Path, image_id: str, annotation: dict) -> Path:
    folder = pilot / "annotations" / "revisions"
    folder.mkdir(parents=True, exist_ok=True)
    for number in range(1, 10000):
        target = folder / f"{Path(image_id).stem}__r{number:04d}.json"
        try:
            with target.open("x", encoding="utf-8") as stream:
                json.dump(annotation, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            return target
        except FileExistsError:
            continue
    raise RuntimeError("Too many revisions for this image")


def create_server(pilot: Path, port: int = 8765) -> HTTPServer:
    pilot = pilot.resolve()
    _, images, triage = load_pilot(pilot)
    from tools.roadmask_pilot import RUN_NAME, latest_review, load_run, save_review, validate_review
    roadmask_run = pilot / RUN_NAME
    roadmask_manifest, roadmask_detections = load_run(pilot, roadmask_run) if roadmask_run.is_dir() else (None, None)
    roadmask_frames = ({item["image"]: item for item in roadmask_manifest["frames"]}
                       if roadmask_manifest else {})

    class Handler(BaseHTTPRequestHandler):
        def local_request(self) -> bool:
            expected = f"127.0.0.1:{self.server.server_port}"
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            if host != expected or (origin is not None and origin != f"http://{expected}"):
                self.respond_json(403, {"error": "Local requests only"})
                return False
            return True

        def respond(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:")
            self.end_headers()
            self.wfile.write(body)

        def respond_json(self, code: int, data: dict | list) -> None:
            self.respond(code, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self) -> None:
            if not self.local_request():
                return
            path = unquote(self.path.split("?", 1)[0])
            if path == "/":
                self.respond(200, UI_PATH.read_bytes(), "text/html; charset=utf-8")
            elif path == "/ui.js":
                self.respond(200, UI_PATH.with_suffix(".js").read_bytes(), "text/javascript; charset=utf-8")
            elif path == "/roadmask":
                self.respond(200, ROADMASK_UI_PATH.read_bytes(), "text/html; charset=utf-8")
            elif path == "/roadmask.js":
                self.respond(200, ROADMASK_UI_PATH.with_suffix(".js").read_bytes(), "text/javascript; charset=utf-8")
            elif path == "/api/roadmask/items":
                self.respond_json(200, [{**item,
                    "preliminary_review": (latest_review(roadmask_run, item["image"]) or {}).get(
                        "preliminary_check", "not_checked")}
                    for item in roadmask_manifest["frames"]] if roadmask_manifest else [])
            elif path.startswith("/api/roadmask/record/"):
                name = path.removeprefix("/api/roadmask/record/")
                if name not in roadmask_frames:
                    self.respond_json(404, {"error": "Unknown road-mask image"})
                else:
                    self.respond_json(200, {"frame": roadmask_frames[name],
                                            "detections": roadmask_detections[name],
                                            "review": latest_review(roadmask_run, name)})
            elif path.startswith("/api/roadmask/predicted/"):
                name = path.removeprefix("/api/roadmask/predicted/")
                if name not in roadmask_frames or not roadmask_frames[name]["predicted_mask"]:
                    self.respond_json(404, {"error": "Prediction missing"})
                else:
                    self.respond(200, (roadmask_run / roadmask_frames[name]["predicted_mask"]).read_bytes(),
                                 "image/png")
            elif path == "/api/items":
                self.respond_json(200, [{
                    "id": name, "triage": triage[name],
                    "source_video": Path(row["source_video"]).name,
                    "frame_index": row["frame_index_zero_based"],
                    "timestamp_ms": row["timestamp_ms_from_fps"],
                    "status": (latest_annotation(pilot, name) or {}).get("status", "unlabeled"),
                } for name, row in images.items()])
            elif path == "/api/taxonomy":
                self.respond_json(200, BOX_LABELS)
            elif path == "/api/export.json":
                self.respond_json(200, {"schema_version": 2, "scope": "local_pilot_review_not_training",
                                        "boxes": export_rows(pilot, images)})
            elif path == "/api/export.csv":
                stream = io.StringIO(newline="")
                writer = csv.DictWriter(stream, fieldnames=EXPORT_FIELDS)
                writer.writeheader()
                writer.writerows(export_rows(pilot, images))
                self.respond(200, stream.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8")
            elif path.startswith("/images/"):
                name = path.removeprefix("/images/")
                if name not in images:
                    self.respond_json(404, {"error": "Unknown image"})
                else:
                    self.respond(200, (pilot / "images" / name).read_bytes(), "image/jpeg")
            elif path.startswith("/api/annotation/"):
                name = path.removeprefix("/api/annotation/")
                if name not in images:
                    self.respond_json(404, {"error": "Unknown image"})
                else:
                    self.respond_json(200, latest_annotation(pilot, name) or {})
            elif path.startswith("/api/history/"):
                name = path.removeprefix("/api/history/")
                if name not in images:
                    self.respond_json(404, {"error": "Unknown image"})
                else:
                    revisions = sorted((pilot / "annotations" / "revisions").glob(f"{Path(name).stem}__r*.json"))
                    self.respond_json(200, [{"revision": revision.name,
                                             "saved_utc": (item := json.loads(revision.read_text(encoding="utf-8"))).get("saved_utc"),
                                             "status": item.get("status")}
                                            for revision in revisions])
            elif path.startswith("/api/revision/"):
                parts = path.removeprefix("/api/revision/").split("/")
                if len(parts) != 2 or parts[0] not in images or not re.fullmatch(
                    re.escape(Path(parts[0]).stem) + r"__r\d{4}\.json", parts[1]
                ):
                    self.respond_json(404, {"error": "Unknown revision"})
                else:
                    revision = pilot / "annotations" / "revisions" / parts[1]
                    if not revision.is_file():
                        self.respond_json(404, {"error": "Unknown revision"})
                    else:
                        self.respond(200, revision.read_bytes(), "application/json; charset=utf-8")
            else:
                self.respond_json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            if not self.local_request():
                return
            path = unquote(self.path.split("?", 1)[0])
            if path.startswith("/api/roadmask/review/"):
                name = path.removeprefix("/api/roadmask/review/")
                if name not in roadmask_frames:
                    self.respond_json(404, {"error": "Unknown road-mask image"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > 32768:
                        raise ValueError("Invalid or oversized review")
                    payload = json.loads(self.rfile.read(length))
                    source = {**roadmask_frames[name], "width_px": images[name]["width_px"],
                              "height_px": images[name]["height_px"]}
                    review = validate_review(payload, source)
                    target = save_review(roadmask_run, name, review)
                    self.respond_json(201, {"saved": target.name, "review_status": review["review_status"],
                                            "preliminary_check": review["preliminary_check"]})
                except (ValueError, TypeError, json.JSONDecodeError) as error:
                    self.respond_json(400, {"error": str(error)})
                return
            quick = path.startswith("/api/save-labels/")
            prefix = "/api/save-labels/" if quick else "/api/annotation/"
            name = path.removeprefix(prefix)
            if not path.startswith(prefix) or name not in images:
                self.respond_json(404, {"error": "Unknown image"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 65536:
                    raise ValueError("Invalid or oversized request")
                payload = json.loads(self.rfile.read(length))
                previous = latest_annotation(pilot, name)
                if quick:
                    payload = quick_save_payload(payload, previous)
                annotation = validate_annotation(payload, images[name], triage[name]["visual_triage"],
                                                 previous)
                target = save_revision(pilot, name, annotation)
                self.respond_json(201, {"saved": str(target.relative_to(pilot)), "status": annotation["status"]})
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self.respond_json(400, {"error": str(error)})

        def log_message(self, format: str, *args: object) -> None:
            pass  # Local UI; do not dump filenames/labels into terminal logs.

    return HTTPServer(("127.0.0.1", port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = create_server(args.pilot, args.port)
    print(f"Local annotation UI: http://127.0.0.1:{server.server_port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
