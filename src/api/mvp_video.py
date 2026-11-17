"""Existing RoadGuard video MVP: loopback-only, durable local jobs and model selection."""
import hashlib
import json
import math
import os
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from filelock import FileLock, Timeout

from fastapi import Body, APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from src.api import video_job_store as store
from src.inference.mvp_video import ROOT, analyze_video, probe_video
from src.inference.video_models import discover_models, resolve_models, resolve_segment_model

RUNS = ROOT / "results/mvp_video28"
WEB = ROOT / "src/api/web"
JOBS = {}
LOCK = threading.Lock()
ADMISSION = threading.RLock()
REPORT_LOCK = threading.Lock()
WORKER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="roadguard-local")
ACTIVE = set()
SERVICE_LEASES = {}
LIMITS = "configured"  # None still fails closed for callers/tests using the old config gate.
REPORT_ENABLED = os.environ.get("RG_VIDEO_REPORT_ENABLED") == "1"


def settings():
    value = json.loads((ROOT / "configs/mvp_video.json").read_text(encoding="utf-8"))
    for key in ("sample_fps", "max_concurrent_jobs", "max_queued_jobs", "minimum_free_disk_mb"):
        if not isinstance(value.get(key), (int, float)) or not math.isfinite(value[key]) or value[key] <= 0:
            raise ValueError("CONFIG_INVALID")
    if value["max_concurrent_jobs"] != 1 or value["mode"] != "local" or value["bind_host"] != "127.0.0.1":
        raise ValueError("PUBLIC_RELEASE_BLOCKED")
    if value["sample_fps"] not in {1, 2, 5, 10} or not isinstance(value["max_queued_jobs"], int):
        raise ValueError("CONFIG_INVALID")
    return value


def fail(status, code, message, stage="validation", action="Kiểm tra thông tin và thử lại."):
    raise HTTPException(status, {"code": code, "message": message, "stage": stage, "action": action})


def local_only(request: Request):
    if not request.client or request.client.host not in {"127.0.0.1", "::1", "testclient"}:
        fail(403, "LOCAL_ONLY", "Chỉ cho phép truy cập trên máy local.", "permission")
    host = request.url.hostname
    if host not in {"127.0.0.1", "localhost", "::1", "testserver"}:
        fail(403, "LOCAL_ONLY", "Tên máy truy cập không được phép.", "permission")
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        fail(403, "ORIGIN_DENIED", "Yêu cầu khác nguồn không được phép.", "permission")
    if request.client.host != "testclient":
        # Prevent two UI entrypoints/processes from running inference or recovering
        # each other's active jobs against the same local result directory.
        with ADMISSION:
            key = str(RUNS.resolve())
            if key not in SERVICE_LEASES:
                RUNS.mkdir(parents=True, exist_ok=True)
                lease = FileLock(str(RUNS / ".service.lock"), thread_local=False)
                try:
                    lease.acquire(timeout=0)
                except Timeout:
                    fail(503, "LOCAL_SERVICE_IN_USE", "Một dịch vụ local khác đang dùng thư mục kết quả. Dùng cửa sổ dịch vụ hiện có.", "configuration")
                SERVICE_LEASES[key] = lease


router = APIRouter(prefix="/api/mvp-video", dependencies=[Depends(local_only)])


def recover():
    RUNS.mkdir(parents=True, exist_ok=True)
    for path in RUNS.glob("*/job.json"):
        try:
            job = store.read(RUNS, path.parent.name)
            if job["job_id"] not in JOBS:
                if job["status"] not in store.TERMINAL | {"READY"}:
                    job.update(status="INTERRUPTED", progress=None,
                               error={"code": "JOB_INTERRUPTED", "stage": "recovery",
                                      "message": "Phiên trước bị gián đoạn. Kết quả đã ghi được giữ lại; không tự chạy lại."})
                    store.save(RUNS, job)
                    store.append(RUNS, job, "recovery", "WARNING", "JOB_INTERRUPTED", job["error"]["message"])
                    # Only this interrupted job's own incomplete upload is temporary.
                    (path.parent / "upload.part").unlink(missing_ok=True)
                JOBS[job["job_id"]] = job
        except (OSError, ValueError, KeyError):
            continue


