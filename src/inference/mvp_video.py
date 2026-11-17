"""RG-AI-MVP-VIDEO-28: two PO-approved checkpoints; no fallback."""
import hashlib
import json
import time
import math
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[2]
MODELS = (
    ("CRACK", "Crack V1", ROOT / "weights/trained/roadguard_crack_yolo11n_v1.pt", {"crack"}),
    ("POTHOLE", "Pothole best mới", ROOT / "weights/trained/best (1).pt", {"pothole", "potholes"}),
)


def load_models(selection=None, expected_models=None):
    loaded, metadata = [], []
    entries = MODELS
    pinned = {}
    if selection is not None:
        from src.inference.video_models import resolve_models
        resolved = resolve_models(selection)
        entries = [(task, row["name"], path, {str(n).lower() for n in row["classes"].values()})
                   for task, row, path in resolved]
        pinned = {task: row for task, row, _ in resolved}
    for category, label, path, allowed in entries:
        if not path.is_file():
            raise FileNotFoundError(f"Thiếu checkpoint: {label}")
        started = time.perf_counter()
        model = YOLO(str(path))
        names = {int(k): str(v) for k, v in model.names.items()}
        if model.task != "detect" or not names or set(n.lower() for n in names.values()) - allowed:
            raise ValueError(f"Sai task/class mapping: {label}: {names}")
        loaded.append((category, label, model))
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if category in pinned and digest != pinned[category]["sha256"]:
            raise ValueError("MODEL_CHANGED")
        expected = next((m for m in (expected_models or []) if m["task"] == category), None)
        if expected and digest != expected["sha256"]:
            raise ValueError("MODEL_CHANGED")
        metadata.append({"category": category, "label": label, "path": path.name,
                         "id": pinned.get(category, {}).get("id"), "version": digest[:12],
                         "sha256": digest,
                         "classes": names, "runtime": "ultralytics / CPU", "load_ms": round((time.perf_counter()-started)*1000, 2)})
    return loaded, metadata


def sample_indices(total, fps, sample_fps):
    """Time-based sampling prevents 25fps / 2fps rounding from yielding 625 frames."""
    rate = min(fps, sample_fps) if sample_fps is not None else fps
    if rate == fps:
        return list(range(total))
    count = math.ceil(total / fps * rate - 1e-8)
    return list(dict.fromkeys(min(total - 1, int(i * fps / rate)) for i in range(count)))


def load_segmenter(model_id, expected=None):
    from src.inference.video_models import resolve_segment_model
    row, path = resolve_segment_model(model_id)
    model = YOLO(str(path))
    names = {int(k): str(v).strip().lower() for k, v in model.names.items()}
    if model.task != 'segment' or names != {0: 'road'}:
        raise ValueError('SEGMENT_CLASS_MAPPING_UNSUPPORTED')
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != row['sha256'] or (expected and digest != expected['sha256']):
        raise ValueError('MODEL_CHANGED')
    import ultralytics
    return model, {'id': row['id'], 'name': path.name, 'task': 'segment', 'classes': names,
                   'sha256': digest, 'version': digest[:12], 'ultralytics': ultralytics.__version__,
                   'conf': .25, 'imgsz': 640, 'retina_masks': True, 'mask_threshold': .5,
                   'review_status': 'ai_prediction_not_ground_truth'}


def segment_frame(model, frame):
    result = model.predict(frame.copy(), conf=.25, imgsz=640, retina_masks=True, device='cpu', verbose=False)[0]
    if result.masks is None or not len(result.masks):
        return None
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    for i, cls in enumerate(result.boxes.cls):
        if int(cls) != 0:
            continue
        raw = result.masks.data[i].cpu().numpy()
        if raw.shape != mask.shape:
            raise ValueError('SEGMENT_MASK_SHAPE_INVALID')
        mask = np.maximum(mask, (raw > .5).astype(np.uint8)*255)
    return mask if mask.any() else None


