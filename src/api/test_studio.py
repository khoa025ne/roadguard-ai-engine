"""Opt-in, loopback-only UI over the real private worker. No production defaults."""
import asyncio
from contextlib import asynccontextmanager, contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.parse import unquote, urlsplit
from uuid import uuid4
import re

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException

from .be_worker import _safe_path, _verify_file, check_capacity, GIB
from .be_worker_contract import SOURCE_CLASSES
from .be_worker_runner import FT95_SHA256, PREPROCESSING_VERSION, CONFIG_VERSION, FFmpegMedia, RunnerError
from .be_worker_store import WorkerStoreError

MAX_UPLOAD = 2 * GIB
WEB = Path(__file__).parent / 'web' / 'test_studio'
LOCAL = {'127.0.0.1', 'localhost', '::1'}


def _backend_url(value):
    if value is None:
        return None
    parsed = urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or parsed.hostname not in LOCAL or
            parsed.username or parsed.password or parsed.path not in ('', '/') or
            parsed.query or parsed.fragment or not parsed.port or parsed.port == 8765):
        raise ValueError('STUDIO_BE_URL_MUST_BE_LOCAL_ORIGIN')
    return value.rstrip('/')


def _be_allowed(method, path):
    # Deliberately no /internal, login, callbacks, arbitrary URL/path escaping.
    if type(path) is not str or len(path) > 2048 or re.search(r'[^A-Za-z0-9/_.?=&%,-]', path):
        return False
    if '%' in path or '..' in path or '//' in path:
        return False
    base = path.split('?', 1)[0]
    identity = r'[0-9a-fA-F-]{36}'
    read = [r'/api/v1/projects', rf'/api/v1/projects/{identity}',
            rf'/api/v1/projects/{identity}/ai-videos(?:/{identity}/telemetry)?',
            r'/api/v1/me/survey-tasks', rf'/api/v1/survey-tasks/{identity}(?:/datasets|/eligible-drones)?',
            rf'/api/v1/datasets/{identity}(?:/coverage)?', rf'/api/v1/processing-jobs/{identity}',
            rf'/api/v1/uploads/{identity}', rf'/api/v1/files/{identity}',
            rf'/api/v1/projects/{identity}/candidates',
            rf'/api/v1/projects/{identity}/ai-candidates/{identity}',
            rf'/api/v1/projects/{identity}/defects/{identity}',
            rf'/api/v1/projects/{identity}/field-inspection-tasks(?:/{identity}(?:/(?:history|start-origin|geometry|submissions/{identity}))?)?',
            rf'/api/v1/projects/{identity}/candidate-decisions/{identity}']
    write = [r'/api/v1/uploads', rf'/api/v1/uploads/{identity}/(?:part-urls|complete|cancel)',
             rf'/api/v1/survey-tasks/{identity}/datasets', r'/api/v1/processing-jobs',
             rf'/api/v1/processing-jobs/{identity}/retry',
             rf'/api/v1/projects/{identity}/ai-videos/{identity}/telemetry-revisions',
             rf'/api/v1/projects/{identity}/candidate-decisions',
             rf'/api/v1/projects/{identity}/field-inspection-tasks',
             rf'/api/v1/projects/{identity}/field-inspection-tasks/{identity}/(?:accept|reject|start|submissions|reviews)']
    patterns = read if method == 'GET' else write if method == 'POST' else []
    return any(re.fullmatch(pattern, base) for pattern in patterns)


async def _json(request, limit=1024*1024):
    raw = bytearray()
    async for part in request.stream():
        if len(raw) + len(part) > limit:
            raise HTTPException(413, 'REQUEST_TOO_LARGE')
        raw.extend(part)
    try:
        body = json.loads(raw)
        if type(body) is not dict:
            raise ValueError()
        return body
    except (ValueError, UnicodeError):
        raise HTTPException(422, 'INVALID_JSON') from None