def get_job(job_id):
    recover()
    job = JOBS.get(job_id)
    if not job:
        fail(404, "JOB_NOT_FOUND", "Không tìm thấy phiên phân tích.", "history")
    return job


def event(job, stage, severity, code, message, details=None):
    if code == "FRAME_OBSERVED" and details:
        job.update(current_frame=details["frame"], timestamp_s=details["timestamp_s"],
                   candidate_counts=details["candidate_counts"])
    return store.append(RUNS, job, stage, severity, code, message, details)


def rate(value):
    if str(value) == "native":
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        value = 0
    if value not in {1, 2, 5, 10}:
        fail(422, "FPS_INVALID", "Chọn FPS 1, 2, 5, 10 hoặc native.")
    return value


def disk_check(required=0):
    RUNS.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(RUNS).free
    if free < required + settings()["minimum_free_disk_mb"] * 1048576:
        fail(507, "DISK_SPACE_LOW", "Không đủ dung lượng ổ đĩa cho video và ảnh kết quả.",
             "storage", "Giải phóng dung lượng hoặc chọn FPS thấp hơn rồi thử lại.")
    return free


def resource_usage():
    import psutil
    import torch
    return {"ram_mb": round(psutil.Process().memory_info().rss / 1048576, 2),
            "vram_mb": round(torch.cuda.memory_allocated() / 1048576, 2) if torch.cuda.is_available() else 0,
            "device": "CPU"}


def execute(job_id, source, limits):
    job = JOBS[job_id]
    with LOCK:
        ACTIVE.add(job_id)
        started = time.perf_counter()
        peak = {"ram_mb": 0, "vram_mb": 0, "device": "CPU"}
        stop = threading.Event()
        def monitor():
            while not stop.is_set():
                usage = resource_usage()
                for key in ("ram_mb", "vram_mb"):
                    peak[key] = max(peak[key], usage[key])
                stop.wait(.2)
        watcher = threading.Thread(target=monitor, daemon=True)
        watcher.start()
        try:
            if job.get("cancel_requested"):
                raise InterruptedError()
            job.update(status="RUNNING", message="Đang xử lý local", progress=None)
            event(job, "model_loading", "INFO", "JOB_STARTED", "Bắt đầu xử lý local bằng model đã chọn.")
            def progress(done, total):
                if job.get("cancel_requested"):
                    raise InterruptedError()
                disk_check()
                job.update(processed_frames=done, total_frames=total,
                           progress=round(100 * done / total, 2) if total else None,
                           message=f"Đã xử lý {done}/{total} frame")
                event(job, "inference", "INFO", "FRAME_PROCESSED", job["message"],
                      {"processed_frames": done, "total_frames": total})
            segment = job.get('segment', {})
            segment_args = {'segment_model': segment['model']['id'], 'expected_segment': segment['model']} if segment.get('enabled') else {}
            if job.get('detection_mode') == 'Vision':
                segment_args['detect_local'] = False
            result = analyze_video(source, RUNS / job_id, duration=limits.get("seconds"),
                                   sample_fps=job.get("sample_fps", limits.get("fps", 2)),
                                   max_frames=limits.get("max_frames"), selection=job.get("selection"),
                                   expected_models=job.get("models"),
                                   progress=progress, cancelled=lambda: job.get("cancel_requested", False),
                                   event=lambda *args: event(job, *args), **segment_args)
            if job.get("cancel_requested"):
                raise InterruptedError()
            job.update(status="COMPLETED", result=result, progress=100,
                       completed_at=store.now(), message="Kết quả đã lưu local")
            event(job, "review", "INFO", "JOB_COMPLETED", "Đã lưu kết quả; cần con người rà soát candidate.")
            local_report(job)
        except InterruptedError:
            job.update(status="CANCELLED", progress=None, message="Đã hủy; giữ kết quả đã lưu.")
            event(job, "cancel", "WARNING", "JOB_CANCELLED", job["message"])
        except Exception as exc:
            known = str(exc) if str(exc) in {"MODEL_CHANGED", "MODEL_UNAVAILABLE", "VIDEO_FRAME_LIMIT"} else (
                "MODEL_MISSING" if isinstance(exc, FileNotFoundError) else
                "MODEL_LOAD_FAILED" if job.get("stage") == "model_loading" else "PROCESSING_FAILED")
            if isinstance(exc, HTTPException) and isinstance(exc.detail, dict):
                known = exc.detail["code"]
            job.update(status="FAILED", error={"code": known, "stage": job.get("stage", "inference"),
                       "message": "Phân tích thất bại. Kiểm tra dung lượng, video và trạng thái model; kết quả đã ghi được giữ lại.",
                       "action": "Mở nhật ký và kiểm tra nguyên nhân trước khi tạo phiên mới."})
            event(job, job.get("stage", "inference"), "ERROR", known, job["error"]["message"])
        finally:
            stop.set()
            watcher.join(timeout=1)
            job["resources"] = peak
            job["resources"]["wall_seconds"] = round(time.perf_counter() - started, 3)
            if job.get("processed_frames"):
                job["resources"]["sampled_fps_actual"] = round(job["processed_frames"] / max(time.perf_counter() - started, .001), 3)
            store.save(RUNS, job)
            (RUNS / job_id / "upload.part").unlink(missing_ok=True)
            ACTIVE.discard(job_id)


