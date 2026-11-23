"""Discover trusted local checkpoints; class metadata, never filenames, grants a task."""
import hashlib
import os
import json
import threading
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FILES = {"CRACK": "roadguard_crack_yolo11n_v1.pt", "POTHOLE": "best (1).pt"}
FT95 = "RoadGuard_YOLO11_UAVPDD2023_FT95_v1.pt"
ROAD_WEIGHTS = ROOT / 'weights/pretrained/yolo11m-road-seg.pt'
UAV_CLASSES = ["alligator crack", "longitudinal crack", "oblique crack", "pothole", "repair", "transverse crack"]
CLASS_NAMES = {"CRACK": {"crack"}, "POTHOLE": {"pothole", "potholes"}}
_cache = {}
_lock = threading.RLock()


def model_directory():
    # Operator configuration only; clients never choose a filesystem root or path.
    cfg = json.loads((ROOT / "configs/mvp_video.json").read_text(encoding="utf-8"))
    value = Path(os.environ.get("RG_VIDEO_MODEL_DIR", cfg["model_directory"]))
    return (value if value.is_absolute() else ROOT / value).resolve()


def inspect_checkpoint(path):
    model = YOLO(str(path))
    names = model.names
    names = dict(enumerate(names)) if isinstance(names, list) else names
    names = {int(k): str(v).strip().lower() for k, v in names.items()}
    categories = [task for task, allowed in CLASS_NAMES.items()
                  if names and set(names.values()) <= allowed]
    if names == dict(enumerate(UAV_CLASSES)):
        categories = ["ROAD_DAMAGE"]
    if model.task == 'segment' and names == {0: 'road'}:
        categories = ['SEGMENT']
    elif model.task != "detect" or len(categories) != 1:
        raise ValueError("CLASS_MAPPING_UNSUPPORTED")
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return {"task": categories[0], "classes": names, "sha256": digest,
            "version": digest[:12], "runtime": "ultralytics / CPU"}


def discover_models(refresh=False):
    # Normalize both sides before comparing containment.  On Windows a
    # temporary path may be returned in 8.3 form while Path.resolve() expands
    # it; comparing the raw directory against a resolved child incorrectly
    # drops every checkpoint from the catalog.
    directory = model_directory().resolve()
    rows = []
    with _lock:
        if refresh:
            _cache.clear()
        if directory.is_dir():
            for path in sorted(directory.glob("*.pt")):
                # A symlink may not escape the trusted operator-configured root.
                if path.resolve().parent != directory:
                    continue
                stat = path.stat()
                key = (str(path), stat.st_size, stat.st_mtime_ns)
                row = {"id": hashlib.sha256(path.name.encode()).hexdigest()[:24],
                       "name": path.name, "status": "available", "task": None,
                       "classes": {}, "version": None, "code": None}
                if key not in _cache:
                    try:
                        _cache[key] = inspect_checkpoint(path)
                    except Exception as exc:
                        # Never disclose checkpoint exceptions, paths, tokens or stack traces.
                        code = "CLASS_MAPPING_UNSUPPORTED" if str(exc) == "CLASS_MAPPING_UNSUPPORTED" else "MODEL_LOAD_FAILED"
                        _cache[key] = {"status": "error", "code": code,
                                       "message": "Không tải được checkpoint hoặc class mapping không được hỗ trợ."}
                row.update(_cache[key])
                row["baseline"] = path.name not in {*DEFAULT_FILES.values(), FT95}
                rows.append(row)
        defaults = {}
        cfg = json.loads((ROOT / "configs/mvp_video.json").read_text(encoding="utf-8"))
        unified = next((r for r in rows if r["name"] == FT95 and r["task"] == "ROAD_DAMAGE" and r["status"] == "available"), None)
        for task, filename in DEFAULT_FILES.items():
            match = next((r for r in rows if r["name"] == filename and r["task"] == task
                          and r["status"] == "available"), None)
            defaults[task] = (unified["id"] if unified else None) if cfg.get("model_profile") == "ft95" else (match["id"] if match else None)
        segment = {'id': hashlib.sha256(('SEGMENT:'+ROAD_WEIGHTS.name).encode()).hexdigest()[:24],
                   'name': ROAD_WEIGHTS.name, 'task': 'SEGMENT', 'classes': {},
                   'status': 'error', 'code': 'MODEL_MISSING', 'version': None}
        if ROAD_WEIGHTS.is_file() and not ROAD_WEIGHTS.is_symlink():
            stat = ROAD_WEIGHTS.stat()
            key = (str(ROAD_WEIGHTS), stat.st_size, stat.st_mtime_ns)
            if key not in _cache:
                try:
                    metadata = inspect_checkpoint(ROAD_WEIGHTS)
                    if metadata['task'] != 'SEGMENT':
                        raise ValueError('CLASS_MAPPING_UNSUPPORTED')
                    _cache[key] = {**metadata, 'status': 'available', 'code': None}
                except Exception:
                    _cache[key] = {'status': 'error', 'code': 'CLASS_MAPPING_UNSUPPORTED'}
            cached = _cache[key]
            if cached.get('task') == 'SEGMENT':
                segment.update(cached)
                segment['status'] = cached.get('status', 'available')
            else:
                segment.update(status='error', code=cached.get('code') or 'CLASS_MAPPING_UNSUPPORTED')
        return {"models": rows, "defaults": defaults,
                'segment_models': [segment],
                'segment_default': segment['id'] if segment['status'] == 'available' else None,
                "message": "Chỉ chọn model đã xác minh task/classes; baseline phải chọn chủ động."}


def resolve_segment_model(model_id):
    catalog = discover_models()
    row = next((m for m in catalog.get('segment_models', []) if m['id'] == model_id), None)
    if not row or row['status'] != 'available' or row['task'] != 'SEGMENT' or not ROAD_WEIGHTS.is_file() or ROAD_WEIGHTS.is_symlink():
        raise ValueError('SEGMENT_MODEL_UNAVAILABLE')
    return row, ROAD_WEIGHTS


def resolve_models(selection):
    if set(selection) != set(CLASS_NAMES):
        raise ValueError("MODEL_SELECTION_REQUIRED")
    catalog = discover_models()
    resolved = []
    if selection["CRACK"] == selection["POTHOLE"]:
        row = next((r for r in catalog["models"] if r["id"] == selection["CRACK"] and r["task"] == "ROAD_DAMAGE" and r["status"] == "available"), None)
        if row:
            return [("ROAD_DAMAGE", row, model_directory() / row["name"])]
    for task, model_id in selection.items():
        row = next((r for r in catalog["models"] if r["id"] == model_id), None)
        if not row or row["task"] != task or row["status"] != "available":
            raise ValueError("MODEL_UNAVAILABLE")
        path = model_directory().resolve() / row["name"]
        if path.resolve().parent != model_directory().resolve():
            raise ValueError("MODEL_UNAVAILABLE")
        resolved.append((task, row, path))
    return resolved