def create_studio(root, worker, token, *, probe, be_url=None, fixture_file=None):
    root = Path(root).resolve()
    if os.name == 'nt' and root.drive.lower() != 'd:':
        raise ValueError('STUDIO_STORAGE_MUST_BE_ON_D')
    root.mkdir(parents=True, exist_ok=True)
    incoming = _safe_path(root, 'incoming')
    incoming.mkdir(exist_ok=True)
    database = _safe_path(root, 'studio.sqlite3')
    be_url = _backend_url(be_url)
    @contextmanager
    def db():
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()
    with db() as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS studio_jobs(id TEXT PRIMARY KEY,name TEXT NOT NULL,created REAL NOT NULL,annotation TEXT)')

    @asynccontextmanager
    async def lifespan(app):
        async with worker.router.lifespan_context(worker):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=worker),
                    base_url='http://worker', headers={'Authorization':'Bearer '+token}, timeout=600) as client:
                app.state.worker_client = client
                yield

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.capacity_check = lambda: check_capacity(root, {}, worker.state.store)
    app.state.backend_transport = None  # Injected only by mechanics tests.
    upload_lock = asyncio.Lock()

    @app.middleware('http')
    async def protect(request, call_next):
        host = request.headers.get('host', '')
        origin = request.headers.get('origin')
        if (not request.client or request.client.host not in LOCAL or
                host not in ('127.0.0.1:8765', 'localhost:8765', '[::1]:8765') or
                (origin is not None and origin != 'http://' + host) or
                request.headers.get('sec-fetch-site') == 'cross-site' or
                (request.method not in ('GET', 'HEAD') and request.headers.get('x-studio-request') != '1')):
            return JSONResponse({'code':'LOCAL_SAME_ORIGIN_REQUIRED'}, status_code=403)
        try:
            response = await call_next(request)
        except Exception:
            return JSONResponse({'code':'STUDIO_INTERNAL_ERROR'}, status_code=500)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob:; media-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.exception_handler(HTTPException)
    async def error(request, exc):
        return JSONResponse({'code':exc.detail}, status_code=exc.status_code)

    @app.exception_handler(WorkerStoreError)
    async def worker_error(request, exc):
        return JSONResponse({'code':exc.code}, status_code=exc.status_code)

    @app.exception_handler(RunnerError)
    async def media_error(request, exc):
        return JSONResponse({'code':'VIDEO_PROBE_FAILED'}, status_code=422)

    async def private(method, path, **kwargs):
        response = await app.state.worker_client.request(method, '/internal/v1/'+path, **kwargs)
        if response.status_code >= 400:
            raise HTTPException(response.status_code, response.json().get('code', 'WORKER_ERROR'))
        return response

    def registered(identity):
        with db() as connection:
            row = connection.execute('SELECT * FROM studio_jobs WHERE id=?', (identity,)).fetchone()
        if row is None:
            raise HTTPException(404, 'JOB_NOT_FOUND')
        record = worker.state.store.get(identity)
        if record is None:
            raise HTTPException(404, 'JOB_NOT_FOUND')
        return row, record

    def describe(identity, full=False):
        row, record = registered(identity)
        data = {'id':identity, 'name':row['name'], 'createdAt':row['created'],
                'state':record['state'], 'errorCode':record['error_code'],
                'inputBytes':record['payload']['inputBytes'],
                'cancellationRequested':record['cancellation_requested']}
        if full and record['state'] == 'COMPLETED':
            data['result'] = record['result']
        return data

    def source(identity):
        _, record = registered(identity)
        marker = _safe_path(worker.state.data_root, identity, 'input.mp4')
        if not marker.is_file() or record['input_marker'] != str(marker):
            raise HTTPException(404, 'VIDEO_NOT_AVAILABLE')
        return marker

    async def chunks(path):
        with path.open('rb') as stream:
            while chunk := await asyncio.to_thread(stream.read, 1024*1024):
                yield chunk

    async def submit(path, name, digest, size, metadata):
        width, height, duration, _ = metadata
        if not 0 < duration <= 180000 or width * height > 16777216:
            raise HTTPException(422, 'VIDEO_LIMIT_180_SECONDS_OR_16_MEGAPIXELS')
        identity = str(uuid4())
        payload = {field:str(uuid4()) for field in ('projectId','jobId','datasetId','sourceVideoFileId','modelVersionId')}
        payload.update(contractVersion='rg-ai-worker-v1', attemptId=identity,
            manifestHash=hashlib.sha256(('studio:'+identity).encode()).hexdigest(),
            checkpointSha256=FT95_SHA256, inputSha256=digest,
            preprocessingVersion=PREPROCESSING_VERSION, configVersion=CONFIG_VERSION,
            inputBytes=size, inputWidth=width, inputHeight=height, inputDurationMs=duration,
            sampleFps=1, maxFrames=180)
        await private('POST','jobs',json=payload)
        with db() as connection:
            connection.execute('INSERT INTO studio_jobs(id,name,created) VALUES(?,?,?)',(identity,name,time.time()))
        try:
            # Includes incoming/tmp/logs plus this attempt's newly committed
            # worst-case reservation; the worker subtree check alone cannot.
            await asyncio.to_thread(app.state.capacity_check)
            await private('PUT',f'jobs/{identity}/input',content=chunks(path),
                headers={'Content-Length':str(size),'X-Content-Sha256':digest})
        except BaseException:
            worker.state.store.request_cancel(identity)
            raise
        return describe(identity)

    @app.get('/')
    async def index():
        return FileResponse(WEB/'index.html', media_type='text/html')

    @app.get('/studio/studio.css')
    async def stylesheet():
        return FileResponse(WEB/'studio.css', media_type='text/css')

    @app.get('/studio/studio.js')
    async def script():
        return FileResponse(WEB/'studio.js', media_type='text/javascript')

    @app.get('/studio/workflow.js')
    async def workflow_script():
        return FileResponse(WEB/'workflow.js', media_type='text/javascript')

    @app.get('/studio/config')
    async def config():
        return {'ready':worker.state.readiness_checker(), 'classes':list(SOURCE_CLASSES),
                'model':'FT95 · YOLO11 · CPU', 'sampleFps':1, 'maxUploadBytes':MAX_UPLOAD,
                'maxDurationSeconds':180, 'beConfigured':be_url is not None,
                'positionMeaning':'DRONE_REFERENCE_NOT_GROUND_LOCATION'}

    @app.get('/studio/jobs')
    async def jobs():
        worker.state.store.expire_awaiting_input()
        with db() as connection:
            identities = [row['id'] for row in connection.execute('SELECT id FROM studio_jobs ORDER BY created DESC LIMIT 100')]
        return {'items':[describe(identity) for identity in identities]}

    @app.post('/studio/jobs', status_code=202)
    async def upload(request: Request):
        try:
            size = int(request.headers.get('content-length', '0'))
        except ValueError:
            size = 0
        if not 0 < size <= MAX_UPLOAD:
            raise HTTPException(413, 'VIDEO_LIMIT_2_GIB')
        if upload_lock.locked():
            raise HTTPException(429, 'UPLOAD_BUSY')
        async with upload_lock:
            await asyncio.to_thread(app.state.capacity_check)
            temporary = _safe_path(incoming, str(uuid4())+'.mp4')
            try:
                digest = hashlib.sha256()
                count = 0
                with temporary.open('xb') as stream:
                    async for chunk in request.stream():
                        count += len(chunk)
                        if count > size:
                            raise HTTPException(422, 'VIDEO_LENGTH_MISMATCH')
                        digest.update(chunk)
                        await asyncio.to_thread(stream.write, chunk)
                    if count != size:
                        raise HTTPException(422, 'VIDEO_LENGTH_MISMATCH')
                metadata = await asyncio.to_thread(probe, temporary)
                name = unquote(request.headers.get('x-video-name','video.mp4'))
                name = re.sub(r'[\x00-\x1f/\\]', '_', name)[:200] or 'video.mp4'
                return await submit(temporary, name, digest.hexdigest(), size, metadata)
            finally:
                temporary.unlink(missing_ok=True)

    @app.get('/studio/jobs/{identity}')
    async def job(identity: str):
        return describe(identity, full=True)

    @app.get('/studio/jobs/{identity}/video')
    async def video(identity: str):
        return FileResponse(source(identity), media_type='video/mp4')

    @app.get('/studio/jobs/{identity}/result')
    async def result(identity: str):
        registered(identity)
        response = await private('GET',f'jobs/{identity}/result')
        return Response(response.content, media_type='application/json',
                        headers={'Content-Disposition':'attachment; filename="ai-result.json"'})

    @app.get('/studio/jobs/{identity}/artifacts/{artifact_id}')
    async def artifact(identity: str, artifact_id: str):
        registered(identity)
        # Existing private transport verifies descriptor membership + bytes/hash.
        response = await private('GET',f'jobs/{identity}/artifacts/{artifact_id}')
        return Response(response.content, media_type=response.headers.get('content-type'),
                        headers={'Content-Disposition':response.headers.get('content-disposition','inline')})

    @app.post('/studio/jobs/{identity}/cancel')
    async def cancel(identity: str):
        registered(identity)
        await private('POST', f'jobs/{identity}/cancel', json={})
        return describe(identity)

    @app.post('/studio/jobs/{identity}/retry', status_code=202)
    async def retry(identity: str):
        row, record = registered(identity)
        if record['state'] not in ('FAILED','INTERRUPTED','CANCELLED'):
            raise HTTPException(409, 'RETRY_REQUIRES_FAILED_CANCELLED_OR_INTERRUPTED')
        if upload_lock.locked():
            raise HTTPException(429, 'UPLOAD_BUSY')
        async with upload_lock:
            await asyncio.to_thread(app.state.capacity_check)
            path = source(identity)
            await asyncio.to_thread(_verify_file, path,
                {'bytes':record['payload']['inputBytes'], 'sha256':record['payload']['inputSha256']})
            metadata = await asyncio.to_thread(probe, path)
            return await submit(path, row['name'], record['payload']['inputSha256'], path.stat().st_size, metadata)

    @app.get('/studio/jobs/{identity}/annotation')
    async def annotation(identity: str):
        row, _ = registered(identity)
        return json.loads(row['annotation']) if row['annotation'] else {}

    @app.post('/studio/jobs/{identity}/annotation')
    async def save_annotation(identity: str, request: Request):
        registered(identity)
        body = await _json(request)
        if body.get('kind') == 'OPERATOR_ESTIMATE':
            for key, bound in (('latitude',90),('longitude',180)):
                value = body.get(key)
                if type(value) not in (float,int) or not math.isfinite(value) or not -bound <= value <= bound:
                    raise HTTPException(422, 'INVALID_COORDINATE')
            if type(body.get('reason')) is not str or not 1 <= len(body['reason'].strip()) <= 1000:
                raise HTTPException(422, 'ESTIMATE_REASON_REQUIRED')
            body = {key:body[key] for key in ('kind','latitude','longitude','reason')}
        elif body.get('kind') == 'EXTERNAL_SRT':
            text = body.get('srtText')
            if type(text) is not str or not text.strip() or len(text.encode('utf-8')) > 1024*1024 or '-->' not in text:
                raise HTTPException(422, 'INVALID_SRT_ATTACHMENT')
            body = {'kind':'EXTERNAL_SRT','srtText':text, 'validation':'ATTACHED_NOT_VALIDATED_AS_GPS'}
        else:
            raise HTTPException(422, 'INVALID_ANNOTATION_KIND')
        with db() as connection:
            connection.execute('UPDATE studio_jobs SET annotation=? WHERE id=?',(json.dumps(body,allow_nan=False),identity))
        return body

    @app.post('/studio/be')
    async def backend(request: Request):
        if be_url is None:
            raise HTTPException(503, 'LOCAL_BE_NOT_CONFIGURED')
        body = await _json(request)
        return await relay(body, request.headers.get('authorization', ''))

    async def relay(body, bearer):
        method, path = body.get('method'), body.get('path')
        if not _be_allowed(method, path):
            raise HTTPException(403, 'BE_ROUTE_NOT_ALLOWED')
        if not bearer.startswith('Bearer ') or len(bearer) > 16384:
            raise HTTPException(401, 'USER_BEARER_REQUIRED')
        headers = {'Authorization':bearer, 'Accept':'application/json'}
        for field, header in (('etag','If-Match'),('idempotencyKey','Idempotency-Key')):
            if body.get(field):
                value = body[field]
                if type(value) is not str or len(value) > 200 or '\r' in value or '\n' in value:
                    raise HTTPException(422, 'INVALID_PRECONDITION')
                headers[header] = value
        try:
            async with httpx.AsyncClient(base_url=be_url, timeout=30, follow_redirects=False,
                    trust_env=False, transport=app.state.backend_transport) as client:
                async with client.stream(method, path, headers=headers, json=body.get('body') if method == 'POST' else None) as response:
                    data = bytearray()
                    async for part in response.aiter_bytes():
                        if len(data) + len(part) > 8*1024*1024:
                            raise HTTPException(502, 'BE_RESPONSE_TOO_LARGE')
                        data.extend(part)
                    try:
                        payload = json.loads(data) if data else None
                    except ValueError:
                        payload = {'code':'NON_JSON_RESPONSE'}
                    return {'status':response.status_code, 'etag':response.headers.get('etag'), 'body':payload}
        except httpx.HTTPError:
            raise HTTPException(502, 'LOCAL_BE_UNREACHABLE') from None

    if fixture_file is not None:
        from .test_studio_workflow import install_workflow
        install_workflow(app, fixture_file, be_url, _json, relay)

    return app


