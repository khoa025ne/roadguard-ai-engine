"""Extract a small, traceable DJI crack-annotation pilot without creating labels.

Selection is an explicit JSON list of video basenames and zero-based frame indices.
The output directory must not exist, so existing imagery/annotations cannot be replaced.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cv2


MAX_FRAMES = 120
FIRST_BATCH_MAX = 20
MASK_MAX = 40


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_selection(selection: list[dict], registry: dict, first_batch: bool) -> None:
    if not selection or len(selection) > (FIRST_BATCH_MAX if first_batch else MAX_FRAMES):
        raise ValueError("Selection must contain 1–20 first-batch frames or at most 120 total")
    seen = set()
    for item in selection:
        basename, index = item["video"], item["frame_index"]
        if basename not in registry or not isinstance(index, int) or isinstance(index, bool):
            raise ValueError(f"Invalid video/frame index: {item}")
        metadata = registry[basename]
        if index < 0 or index >= metadata["video_metadata"]["frame_count"]:
            raise ValueError(f"Frame out of bounds: {item}")
        key = (basename, index)
        if key in seen:
            raise ValueError(f"Duplicate frame: {key}")
        seen.add(key)


def extract(selection_path: Path, audit_path: Path, output: Path, first_batch: bool = True) -> dict:
    selection = json.loads(selection_path.read_text(encoding="utf-8"))["frames"]
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    registry = {video["basename"]: video for video in audit["videos"]}
    validate_selection(selection, registry, first_batch)
    if output.exists():
        raise FileExistsError(f"Pilot output already exists; refusing to overwrite: {output}")

    # Check all inputs before the first output is written. 5 MP4s may take time to hash.
    used = sorted({item["video"] for item in selection})
    for basename in used:
        record = registry[basename]
        video = Path(record["video"])
        sidecar = Path(record["srt"])
        if not video.is_file() or not sidecar.is_file():
            raise FileNotFoundError(f"Missing source MP4/SRT pair: {basename}")
        if video.stat().st_size != record["video_size_bytes"]:
            raise ValueError(f"Video size changed since survey audit: {basename}")
        if sha256(video) != record["video_sha256"] or sha256(sidecar) != record["srt_sha256"]:
            raise ValueError(f"Source hash changed since survey audit: {basename}")

    output.mkdir(parents=True, exist_ok=False)
    images = output / "images"
    images.mkdir()
    rows = []
    captures = {}
    try:
        for item in selection:
            basename, index = item["video"], item["frame_index"]
            record = registry[basename]
            if basename not in captures:
                captures[basename] = cv2.VideoCapture(record["video"])
                if not captures[basename].isOpened():
                    raise RuntimeError(f"Cannot open video: {basename}")
            capture = captures[basename]
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            actual_next = round(capture.get(cv2.CAP_PROP_POS_FRAMES))
            if not ok or frame is None or actual_next != index + 1:
                raise RuntimeError(f"Cannot decode requested frame exactly: {basename}:{index}, next={actual_next}")
            fps = record["video_metadata"]["fps"]
            timestamp_ms = round(index * 1000 / fps)
            filename = f"{basename}_f{index:06d}_t{timestamp_ms:09d}ms.jpg"
            image_path = images / filename
            ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if not ok:
                raise RuntimeError(f"JPEG encode failed: {basename}:{index}")
            with image_path.open("xb") as stream:
                stream.write(encoded.tobytes())
            reopened = cv2.imread(str(image_path))
            height, width = frame.shape[:2]
            if reopened is None or reopened.shape[:2] != (height, width):
                raise RuntimeError(f"Export validation failed: {image_path}")
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rows.append({
                "image": f"images/{filename}",
                "image_sha256": sha256(image_path),
                "source_video": record["video"],
                "source_video_sha256": record["video_sha256"],
                "source_srt": record["srt"],
                "source_srt_sha256": record["srt_sha256"],
                "frame_index_zero_based": index,
                "timestamp_ms_from_fps": timestamp_ms,
                "timestamp_note": "nominal frame index / ffprobe average FPS; not a synchronized SRT cue or PTS proof",
                "width_px": width,
                "height_px": height,
                "selection_reason": item.get("reason", "sparse visual triage"),
                "luma_mean": round(float(gray.mean()), 2),
                "laplacian_variance": round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2),
                "quality_status": "pending_review",
                "scene_tags_provisional": [],
                "bbox_status": "unlabeled",
                "mask_status": "unlabeled",
                "annotation_review_status": "pending_review",
                "approved_by": None,
                "annotation_minutes_actual": None,
            })
    finally:
        for capture in captures.values():
            capture.release()

    manifest = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "first_20_pending_human_review" if first_batch else "candidate_pending_human_review",
        "caps": {"selected_frames": MAX_FRAMES, "mask_frames": MASK_MAX},
        "selection_file": str(selection_path.resolve()),
        "survey_audit_file": str(audit_path.resolve()),
        "counts_by_video": dict(Counter(Path(row["source_video"]).stem for row in rows)),
        "frames": rows,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "review_queue.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = ["image", "source_video", "frame_index_zero_based", "timestamp_ms_from_fps",
                  "quality_status", "scene_tags_provisional", "bbox_status", "mask_status",
                  "annotation_review_status", "approved_by", "annotation_minutes_actual"]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = extract(args.selection, args.audit, args.output)
    print(json.dumps({"output": str(args.output), "count": len(manifest["frames"]),
                      "by_video": manifest["counts_by_video"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
