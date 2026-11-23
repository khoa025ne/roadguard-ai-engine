"""Explicitly opted-in isolated fixture sessions; never mounted in production AI/BE."""
import asyncio
import json
import os
from pathlib import Path
import time
import hashlib
from uuid import UUID, uuid4
from urllib.parse import urlsplit

import httpx
from fastapi import Request, Response
from starlette.exceptions import HTTPException


def install_workflow(app, fixture_file, be_url, read_json, relay):
    path = Path(fixture_file).resolve(strict=True)
    if os.name == 'nt' and path.drive.lower() != 'd:':
        raise ValueError('FIXTURE_STORAGE_MUST_BE_ON_D')
    if path.stat().st_size > 1024 * 1024:
        raise ValueError('FIXTURE_TOO_LARGE')
    fixture = json.loads(path.read_text(encoding='utf-8-sig'))
    if not be_url or fixture['backendUrl'].rstrip('/') != be_url:
        raise ValueError('FIXTURE_BACKEND_MISMATCH')
    project = str(UUID(fixture['projectId']))
    accounts = fixture['accounts']
    if set(accounts) != {'PM', 'CREW'}:
        raise ValueError('FIXTURE_ROLES_REQUIRED')
    # Explicit public keys prevent future fixture credentials accidentally reaching the UI.
    public = {key: fixture[key] for key in (
        'projectId', 'projectName', 'surveyId', 'routeVersionId', 'segmentSetId',
        'segmentId', 'crewUserId', 'datasetId', 'workId', 'detectionIds',
        'classMap', 'causeCategoryCode', 'evidence', 'geometryEvidence', 'chainageRange') if key in fixture}
    public['isolatedLocal'] = True
    sessions = {}
    locks = {role: asyncio.Lock() for role in accounts}

    async def session(role):
        async with locks[role]:
            cached = sessions.get(role)
            if cached and cached[1] > time.monotonic():
                return cached[0]
            try:
                async with httpx.AsyncClient(base_url=be_url, follow_redirects=False,
                        trust_env=False, timeout=30, transport=app.state.backend_transport) as client:
                    response = await client.post('/api/v1/auth/login', json=accounts[role])
                    value = response.json() if response.status_code == 200 else {}
                token = value.get('accessToken')
                if not isinstance(token, str) or not token:
                    raise HTTPException(502, 'LOCAL_FIXTURE_LOGIN_FAILED')
            except (httpx.HTTPError, ValueError):
                raise HTTPException(502, 'LOCAL_FIXTURE_LOGIN_FAILED') from None
            sessions[role] = (token, time.monotonic() + 240)
            return token

    @app.get('/studio/workflow/context')
    async def context():
        return public

    @app.post('/studio/workflow/be')
    async def execute(request: Request):
        body = await read_json(request)
        role = body.get('role')
        target = body.get('path', '')
        # Fixture sessions may only affect this fixture project. Generic bearer workbench
        # remains independent and cannot borrow these identities.
        if role not in accounts or not isinstance(target, str) or not target.startswith(f'/api/v1/projects/{project}/'):
            raise HTTPException(403, 'FIXTURE_SCOPE_REQUIRED')
        result = await relay(body, 'Bearer ' + await session(role))
        if result['status'] == 401:
            sessions.pop(role, None)
        return result

    async def backend(role, method, target, body=None, etag=None):
        headers = {'Authorization': 'Bearer ' + await session(role)}
        if method == 'POST':
            headers['Idempotency-Key'] = str(uuid4())
        if etag:
            headers['If-Match'] = etag
        try:
            async with httpx.AsyncClient(base_url=be_url, follow_redirects=False,
                    trust_env=False, timeout=60, transport=app.state.backend_transport) as client:
                response = await client.request(method, target, json=body, headers=headers)
        except httpx.HTTPError:
            raise HTTPException(502, 'LOCAL_BE_UNREACHABLE') from None
        if not response.is_success:
            # Preserve safe structured business errors without exposing transport credentials.
            try:
                detail = response.json()
            except ValueError:
                detail = 'LOCAL_BE_REQUEST_FAILED'
            raise HTTPException(response.status_code, detail)
        return response

    @app.get('/studio/workflow/frames/{detection_id}')
    async def frame(detection_id: str):
        if detection_id not in fixture.get('detectionIds', []):
            raise HTTPException(404, 'FIXTURE_DETECTION_REQUIRED')
        facts = (await backend('PM', 'GET', f'/api/v1/projects/{project}/ai-candidates/{detection_id}')).json()
        file_id = str(UUID(facts['frameFileId']))
        response = await backend('PM', 'GET', f'/api/v1/files/{file_id}/content')
        media = response.headers.get('content-type', '').split(';')[0]
        if media not in ('image/jpeg', 'image/png') or len(response.content) > 8*1024*1024:
            raise HTTPException(502, 'INVALID_FRAME_CONTENT')
        return Response(response.content, media_type=media, headers={'Cache-Control':'no-store'})

    @app.post('/studio/workflow/tasks/{task_id}/photo')
    async def photo(task_id: str, request: Request):
        media = request.headers.get('content-type', '').split(';')[0]
        if media not in ('image/jpeg', 'image/png'):
            raise HTTPException(415, 'JPEG_OR_PNG_REQUIRED')
        task_id = str(UUID(task_id))
        task = (await backend('CREW', 'GET', f'/api/v1/projects/{project}/field-inspection-tasks/{task_id}')).json()
        if task.get('assignedToUserId') != fixture['crewUserId']:
            raise HTTPException(403, 'FIXTURE_CREW_REQUIRED')
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 20*1024*1024:
                raise HTTPException(413, 'PHOTO_TOO_LARGE')
        if not data or (media == 'image/jpeg' and not data.startswith(b'\xff\xd8\xff')) or (media == 'image/png' and not data.startswith(b'\x89PNG\r\n\x1a\n')):
            raise HTTPException(422, 'INVALID_PHOTO_SIGNATURE')
        checksum = hashlib.sha256(data).hexdigest()
        upload = (await backend('CREW','POST','/api/v1/uploads',{
            'purpose':'MEASUREMENT','projectId':project,'targetId':task_id,
            'fileName':'crew-test.jpg' if media == 'image/jpeg' else 'crew-test.png',
            'mediaType':media,'sizeBytes':len(data),'checksumSha256':checksum})).json()
        upload_id = str(UUID(upload['id']))
        root = f'/api/v1/uploads/{upload_id}'
        size = int(upload['partSizeBytes'])
        if size <= 0:
            raise HTTPException(502, 'INVALID_PART_SIZE')
        numbers = list(range(1, (len(data)+size-1)//size+1))
        parts = (await backend('CREW','POST',root+'/part-urls',{'partNumbers':numbers})).json()['parts']
        completed = []
        origin = fixture.get('storageOrigin', '').rstrip('/')
        allowed = urlsplit(origin)
        if allowed.scheme not in ('http','https') or allowed.hostname not in ('127.0.0.1','localhost','::1'):
            raise HTTPException(502, 'LOCAL_STORAGE_REQUIRED')
        async with httpx.AsyncClient(follow_redirects=False, trust_env=False, timeout=60,
                transport=app.state.backend_transport) as client:
            for part in parts:
                url = urlsplit(part['url'])
                if f'{url.scheme}://{url.netloc}' != origin or url.username or url.password:
                    raise HTTPException(502, 'STORAGE_ORIGIN_MISMATCH')
                number = int(part['partNumber'])
                if number not in numbers:
                    raise HTTPException(502, 'INVALID_UPLOAD_PART')
                try:
                    sent = await client.put(part['url'],content=bytes(data[(number-1)*size:number*size]))
                except httpx.HTTPError:
                    raise HTTPException(502, 'LOCAL_STORAGE_UPLOAD_FAILED') from None
                if not sent.is_success or not sent.headers.get('etag'):
                    raise HTTPException(502, 'LOCAL_STORAGE_UPLOAD_FAILED')
                completed.append({'partNumber':number,'eTag':sent.headers['etag']})
        current = await backend('CREW','GET',root)
        version = current.headers.get('etag') or '"'+current.json()['version']+'"'
        await backend('CREW','POST',root+'/complete',{'parts':completed,'checksumSha256':checksum},version)
        for _ in range(40):
            state = (await backend('CREW','GET',root)).json()
            if state['status'] == 'VERIFIED':
                return {'fileId':upload['fileId'],'checksumSha256':checksum,'mediaType':media,'status':'VERIFIED'}
            if state['status'] in ('FAILED','CANCELLED','EXPIRED'):
                raise HTTPException(409, 'UPLOAD_'+state['status'])
            await asyncio.sleep(.5)
        raise HTTPException(504, 'UPLOAD_VERIFICATION_PENDING')