@router.get("/config")
def config():
    try:
        cfg = settings()
        catalog = discover_models()
        disk_check()
    except (ValueError, OSError):
        fail(503, "CONFIG_INVALID", "Không đọc được cấu hình local hợp lệ.", "configuration")
    ready = LIMITS is not None
    return {"mode": "local", "limits": {"bytes": None, "seconds": None, "fps": cfg["sample_fps"],
            "max_frames": None, "concurrent": 1, "queued": cfg["max_queued_jobs"]},
            "public_release_enabled": False,
            "ready": ready, "report_enabled": REPORT_ENABLED, "models": catalog["models"],
            "defaults": catalog["defaults"], "fps_options": [1, 2, 5, 10, "native"],
            'segment_models': catalog.get('segment_models', []), 'segment_default': catalog.get('segment_default'),
            "message": "Xử lý local • Không áp giới hạn public • Chỉ một job chạy đồng thời"}


@router.get("/models")
def models(refresh: bool = False):
    return discover_models(refresh)


@router.get("/jobs")
def history():
    recover()
    return {"jobs": sorted(({k: v for k, v in j.items() if k not in {"result", "idempotency_key", "source_sha256"}}
                             for j in JOBS.values()), key=lambda j: j.get("created_at", ""), reverse=True)}


def segment_identity(selection):
    selection = selection or {}
    model = selection.get('model') or {}
    return (bool(selection.get('enabled')), model.get('id'), model.get('sha256'))