def create_app_from_env():
    """uvicorn factory; operator explicitly supplies all filesystem paths."""
    from .be_worker_runtime import create_runtime_app
    root = Path(os.environ['ROADGUARD_STUDIO_DATA_ROOT'])
    if not root.is_absolute() or (os.name == 'nt' and root.resolve().drive.lower() != 'd:'):
        raise ValueError('INVALID_STUDIO_DATA_ROOT')
    root.mkdir(parents=True, exist_ok=True)
    (root/'studio-server.pid').write_text(str(os.getpid()), encoding='ascii')
    # In-process credential: never persisted, logged or delivered to the browser.
    token = secrets.token_hex(32)
    token_file = _safe_path(root.resolve(), '.runtime-token')
    token_file.write_text(token, encoding='ascii')
    options = {key:os.environ[env] for key,env in {
        'checkpoint_path':'ROADGUARD_WORKER_CHECKPOINT',
        'ffmpeg':'ROADGUARD_WORKER_FFMPEG','ffprobe':'ROADGUARD_WORKER_FFPROBE'}.items()}
    try:
        worker = create_runtime_app(data_root=root/'worker',token_file=token_file,**options)
    finally:
        token_file.unlink(missing_ok=True)
    media = FFmpegMedia(options['ffmpeg'], options['ffprobe'])
    return create_studio(root, worker, token, probe=lambda path:media.probe(path,lambda:None),
                         be_url=os.environ.get('ROADGUARD_STUDIO_BE_URL') or None,
                         fixture_file=os.environ.get('ROADGUARD_STUDIO_FIXTURE_FILE') or None)
