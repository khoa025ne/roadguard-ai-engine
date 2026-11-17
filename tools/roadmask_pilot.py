"""Prepare and evaluate a non-production, 20-frame DJI road-mask pilot.

Preparation runs each model once per source image, never edits source assets,
and refuses to overwrite an existing run. Reviews are separate append-only JSON.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.inference.predictor import RoadDefectPredictor
from src.utils.io import safe_imread, safe_imwrite
from tools.annotate_dji_crack_pilot import latest_annotation, load_pilot, normalized_boxes

ROOT = Path(__file__).resolve().parent.parent
RUN_NAME = "roadmask_pilot_v1"
ROAD_WEIGHTS = ROOT / "weights/pretrained/yolo11m-road-seg.pt"
DEFECT_WEIGHTS = ROOT / "weights/trained/roadguard_best_15k.pt"
FT95_WEIGHTS = ROOT / "weights/trained/RoadGuard_YOLO11_UAVPDD2023_FT95_v1.pt"
ISSUE_KINDS = {"false_road", "missing_road", "uncertain_boundary", "occluder"}
CHECKS = {"looks_correct", "needs_correction", "uncertain"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_png(path: Path, mask: np.ndarray) -> None:
    ok, encoded = cv2.imencode(".png", mask)
    if not ok:
        raise RuntimeError(f"Could not encode mask: {path.name}")
    encoded.tofile(str(path))


def read_png(path: Path) -> np.ndarray | None:
    if not path.is_file():
        return None
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)


def predict_road(model, image: np.ndarray) -> np.ndarray | None:
    height, width = image.shape[:2]
    result = model.predict(image, imgsz=640, conf=0.25, verbose=False)[0]
    if result.masks is None or not len(result.masks):
        return None
    mask = np.zeros((height, width), dtype=np.uint8)
    for index, cls in enumerate(result.boxes.cls):
        if int(cls) != 0:
            continue
        raw = result.masks.data[index].cpu().numpy()
        resized = cv2.resize(raw, (width, height), interpolation=cv2.INTER_NEAREST)
        mask = np.maximum(mask, (resized > 0.5).astype(np.uint8) * 255)
    return mask if np.any(mask) else None


def prepare(pilot: Path, output: Path, road_weights: Path = ROAD_WEIGHTS,
            defect_weights: Path = DEFECT_WEIGHTS) -> dict:
    pilot = pilot.resolve()
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"Run already exists; no overwrite: {output}")
    if output.parent != pilot:
        raise ValueError("Pilot run must stay directly under the selected pilot directory")
    _, images, triage = load_pilot(pilot)
    if len(images) != 20:
        raise ValueError("Expected exactly 20 pilot images")
    hashes = []
    for name, row in images.items():
        digest = sha256(pilot / row["image"])
        if digest != row["image_sha256"]:
            raise ValueError(f"Image SHA-256 mismatch: {name}")
        hashes.append(digest)
    if len(set(hashes)) != 20:
        raise ValueError("Duplicate image content in 20-frame pilot")

    from ultralytics import YOLO
    segmenter = YOLO(str(road_weights))
    detector = RoadDefectPredictor(defect_weights, conf_threshold=0.25,
                                   class_map_path=ROOT / "class_map.json")
    if segmenter.task != "segment" or segmenter.names != {0: "road"}:
        raise ValueError("Unexpected road segmentation checkpoint taxonomy")
    if detector.model.task != "detect":
        raise ValueError("Unexpected defect detector task")
    # The checkpoint taxonomy is authoritative; class_map.json describes another model.
    detector.class_map = {int(k): str(v) for k, v in detector.model.names.items()}

    with tempfile.TemporaryDirectory(prefix=".roadmask_build_", dir=pilot) as temp:
        stage = Path(temp) / RUN_NAME
        (stage / "predicted").mkdir(parents=True)
        (stage / "examples").mkdir()
        records = []
        detections = {}
        for name, row in images.items():
            frame = safe_imread(pilot / row["image"])
            if frame is None or frame.shape[:2] != (row["height_px"], row["width_px"]):
                raise ValueError(f"Unreadable or dimension-mismatched image: {name}")
            mask = predict_road(segmenter, frame)
            mask_rel = f"predicted/{Path(name).stem}.png" if mask is not None else None
            if mask_rel:
                write_png(stage / mask_rel, mask)
            raw = detector.predict_full_frame(frame, use_tiling=True)
            detections[name] = [
                {"id": f"det-{index + 1:04d}", "box": [int(v) for v in item["box"]],
                 "class_id": int(item["class_id"]), "class_name": item["class_name"],
                 "confidence": float(item["confidence"])}
                for index, item in enumerate(raw)
            ]
            old = latest_annotation(pilot, name) or {}
            records.append({
                "image": name, "image_sha256": row["image_sha256"],
                "source_video": Path(row["source_video"]).name,
                "source_video_sha256": row["source_video_sha256"],
                "source_srt": Path(row["source_srt"]).name,
                "source_srt_sha256": row["source_srt_sha256"],
                "frame_index_zero_based": row["frame_index_zero_based"],
                "timestamp_ms_from_fps_nominal": row["timestamp_ms_from_fps"],
                "timestamp_note": row["timestamp_note"],
                "route_segment": None, "survey_independence": "unverified",
                "triage": triage[name]["visual_triage"],
                "box_annotation_status_at_prepare": old.get("status", "unlabeled"),
                "quality_decision_at_prepare": old.get("quality_decision", "unverified"),
                "prediction_status": "predicted_unreviewed" if mask_rel else "prediction_missing",
                "predicted_mask": mask_rel,
                "predicted_mask_sha256": sha256(stage / mask_rel) if mask_rel else None,
                "human_review_status": "pending_review",
                "engineering_approval_status": "not_requested",
                "raw_detection_count": len(raw),
            })
        artifact = {
            "schema_version": 1, "scope": "local_pilot_not_training_or_production",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "road_model": {"path": str(road_weights), "sha256": sha256(road_weights),
                           "conf": 0.25, "imgsz": 640, "fallback": "none"},
            "defect_model": {"path": str(defect_weights), "sha256": sha256(defect_weights),
                             "conf": 0.25, "tiling": True, "tile_size": 640, "tile_overlap": 0.2,
                             "class_names": detector.class_map, "run_once_per_image": True},
            "versions": {"ultralytics": __import__("ultralytics").__version__,
                         "torch": __import__("torch").__version__, "opencv": cv2.__version__},
            "frames": records,
        }
        (stage / "manifest.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")
        (stage / "raw_detections.json").write_text(json.dumps(detections, ensure_ascii=False, indent=2) + "\n",
                                                      encoding="utf-8")
        # Representative original/overlay pairs; a missing prediction is visibly marked, not filled in.
        edge = next((item for item in records if item["triage"] == "uncertain" and item["predicted_mask"]), records[0])
        missing = next((item for item in records if not item["predicted_mask"]), None)
        for kind, item in (("edge", edge), ("missing", missing)):
            if item is None:
                continue
            frame = safe_imread(pilot / "images" / item["image"])
            mask = read_png(stage / item["predicted_mask"]) if item["predicted_mask"] else None
            overlay = frame.copy()
            if mask is not None:
                color = np.zeros_like(frame)
                color[:, :] = (230, 125, 35)
                blended = cv2.addWeighted(frame, 0.60, color, 0.40, 0)
                overlay[mask > 0] = blended[mask > 0]
                label = "PREDICTED ROAD (unreviewed)"
            else:
                label = "NO ROAD PREDICTION - NEEDS REVIEW"
            cv2.putText(overlay, label, (18, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                        (0, 0, 255) if mask is None else (255, 255, 255), 3)
            pair = cv2.hconcat((cv2.resize(frame, (960, 540)), cv2.resize(overlay, (960, 540))))
            if not safe_imwrite(stage / "examples" / f"{kind}_original_vs_prediction.jpg", pair):
                raise RuntimeError("Could not write diagnostic example")
        stage.rename(output)
    return artifact


def load_run(pilot: Path, run: Path) -> tuple[dict, dict]:
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    frames = {row["image"]: row for row in manifest["frames"]}
    if len(frames) != 20 or set(frames) != set(load_pilot(pilot)[1]):
        raise ValueError("Road-mask run does not match the 20-frame pilot")
    detections = json.loads((run / "raw_detections.json").read_text(encoding="utf-8"))
    if set(detections) != set(frames):
        raise ValueError("Raw detections do not match pilot images")
    return manifest, detections


def latest_review(run: Path, image: str) -> dict | None:
    versions = sorted((run / "reviews").glob(f"{Path(image).stem}__r*.json"))
    return json.loads(versions[-1].read_text(encoding="utf-8")) if versions else None


def validate_review(payload: dict, source: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Review must be an object")
    name = payload.get("checked_by")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        raise ValueError("Enter the preliminary reviewer's name")
    check = payload.get("preliminary_check")
    if check not in CHECKS:
        raise ValueError("Choose a preliminary check result")
    notes = payload.get("notes", "")
    if not isinstance(notes, str) or len(notes) > 2000:
        raise ValueError("Notes must be text of at most 2000 characters")
    issues = payload.get("issues", [])
    if not isinstance(issues, list) or len(issues) > 100:
        raise ValueError("At most 100 issue rectangles are allowed")
    cleaned = []
    for issue in issues:
        if not isinstance(issue, dict) or issue.get("kind") not in ISSUE_KINDS:
            raise ValueError("Unknown mask issue")
        box = issue.get("box")
        if not isinstance(box, list) or len(box) != 4 or any(
            not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in box
        ):
            raise ValueError("Issue box must contain four pixel coordinates")
        x1, y1, x2, y2 = [int(v) for v in box]
        if not (0 <= x1 < x2 <= source["width_px"] and 0 <= y1 < y2 <= source["height_px"]):
            raise ValueError("Issue box must be inside image")
        cleaned.append({"kind": issue["kind"], "box": [x1, y1, x2, y2]})
    if check == "looks_correct" and cleaned:
        raise ValueError("A mask with marked errors cannot be called correct")
    if source["prediction_status"] == "prediction_missing" and check == "looks_correct":
        raise ValueError("A missing prediction cannot be called correct")
    minutes = payload.get("minutes_actual")
    if minutes is not None and (
        not isinstance(minutes, (int, float)) or isinstance(minutes, bool)
        or not math.isfinite(minutes) or minutes < 0 or minutes > 1440
    ):
        raise ValueError("Review minutes must be 0–1440 or null")
    return {
        "schema_version": 1, "image": source["image"], "image_sha256": source["image_sha256"],
        "prediction_status": source["prediction_status"],
        "review_status": "pending_review", "engineering_approval_status": "not_requested",
        "preliminary_check": check, "checked_by": name.strip(), "notes": notes.strip(),
        "issues": cleaned, "minutes_actual": minutes,
        "saved_utc": datetime.now(timezone.utc).isoformat(),
    }


def save_review(run: Path, image: str, review: dict) -> Path:
    folder = run / "reviews"
    folder.mkdir(exist_ok=True)
    for number in range(1, 10000):
        path = folder / f"{Path(image).stem}__r{number:04d}.json"
        try:
            with path.open("x", encoding="utf-8") as stream:
                json.dump(review, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            return path
        except FileExistsError:
            continue
    raise RuntimeError("Too many road-mask reviews")


def box_overlap(box: list[int], mask: np.ndarray) -> float:
    height, width = mask.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in box]
    x1, x2 = max(0, min(width, x1)), max(0, min(width, x2))
    y1, y2 = max(0, min(height, y1)), max(0, min(height, y2))
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return float(np.count_nonzero(mask[y1:y2, x1:x2])) / ((x2 - x1) * (y2 - y1))


def intersects(a: list[int], b: list[int]) -> bool:
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def route_detection(det: dict, mask: np.ndarray | None, review: dict | None,
                    approved_cracks: list[list[int]], edge_px: int = 16) -> dict:
    box = det["box"]
    if any(intersects(box, crack) for crack in approved_cracks):
        return {"route": "needs_review", "reason": "overlaps_approved_crack_protected"}
    if mask is None:
        return {"route": "needs_review", "reason": "road_prediction_missing"}
    if review and review.get("preliminary_check") == "uncertain":
        return {"route": "needs_review", "reason": "mask_marked_uncertain"}
    issues = (review or {}).get("issues", [])
    if any(intersects(box, issue["box"]) for issue in issues):
        return {"route": "needs_review", "reason": "marked_mask_issue"}
    overlap = box_overlap(box, mask)
    if overlap >= 0.60:
        return {"route": "candidate", "reason": "road_overlap", "road_overlap": round(overlap, 4)}
    if overlap > 0:
        return {"route": "needs_review", "reason": "road_boundary_or_partial", "road_overlap": round(overlap, 4)}
    height, width = mask.shape[:2]
    x1, y1, x2, y2 = box
    padded = [max(0, x1-edge_px), max(0, y1-edge_px), min(width, x2+edge_px), min(height, y2+edge_px)]
    if box_overlap(padded, mask) > 0:
        return {"route": "needs_review", "reason": "within_road_edge_band", "road_overlap": 0.0}
    if review and review.get("preliminary_check") in {"looks_correct", "needs_correction"}:
        return {"route": "reject", "reason": "outside_prelim_checked_road", "road_overlap": 0.0}
    return {"route": "needs_review", "reason": "outside_unreviewed_road", "road_overlap": 0.0}


def evaluate(pilot: Path, run: Path) -> dict:
    manifest, detections = load_run(pilot, run)
    rows = []
    counts = Counter()
    reasons = Counter()
    approved_total = 0
    approved_unmatched = []
    for frame in manifest["frames"]:
        name = frame["image"]
        mask = read_png(run / frame["predicted_mask"]) if frame["predicted_mask"] else None
        if mask is not None and mask.shape != (1080, 1920):
            raise ValueError(f"Wrong mask dimensions: {name}")
        review = latest_review(run, name)
        old = latest_annotation(pilot, name)
        approved_cracks = [box["xyxy_px"] for box in normalized_boxes(old)
                           if box["label"] == "crack" and box["review_status"] == "approved"]
        approved_total += len(approved_cracks)
        for index, crack in enumerate(approved_cracks, 1):
            if not any(intersects(det["box"], crack) for det in detections[name]):
                approved_unmatched.append({"image": name, "approved_crack_index": index,
                                           "reason": "no_raw_detector_overlap"})
        for det in detections[name]:
            routed = route_detection(det, mask, review, approved_cracks)
            counts[routed["route"]] += 1
            reasons[routed["reason"]] += 1
            rows.append({"image": name, "detection_id": det["id"], "class_name": det["class_name"],
                         "confidence": det["confidence"], "box": det["box"],
                         "baseline": "candidate", "route": routed["route"],
                         "reason": routed["reason"], "road_overlap": routed.get("road_overlap"),
                         "mask_review": (review or {}).get("preliminary_check", "unreviewed"),
                         "triage": frame["triage"]})
    return {
        "scope": "paired_local_pilot_not_holdout_or_production",
        "raw_detections_count": len(rows), "routed_counts": dict(counts),
        "routing_reasons": dict(reasons),
        "approved_crack_boxes_in_latest_revisions": approved_total,
        "approved_crack_boxes_without_raw_detector_overlap": approved_unmatched,
        "prelim_reviewed_masks": sum(latest_review(run, f["image"]) is not None for f in manifest["frames"]),
        "missing_predictions": sum(f["prediction_status"] == "prediction_missing" for f in manifest["frames"]),
        "false_positive_nonroad_before": None, "false_positive_nonroad_after": None,
        "crack_recall_before": None, "crack_recall_after": None,
        "target_20pct_fp_reduction_status": "insufficient_verified_reference_labels",
        "detections": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, default=ROOT / "data/pilots/crack_dji_20261022_batch01")
    parser.add_argument("--run", type=Path)
    parser.add_argument("--defect-weights", type=Path, default=DEFECT_WEIGHTS)
    parser.add_argument("--output", type=Path, help="New JSON result path for --evaluate; never overwritten")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()
    run = args.run or args.pilot / RUN_NAME
    if args.prepare == args.evaluate:
        parser.error("Choose exactly one of --prepare or --evaluate")
    try:
        result = prepare(args.pilot, run, defect_weights=args.defect_weights) if args.prepare else evaluate(args.pilot, run)
    except (FileExistsError, ValueError) as error:
        parser.exit(2, f"{error}\n")
    if args.prepare:
        print(json.dumps({"frames": len(result["frames"]),
                          "predicted": sum(bool(f["predicted_mask"]) for f in result["frames"]),
                          "raw_detections": sum(f["raw_detection_count"] for f in result["frames"]),
                          "run": str(run)}, ensure_ascii=False))
    else:
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        summary = {key: value for key, value in result.items() if key != "detections"}
        print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