@router.post("/upload")
async def upload(bg: BackgroundTasks, file: UploadFile = File(...), crack_model: str = Form(""),
                 pothole_model: str = Form(""), sample_fps: str = Form(""),
                 road_mask_enabled: bool = Form(False), segment_model: str = Form(''),
                 prepare_only: bool = Form(False), detection_mode: str = Form(""),
                 idempotency_key: str = Header(default="", alias="Idempotency-Key")):
    try:
        cfg = settings()
    except (ValueError, OSError):
        fail(503, "CONFIG_INVALID", "Cấu hình local không hợp lệ. Kiểm tra cấu hình máy chủ trước khi tải video.", "configuration")
    if LIMITS is None:
        fail(503, "CONFIG_INVALID", "Cấu hình xử lý chưa sẵn sàng.", "configuration")
    fps = rate(sample_fps or cfg["sample_fps"])
    if Path(file.filename or "").suffix.lower() not in {".mp4", ".mov", ".avi", ".mkv"}:
        fail(415, "UNSUPPORTED_FILE", "Định dạng video không hỗ trợ. Chọn MP4, MOV, AVI hoặc MKV.")
    catalog = discover_models()
    selection = {"CRACK": crack_model or catalog["defaults"]["CRACK"],
                 "POTHOLE": pothole_model or catalog["defaults"]["POTHOLE"]}
    if detection_mode not in {"", "FT95", "Vision", "FT95 + Vision"}:
        fail(422, "INVALID_DETECTION_MODE", "Chế độ nhận diện không hợp lệ.")
    try:
        if detection_mode == "Vision":
            selection = {}
            resolved = []
        elif detection_mode:
            ft95 = next((row for row in catalog["models"] if row["task"] == "ROAD_DAMAGE"
                         and row["name"] == "RoadGuard_YOLO11_UAVPDD2023_FT95_v1.pt"
                         and row["status"] == "available"), None)
            if not ft95:
                raise ValueError("FT95 unavailable")
            selection = dict.fromkeys(("CRACK", "POTHOLE"), ft95["id"])
            resolved = resolve_models(selection)
        else:
            resolved = resolve_models(selection)
        segment = {'enabled': bool(road_mask_enabled), 'model': None}
        if road_mask_enabled:
            row, _ = resolve_segment_model(segment_model or catalog.get('segment_default'))
            segment['model'] = row
    except ValueError:
        fail(422, "MODEL_UNAVAILABLE", "Model đã chọn thiếu, hỏng hoặc sai task; không tự dùng model khác.", "model_loading")
    recover()
    with ADMISSION:
        old = next((j for j in JOBS.values() if idempotency_key and j.get("idempotency_key") == idempotency_key), None)
        if old and old["status"] == "UPLOADING":
            fail(409, "UPLOAD_IN_PROGRESS", "Upload trước vẫn đang xử lý. Đọc lại trạng thái, không tạo lệnh mới.", "upload")
        if not old and not prepare_only and sum(j.get("status") not in store.TERMINAL | {"READY"} for j in JOBS.values()) >= 1 + cfg["max_queued_jobs"]:
            fail(429, "QUEUE_FULL", "Đang có một job chạy và ba chỗ chờ đã được đặt. Thử lại sau.", "queue")
        job_id = old["job_id"] if old else uuid.uuid4().hex
        folder = store.directory(RUNS, job_id)
        if not old:
            folder.mkdir(parents=True, exist_ok=False)
            job = {"job_id": job_id, "created_at": store.now(), "status": "UPLOADING", "progress": None,
                   "selection": selection, "models": [r for _, r, _ in resolved], "sample_fps": fps,
                   'segment': segment, 'detection_mode': detection_mode,
                   "source_name": Path(file.filename or "video").name, "idempotency_key": idempotency_key,
                   "mode": "local", "sequence": 0, "cancel_requested": False}
            JOBS[job_id] = job
            store.save(RUNS, job)
    source = folder / "source.video"
    temp = folder / "upload.part"
    digest = hashlib.sha256()
    size = 0
    try:
        handle = None if old else temp.open("wb")
        try:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                digest.update(chunk)
                if not old:
                    if job.get("cancel_requested"):
                        raise InterruptedError()
                    disk_check(len(chunk))
                    handle.write(chunk)
        finally:
            if handle:
                handle.close()
        if old:
            if (digest.hexdigest() != old.get("source_sha256") or selection != old["selection"] or fps != old["sample_fps"]
                or segment_identity(segment) != segment_identity(old.get('segment'))
                or detection_mode != old.get('detection_mode', '')):
                fail(409, "IDEMPOTENCY_CONFLICT", "Khóa yêu cầu đã dùng với video hoặc model/FPS khác.", "upload")
            return {"job_id": job_id, "replayed": True}
        if not size:
            fail(422, "VIDEO_EMPTY", "Video không có dữ liệu.")
        try:
            metadata = probe_video(temp, duration=None, sample_fps=fps, max_frames=None)
        except ValueError as exc:
            fail(422, str(exc), "Không đọc được metadata video. Kiểm tra định dạng hoặc tệp bị hỏng.", "decode")
        # Conservative upper estimate: two uncompressed RGB frames per sample + reserve.
        required = metadata["sampled_frames"] * metadata["width"] * metadata["height"] * 6
        disk_check(required)
        temp.replace(source)
        job.update(source_sha256=digest.hexdigest(), source_bytes=size, video=metadata,
                   status="READY" if prepare_only else "QUEUED")
        event(job, "validation" if prepare_only else "queue", "INFO", "VIDEO_READY" if prepare_only else "JOB_QUEUED",
              "Đã xác minh video; xem số frame trước khi bắt đầu." if prepare_only else "Đang chờ lượt xử lý.",
              {"estimated_frames": metadata["sampled_frames"], "source_bytes": size})
        # One executor is shared by all requests. No second inference worker is created.
        if not prepare_only:
            bg.add_task(WORKER.submit, execute, job_id, source, {"seconds": None, "fps": fps, "max_frames": None})
    except Exception as exc:
        if not old:
            temp.unlink(missing_ok=True)
            if isinstance(exc, InterruptedError):
                job.update(status="CANCELLED")
                event(job, "upload", "WARNING", "JOB_CANCELLED", "Đã hủy upload và dọn tệp tạm.")
            else:
                detail = exc.detail if isinstance(exc, HTTPException) and isinstance(exc.detail, dict) else {
                    "code": "UPLOAD_FAILED", "stage": "upload", "message": "Không lưu được video local."}
                job.update(status="FAILED", error=detail)
                event(job, detail["stage"], "ERROR", detail["code"], detail["message"])
        if isinstance(exc, (HTTPException, InterruptedError)):
            if isinstance(exc, InterruptedError):
                fail(409, "JOB_CANCELLED", "Upload đã được hủy.", "upload")
            raise
        fail(500, "UPLOAD_FAILED", "Không lưu được video. Kiểm tra dung lượng ổ đĩa.", "upload")
    finally:
        await file.close()
    return {"job_id": job_id}