def road_overlap(box, mask):
    if mask is None:
        return None
    h,w = mask.shape
    x1,y1,x2,y2 = [int(v) for v in box]
    x1,x2=max(0,min(w,x1)),max(0,min(w,x2))
    y1,y2=max(0,min(h,y1)),max(0,min(h,y2))
    return float(np.count_nonzero(mask[y1:y2,x1:x2]))/max(1,(x2-x1)*(y2-y1))


def probe_video(video, *, duration, sample_fps, max_frames):
    cap = cv2.VideoCapture(str(video))
    try:
        fps, total = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not cap.isOpened() or not math.isfinite(fps) or not math.isfinite(total) or fps <= 0 or total <= 0:
            raise ValueError("VIDEO_INVALID")
        seconds = total / fps
        if duration is not None and seconds > duration + 1e-6:
            raise ValueError("VIDEO_DURATION_LIMIT")
        rate = min(fps, sample_fps) if sample_fps is not None else fps
        sampled = int(total) if rate == fps else math.ceil(total / fps * rate - 1e-8)
        if max_frames is not None and sampled > max_frames:
            raise ValueError("VIDEO_FRAME_LIMIT")
        return {"fps": fps, "total_frames": int(total), "duration_seconds": seconds,
                "sampled_frames": sampled, "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}
    finally:
        cap.release()


def analyze_video(video, output, *, duration, sample_fps, confidence=0.25, progress=None,
                  selection=None, event=None, max_frames=None, cancelled=None, expected_models=None,
                  segment_model=None, expected_segment=None, detect_local=True):
    """Bounded sampled-frame inference; counts are observations, not unique defects."""
    if (duration is not None and duration <= 0) or (sample_fps is not None and not 0 < sample_fps <= 30) or not 0 < confidence <= 1:
        raise ValueError("Giới hạn inference không hợp lệ")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    emit = event or (lambda *args, **kwargs: None)
    emit("model_loading", "INFO", "MODEL_LOADING", "Đang tải các model đã chọn.")
    loaded, metadata = load_models(selection, expected_models) if detect_local else ([], [])
    segmenter, segment_meta = load_segmenter(segment_model, expected_segment) if segment_model else (None, None)
    emit("decode", "INFO", "VIDEO_DECODING", "Đang đọc metadata và giải mã video.")
    cap = cv2.VideoCapture(str(video))
    frames, detections = [], []
    counts = {"CRACK": 0, "POTHOLE": 0, "REPAIR": 0}
    started = time.perf_counter()
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not cap.isOpened() or fps <= 0 or total <= 0:
            raise ValueError("Không đọc được video hoặc metadata FPS")
        end = total if duration is None else min(total, int(duration * fps))
        indices = sample_indices(end, fps, sample_fps)
        if max_frames is not None and len(indices) > max_frames:
            raise ValueError("VIDEO_FRAME_LIMIT")
        emit("inference", "INFO", "INFERENCE_STARTED", "Bắt đầu nhận diện bằng model đã chọn trên tập frame lấy mẫu.")
        next_index = 0
        for index in indices:
            if cancelled and cancelled():
                raise InterruptedError("JOB_CANCELLED")
            if index != next_index and not cap.set(cv2.CAP_PROP_POS_FRAMES, index):
                raise ValueError("VIDEO_SEEK_FAILED")
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f"Không giải mã được frame {index}")
            next_index = index + 1
            mask = segment_frame(segmenter, frame) if segmenter else None
            mask_info = {'road_mask_status': 'disabled'}
            if segmenter:
                mask_info = {'road_mask_status': 'predicted_unreviewed' if mask is not None else 'missing_needs_review',
                             'road_mask': None, 'road_overlay': None, 'mask_is_ground_truth': False}
                if mask is not None:
                    mask_name = f'roadmask_{index:08d}.png'
                    mask_ok, encoded_mask = cv2.imencode('.png', mask)
                    if not mask_ok: raise OSError('Cannot encode road mask')
                    encoded_mask.tofile(str(output/mask_name))
                    overlay = frame.copy()
                    color = np.empty_like(frame); color[:] = (220,130,30)
                    overlay[mask>0] = cv2.addWeighted(frame,.65,color,.35,0)[mask>0]
                    overlay_name = f'road_overlay_{index:08d}.jpg'
                    overlay_ok, encoded_overlay = cv2.imencode('.jpg', overlay)
                    if not overlay_ok: raise OSError('Cannot encode road overlay')
                    encoded_overlay.tofile(str(output/overlay_name))
                    mask_info.update(road_mask=mask_name, road_overlay=overlay_name,
                                     road_coverage=float(np.count_nonzero(mask))/mask.size)
            annotated = frame.copy()
            for category, label, model in loaded:
                result = model.predict(frame, conf=confidence, device="cpu", verbose=False)[0]
                metadata[[m[0] for m in loaded].index(category)].setdefault("inference_ms", []).append(result.speed["inference"])
                for box in result.boxes:
                    x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                    score = float(box.conf[0])
                    model_meta = next(m for m in metadata if m["category"] == category)
                    class_id = int(box.cls[0])
                    observation_category = ("POTHOLE" if class_id == 3 else "REPAIR" if class_id == 4 else "CRACK") if category == "ROAD_DAMAGE" else category
                    record = {"category": observation_category, "class_name": model_meta["classes"][class_id], "review_status": "ai_prediction", "model": label,
                              "model_id": model_meta["id"], "model_version": model_meta["version"],
                              "local_class_id": int(box.cls[0]),
                              "confidence": round(score, 5), "frame": index, "timestamp_s": round(index/fps, 3),
                              "bbox": [x1, y1, x2, y2]}
                    if segmenter:
                        fraction = road_overlap(record['bbox'], mask)
                        record.update(road_overlap=fraction, road_warning='mask_missing_needs_review' if fraction is None else
                                      'outside_or_partial_road_mask' if fraction < .6 else 'mask_unverified',
                                      mask_is_ground_truth=False)
                    detections.append(record)
                    counts[observation_category] += 1
                    color = [(255,180,0),(0,220,255),(255,100,190),(30,140,255),(180,150,100),(80,220,100)][class_id % 6]
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(annotated, f'{record["class_name"]} {score:.2f}',
                                (x1, max(18, y1-5)), cv2.FONT_HERSHEY_SIMPLEX, .6, color, 2)
            cv2.putText(annotated, f"Frame {index} | {index/fps:.3f}s", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, .7, (255,255,255), 2)
            name = f"frame_{index:08d}.jpg"
            success, encoded = cv2.imencode(".jpg", annotated)
            if not success:
                raise OSError("Không thể mã hóa ảnh kết quả")
            encoded.tofile(str(output / name))
            original_name = f"original_{index:08d}.jpg"
            original_ok, original = cv2.imencode(".jpg", frame)
            if not original_ok:
                raise OSError("Không thể mã hóa ảnh gốc")
            original.tofile(str(output / original_name))
            frames.append({"frame": index, "timestamp_s": round(index/fps, 3), "image": name,
                           "original": original_name, **mask_info})
            if progress:
                progress(len(frames), len(indices))
            emit("inference", "INFO", "FRAME_OBSERVED", "Đã phân tích frame nguồn bằng model đã chọn.",
                 {"frame": index, "timestamp_s": round(index / fps, 3), "candidate_counts": dict(counts)})
        if not frames:
            raise ValueError("Video không có frame trong giới hạn")
    finally:
        cap.release()
    emit("aggregate", "INFO", "AGGREGATING", "Đang tổng hợp box quan sát; chưa khử trùng lặp khuyết tật.")
    report = {"models": metadata, "frames": frames, "detections": detections,
              'road_mask': {'enabled': segmenter is not None, 'model': segment_meta,
                            'policy': 'preserve_all_detections_mask_is_unverified'},
              "summary": {"sampled_frames": len(frames), "source_fps": fps,
                          "analyzed_seconds": end/fps, "confidence_threshold": confidence,
                          "counts": {c: sum(d["category"] == c for d in detections) for c in counts},
                          "runtime_seconds": round(time.perf_counter()-started, 3)},
              "limitations": "Số box trên các frame lấy mẫu, chưa khử trùng lặp; không phải số lỗi duy nhất. Chưa có GT, không kết luận accuracy/mAP, kích thước, mức độ hay GPS."}
    (output / "analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
