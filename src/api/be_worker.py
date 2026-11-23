"""Authenticated private worker transport; deliberately starts no inference.

Input publication uses a unique same-directory temporary file and an atomic
non-replacing rename/link. A crash between publication and the SQLite marker is
reconciled by an identical upload: verify the published bytes, then mark queued.
Never infer a verified marker merely from the presence of a filename.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException

from .be_worker_contract import ValidationError, validate_admission, validate_result
from .be_worker_store import WorkerStore, WorkerStoreError

CONTROL_LIMIT = 64 * 1024
GIB = 1024 ** 3


def _uuid(value):
    try:
        parsed = UUID(value)
        return parsed.int != 0 and str(parsed) == value
    except (ValueError, TypeError, AttributeError):
        return False


def _state(record):
    code = record["error_code"]
    if code is not None and (type(code) is not str or re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", code) is None):
        code = "INTERNAL_ERROR"
    return {"attemptId": record["attemptId"], "state": record["state"],
            "cancellationRequested": record["cancellation_requested"], "errorCode": code}


def _safe_path(root, *parts):
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink() or path.is_junction():
            raise WorkerStoreError("UNSAFE_STORAGE", 422)
    if not path.resolve().is_relative_to(root):
        raise WorkerStoreError("UNSAFE_STORAGE", 422)
    return path


def _verify_file(path, expected):
    if path.is_symlink() or path.is_junction() or not path.is_file():
        raise WorkerStoreError("ARTIFACT_NOT_FOUND", 404)
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            count += len(chunk)
            if count > expected["bytes"]:
                raise WorkerStoreError("INPUT_CHECKSUM_MISMATCH", 422)
            digest.update(chunk)
    if count != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
        raise WorkerStoreError("INPUT_CHECKSUM_MISMATCH", 422)


def _publish(temporary, final):
    if os.name == "nt":
        # Windows has no portable directory fsync. MOVEFILE_WRITE_THROUGH waits
        # for durable movement; omitting REPLACE_EXISTING preserves the winner.
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        move = kernel.MoveFileExW
        move.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD)
        move.restype = wintypes.BOOL
        if not move(str(temporary), str(final), 0x8):
            error = ctypes.get_last_error()
            if error in (80, 183):
                raise FileExistsError()
            raise ctypes.WinError(error)
    else:
        os.link(temporary, final)
        directory_fd = os.open(final.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)


def check_capacity(root, payload, store):
    """Independent local 40 GiB budget and 30 GiB free floor, plus reserve."""
    used = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            child = Path(directory) / name
            if child.is_symlink() or child.is_junction():
                raise WorkerStoreError("UNSAFE_STORAGE", 422)
        used += sum((Path(directory) / name).stat().st_size for name in files)
    reserved = store.active_reservation_bytes() + 2 * GIB
    if used + reserved > 40 * GIB or shutil.disk_usage(root).free - reserved < 30 * GIB:
        raise WorkerStoreError("DISK_BUDGET_EXCEEDED", 507)


async def _control_json(request, *, empty=False):
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > CONTROL_LIMIT:
            raise WorkerStoreError("INVALID_INPUT", 422)
        body.extend(chunk)
    if empty and not body:
        return {}
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate")
            result[key] = value
        return result
    def constant(value):
        raise ValueError("nonfinite")
    try:
        result = json.loads(body, object_pairs_hook=pairs, parse_constant=constant)
        if type(result) is not dict:
            raise ValueError("object required")
        return result
    except (ValueError, UnicodeError, RecursionError):
        raise WorkerStoreError("INVALID_INPUT", 422) from None


def create_app(data_root, token, store=None):
    """Factory for a trusted operator-owned directory and mounted secret."""
    try:
        secret = token.encode("ascii") if type(token) is str else b""
    except UnicodeError:
        secret = b""
    if len(secret) < 32 or any(byte <= 32 or byte >= 127 for byte in secret):
        raise ValueError("A service token of at least 32 printable ASCII bytes is required")
    root = Path(data_root).absolute()
    if root.is_symlink() or root.is_junction():
        raise ValueError("A trusted storage directory is required")
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.data_root = root
    app.state.store = store if store is not None else WorkerStore(root / "worker.sqlite3")
    app.state.capacity_checker = check_capacity
    app.state.readiness_checker = lambda: True

    @app.middleware("http")
    async def authenticate(request, call_next):
        auth = request.headers.getlist("authorization")
        supplied = auth[0].encode("utf-8") if len(auth) == 1 else b""
        if not hmac.compare_digest(supplied, b"Bearer " + secret):
            return JSONResponse({"code": "UNAUTHORIZED"}, status_code=401)
        try:
            return await call_next(request)
        except Exception:
            # Neither caller data, local paths nor raw exceptions enter logs/wire.
            return JSONResponse({"code": "INTERNAL_ERROR"}, status_code=500)

    @app.exception_handler(WorkerStoreError)
    async def store_error(request, exc):
        code = exc.code if type(exc.code) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", exc.code) else "INTERNAL_ERROR"
        return JSONResponse({"code": code}, status_code=exc.status_code)

    @app.exception_handler(ValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"code": "INVALID_INPUT"}, status_code=422)

    @app.exception_handler(HTTPException)
    async def framework_error(request, exc):
        codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        return JSONResponse({"code": codes.get(exc.status_code, "INVALID_INPUT")}, status_code=exc.status_code)

    def record(attempt_id):
        if not _uuid(attempt_id):
            raise WorkerStoreError("ATTEMPT_NOT_FOUND", 404)
        app.state.store.expire_awaiting_input()
        found = app.state.store.get(attempt_id)
        if found is None:
            raise WorkerStoreError("ATTEMPT_NOT_FOUND", 404)
        return found

    @app.get("/internal/v1/health")
    async def health():
        if not app.state.readiness_checker():
            return JSONResponse({"code": "WORKER_NOT_READY"}, status_code=503)
        return {"status": "ok"}

    @app.post("/internal/v1/jobs")
    async def admit(request: Request):
        payload = validate_admission(await _control_json(request))
        found, replay = app.state.store.admit(payload)
        return JSONResponse(_state(found), status_code=200 if replay else 202)

    @app.get("/internal/v1/jobs/{attempt_id}")
    async def get_state(attempt_id: str):
        return _state(record(attempt_id))

    @app.post("/internal/v1/jobs/{attempt_id}/cancel")
    async def cancel(attempt_id: str, request: Request):
        record(attempt_id)
        if await _control_json(request, empty=True):
            raise WorkerStoreError("INVALID_INPUT", 422)
        return _state(app.state.store.request_cancel(attempt_id))

    @app.put("/internal/v1/jobs/{attempt_id}/input")
    async def upload(attempt_id: str, request: Request):
        found = record(attempt_id)
        payload = found["payload"]
        lengths = request.headers.getlist("content-length")
        hashes = request.headers.getlist("x-content-sha256")
        if (lengths != [str(payload["inputBytes"])] or hashes != [payload["inputSha256"]]):
            raise WorkerStoreError("INPUT_CHECKSUM_MISMATCH", 422)
        if found["input_marker"] is None and found["state"] != "AWAITING_INPUT":
            raise WorkerStoreError("INVALID_STATE", 409)
        app.state.capacity_checker(root, payload, app.state.store)
        directory = _safe_path(root, attempt_id)
        directory.mkdir(exist_ok=True)
        final = _safe_path(root, attempt_id, "input.mp4")
        fd, temporary = tempfile.mkstemp(prefix=".upload-", dir=directory)
        temporary = Path(temporary)
        try:
            digest = hashlib.sha256()
            count = 0
            with os.fdopen(fd, "wb") as stream:
                async for chunk in request.stream():
                    count += len(chunk)
                    if count > payload["inputBytes"]:
                        raise WorkerStoreError("INPUT_CHECKSUM_MISMATCH", 422)
                    digest.update(chunk)
                    stream.write(chunk)
                if count != payload["inputBytes"] or digest.hexdigest() != payload["inputSha256"]:
                    raise WorkerStoreError("INPUT_CHECKSUM_MISMATCH", 422)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                _publish(temporary, final)
            except FileExistsError:
                _verify_file(final, {"bytes": payload["inputBytes"], "sha256": payload["inputSha256"]})
            verified = app.state.store.mark_input_verified(attempt_id, str(final))
            return _state(verified)
        finally:
            temporary.unlink(missing_ok=True)

    def completed(attempt_id):
        found = record(attempt_id)
        result = app.state.store.get_result(attempt_id)
        return validate_result(result, found["payload"])

    @app.get("/internal/v1/jobs/{attempt_id}/result")
    async def get_result(attempt_id: str):
        return completed(attempt_id)

    @app.get("/internal/v1/jobs/{attempt_id}/artifacts/{artifact_id}")
    async def get_artifact(attempt_id: str, artifact_id: str):
        if not _uuid(artifact_id):
            raise WorkerStoreError("ARTIFACT_NOT_FOUND", 404)
        result = completed(attempt_id)
        artifacts = [result["rawArtifact"], *result["frameArtifacts"]]
        if result["telemetry"]["srtArtifact"] is not None:
            artifacts.append(result["telemetry"]["srtArtifact"])
        metadata = next((item for item in artifacts if item["artifactId"] == artifact_id), None)
        if metadata is None:
            raise WorkerStoreError("ARTIFACT_NOT_FOUND", 404)
        path = _safe_path(root, attempt_id, "artifacts", artifact_id)
        _verify_file(path, metadata)
        return FileResponse(path, media_type=metadata["mediaType"], filename=artifact_id)

    return app