@router.post("/{job_id}/start")
def start_prepared(job_id: str, bg: BackgroundTasks):
    job = get_job(job_id)
    with ADMISSION:
        if job["status"] != "READY":
            return {"job_id": job_id, "status": job["status"], "replayed": True}
        if sum(j.get("status") not in store.TERMINAL | {"READY"} for j in JOBS.values()) >= 1 + settings()["max_queued_jobs"]:
            fail(429, "QUEUE_FULL", "Một job chạy và ba chỗ chờ đã được đặt. Thử lại sau.", "queue")
        video = job["video"]
        disk_check(video["sampled_frames"] * video["width"] * video["height"] * 6)
        job["status"] = "QUEUED"
        event(job, "queue", "INFO", "JOB_QUEUED", "Đã xếp hàng sau khi người dùng kiểm tra số frame.")
        bg.add_task(WORKER.submit, execute, job_id, RUNS / job_id / "source.video",
                    {"seconds": None, "fps": job["sample_fps"], "max_frames": None})
    return {"job_id": job_id, "status": "QUEUED"}


@router.get("/ui.js")
def script():
    return FileResponse(WEB / "mvp_video.js", media_type="text/javascript")


@router.get("/ui.css")
def stylesheet():
    return FileResponse(WEB / "mvp_video.css", media_type="text/css")


@router.get("/brand")
def brand():
    return FileResponse(WEB / "roadguard-logo.png", media_type="image/png")


