"""Local-only annotation UI for the existing 20-frame DJI crack pilot.

Run: python tools/annotate_dji_crack_pilot.py --pilot data/pilots/crack_dji_20261022_batch01
Open the printed 127.0.0.1 URL. Draft/review JSON revisions are saved only under the pilot.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote


STATUSES = {"draft", "pending_review", "uncertain", "reject", "approved"}
IMAGE_ID = re.compile(r"DJI_\d{4}_f\d{6}_t\d{9}ms\.jpg\Z")
UI_PATH = Path(__file__).with_name("dji_crack_annotation_ui.html")


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


def validate_annotation(payload: dict, source: dict, visual_triage: str = "uncertain") -> dict:
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
        raise ValueError("boxes must be a list of at most 200 crack boxes")
    width, height = source["width_px"], source["height_px"]
    cleaned_boxes = []
    for box in boxes:
        if not isinstance(box, list) or len(box) != 4 or any(
            not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)
            for value in box
        ):
            raise ValueError("Each box must contain four finite pixel coordinates")
        x1, y1, x2, y2 = [round(float(value), 2) for value in box]
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError("Box must have positive area inside the source image")
        cleaned_boxes.append([x1, y1, x2, y2])
    negative_reviewed = payload.get("negative_reviewed") is True
    if status == "approved":
        if visual_triage == "provisional_reject" or quality != "accept":
            raise ValueError("Oblique/quality-rejected frames cannot be approved for the nadir branch")
        if not reviewer or not payload.get("explicit_review_confirmation") is True:
            raise ValueError("Approval requires named reviewer and explicit confirmation")
        if not cleaned_boxes and not negative_reviewed:
            raise ValueError("Approving zero boxes requires a full-frame negative review")
    if status in {"uncertain", "reject"} and not notes:
        raise ValueError("Uncertain/reject requires a reason in notes")
    minutes = payload.get("annotation_minutes_actual")
    if minutes is not None and (
        not isinstance(minutes, (int, float)) or isinstance(minutes, bool)
        or not math.isfinite(minutes) or minutes < 0 or minutes > 1440
    ):
        raise ValueError("Annotation minutes must be 0–1440 or null")
    return {
        "schema_version": 1,
        "image": source["image"],
        "image_sha256": source["image_sha256"],
        "source_video": Path(source["source_video"]).name,
        "source_video_sha256": source["source_video_sha256"],
        "source_srt_sha256": source["source_srt_sha256"],
        "frame_index_zero_based": source["frame_index_zero_based"],
        "timestamp_ms_from_fps": source["timestamp_ms_from_fps"],
        "width_px": width,
        "height_px": height,
        "label": "crack",
        "boxes_xyxy_px": cleaned_boxes,
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
            elif path == "/api/items":
                self.respond_json(200, [{
                    "id": name, "triage": triage[name],
                    "source_video": Path(row["source_video"]).name,
                    "frame_index": row["frame_index_zero_based"],
                    "timestamp_ms": row["timestamp_ms_from_fps"],
                    "status": (latest_annotation(pilot, name) or {}).get("status", "unlabeled"),
                } for name, row in images.items()])
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
            else:
                self.respond_json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            if not self.local_request():
                return
            name = unquote(self.path.split("?", 1)[0]).removeprefix("/api/annotation/")
            if not self.path.startswith("/api/annotation/") or name not in images:
                self.respond_json(404, {"error": "Unknown image"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 65536:
                    raise ValueError("Invalid or oversized request")
                payload = json.loads(self.rfile.read(length))
                annotation = validate_annotation(payload, images[name], triage[name]["visual_triage"])
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