@router.get("/{job_id}")
def status(job_id: str):
    return {k: v for k, v in get_job(job_id).items() if k not in {"idempotency_key", "source_sha256"}}


@router.get("/{job_id}/logs")
def logs(job_id: str, after: int = 0):
    get_job(job_id)
    return {"events": store.events(RUNS, job_id, max(0, after)), "connection": "connected"}


@router.post("/{job_id}/cancel")
def cancel(job_id: str):
    job = get_job(job_id)
    if job["status"] not in store.TERMINAL:
        job["cancel_requested"] = True
        pending = job["status"] in {"READY", "QUEUED"}
        if pending:
            job["status"] = "CANCELLED"
        event(job, "cancel", "WARNING", "CANCEL_REQUESTED",
              "Đã hủy phiên chưa chạy; dữ liệu đã lưu được giữ lại." if pending else "Đã yêu cầu hủy; chờ frame hiện tại hoàn tất.")
    return {"job_id": job_id, "status": job["status"], "cancel_requested": job.get("cancel_requested", False)}


@router.get("/{job_id}/files/{name}")
def artifact(job_id: str, name: str):
    job = get_job(job_id)
    allowed = {"analysis.json", "report_vi.txt", "report_local.html", "report_local.json"}
    for frame in job.get("result", {}).get("frames", []):
        allowed.update(frame[k] for k in ("image", "original", 'road_mask', 'road_overlay') if frame.get(k))
    try:
        path = store.directory(RUNS, job_id) / name
    except ValueError:
        fail(404, "FILE_NOT_FOUND", "Không tìm thấy tệp.")
    if name in {"report_local.html", "report_local.json"} and job.get("status") == "COMPLETED":
        local_report(job)
    if name not in allowed or path.name != name or not path.is_file() or path.is_symlink():
        fail(404, "FILE_NOT_FOUND", "Không tìm thấy tệp.")
    return FileResponse(path)


def local_report(job):
    from src.api.local_video_report import write
    return write(job, store.directory(RUNS, job["job_id"]))


@router.post("/{job_id}/report/local")
def statistics(job_id: str):
    job = get_job(job_id)
    if job["status"] != "COMPLETED":
        fail(409, "JOB_NOT_COMPLETE", "Chưa có kết quả hoàn tất để lập báo cáo.", "report")
    return local_report(job)


@router.post("/{job_id}/report")
def report(job_id: str, body: dict | None = Body(None)):
    job = get_job(job_id)
    if not REPORT_ENABLED:
        fail(503, "REPORT_PROVIDER_UNAVAILABLE", "Chưa bật provider báo cáo. Báo cáo thống kê local vẫn sử dụng được.", "report")
    if job["status"] != "COMPLETED":
        fail(409, "JOB_NOT_COMPLETE", "Video chưa phân tích thành công.", "report")
    if (body or {}).get("confirm_paid") is not True:
        fail(409, "REPORT_CONSENT_REQUIRED", "Cần xác nhận trước khi gửi dữ liệu báo cáo.", "report")
    from src.curation.kdv_inspector import KDVInspector
    inspector = KDVInspector(timeout=60, max_retries=0)
    if not inspector.is_available or not os.environ.get("KDV_MODEL") or not os.environ.get("KDV_BASE_URL"):
        fail(503, "REPORT_PROVIDER_UNAVAILABLE", "Thiếu cấu hình provider/model/API key trên máy chủ.", "report")
    if not inspector.model.lower().startswith(("qwen", "deepseek")):
        fail(503, "REPORT_PROVIDER_UNAVAILABLE", "Local MVP chỉ mở diễn giải khi cấu hình model Qwen hoặc DeepSeek.", "report")
    if not REPORT_LOCK.acquire(blocking=False):
        fail(409, "REPORT_IN_PROGRESS", "Một yêu cầu báo cáo đang chạy. Không gửi lại.", "report")
    try:
        if job.get("llm_report"):
            return job["llm_report"]
        result = job["result"]
        payload = {"summary": result["summary"], "models": [m["label"] for m in result["models"]],
                   "limitations": result["limitations"]}
        event(job, "report", "INFO", "REPORT_REQUESTED", "Người dùng yêu cầu diễn giải LLM; chỉ gửi thống kê.")
        response = inspector._client.with_options(max_retries=0).chat.completions.create(
            model=inspector.model,
            messages=[{"role": "system", "content": "Viết báo cáo kỹ thuật tiếng Việt từ dữ liệu. Tách đầu ra model và quyết định con người. Không bịa accuracy/mAP, severity, số đo vật lý, GPS, số lỗi duy nhất hoặc kết luận kiểm định. Nêu hạn chế và đề nghị kiểm tra thực địa."},
                      {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}], max_tokens=1200)
        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise ValueError()
        (RUNS / job_id / "report_vi.txt").write_text(content, encoding="utf-8")
        job["llm_report"] = {"text": content, "model": inspector.model,
                             "provider": "Qwen" if inspector.model.lower().startswith("qwen") else "DeepSeek",
                             "generated_at": store.now()}
        event(job, "report", "INFO", "REPORT_COMPLETED", "Đã lưu bản diễn giải LLM và provenance.")
        return job["llm_report"]
    except Exception:
        event(job, "report", "ERROR", "REPORT_PROVIDER_FAILED", "Provider chưa trả báo cáo; không tự gửi lại.")
        fail(502, "REPORT_PROVIDER_FAILED", "Provider chưa tạo được báo cáo; kiểm tra cấu hình/kết nối.", "report")
    finally:
        REPORT_LOCK.release()



@router.post("/{job_id}/review")
def review_detection(job_id: str, body: dict = Body(...)):
    with ADMISSION:
        job = get_job(job_id)
        if (store.directory(RUNS, job_id)/'review/source.json').exists():
            fail(409, 'USE_REVIEW_QUEUE', 'Mở Review Queue để lưu revision theo phiên xử lý.', 'review')
        index = body.get("detection_index")
        state = body.get("status")
        detections = job.get("result", {}).get("detections", [])
        if job["status"] != "COMPLETED" or type(index) is not int or not 0 <= index < len(detections) or state not in {"pending_review", "approved"}:
            fail(422, "REVIEW_INVALID", "Box hoặc trạng thái review không hợp lệ.", "review")
        reviews = job.setdefault("reviews", {})
        previous = reviews.get(str(index), {})
        if previous.get("status") == "approved":
            fail(409, "REVIEW_APPROVED_LOCKED", "Box đã duyệt được giữ nguyên; không ghi đè revision.", "review")
        import uuid
        revision = {"id": uuid.uuid4().hex, "detection_index": index, "status": state, "timestamp": store.now(), "previous_revision": previous.get("id")}
        path = store.directory(RUNS, job_id) / ("review_" + revision["id"] + ".json")
        with path.open("x", encoding="utf-8") as handle:
            json.dump(revision, handle, ensure_ascii=False)
        reviews[str(index)] = revision
        event(job, "review", "INFO", "REVIEW_SAVED", "Đã lưu revision review riêng; prediction gốc được giữ nguyên.", revision)
        store.save(RUNS, job)
        return revision


from src.api.video_review import install_review_routes
install_review_routes(router, get_job, lambda: RUNS, ADMISSION)
from src.api.ckey_routes import install as install_ckey_routes
install_ckey_routes(router, get_job, lambda: RUNS, REPORT_LOCK)

if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    app = FastAPI(title="RoadGuard AI Local")
    app.include_router(router)
    @app.get("/", response_class=HTMLResponse, dependencies=[Depends(local_only)])
    def page():
        return (WEB / "mvp_video.html").read_text(encoding="utf-8")
    settings()  # Public mode is deliberately blocked until its release gates exist.
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("RG_VIDEO_PORT", "8788")))
