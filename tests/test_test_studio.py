"""Studio boundary tests; injected media is NOT actual inference evidence."""
import os
from pathlib import Path
import tempfile
import unittest
import httpx
from fastapi.testclient import TestClient
from src.api.be_worker import create_app as worker_app
from src.api.test_studio import create_studio, _be_allowed

TOKEN = 'studio-test-secret-not-production-1234567890'
WRITE = {'X-Studio-Request': '1'}


class StudioTests(unittest.TestCase):
    def test_workflow_photo_uses_normal_upload_and_rejects_foreign_storage(self):
        import json
        identity = '00000001-0000-0000-0000-000000000001'
        fixture = self.root/'photo-fixture.json'
        fixture.write_text(json.dumps({'backendUrl':'http://127.0.0.1:5000','projectId':identity,
            'crewUserId':identity,'storageOrigin':'http://127.0.0.1:9000',
            'accounts':{'PM':{'email':'pm','password':'private'},'CREW':{'email':'crew','password':'private'}}}))
        app = create_studio(self.root/'photos',worker_app(self.root/'photo-worker',TOKEN),TOKEN,
            probe=lambda p: None,be_url='http://127.0.0.1:5000',fixture_file=fixture)
        foreign = False
        seen = []
        def handle(request):
            seen.append(request)
            path=request.url.path
            if path.endswith('/login'): return httpx.Response(200,json={'accessToken':'private-crew-token'})
            if 'field-inspection-tasks' in path: return httpx.Response(200,json={'assignedToUserId':identity})
            if path == '/api/v1/uploads':
                body=json.loads(request.content)
                self.assertEqual(body['targetId'],identity)
                self.assertEqual(body['purpose'],'MEASUREMENT')
                return httpx.Response(201,json={'id':identity,'fileId':identity,'partSizeBytes':8*1024*1024})
            if path.endswith('/part-urls'): return httpx.Response(200,json={'parts':[{'partNumber':1,'url':('http://evil.test' if foreign else 'http://127.0.0.1:9000')+'/part?secret=signed'}]})
            if request.method == 'PUT': return httpx.Response(200,headers={'ETag':'"part-etag"'})
            if path.endswith('/complete'): return httpx.Response(202,json={})
            return httpx.Response(200,json={'status':'VERIFIED','version':'version'},headers={'ETag':'"version"'})
        app.state.backend_transport=httpx.MockTransport(handle)
        with TestClient(app,base_url='http://127.0.0.1:8765',client=('127.0.0.1',1234)) as client:
            route=f'/studio/workflow/tasks/{identity}/photo'
            headers={**WRITE,'Content-Type':'image/jpeg'}
            self.assertEqual(client.post(route,headers=headers,content=b'invalid').status_code,422)
            response=client.post(route,headers=headers,content=b'\xff\xd8\xfftest')
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['status'],'VERIFIED')
            self.assertNotIn('private-crew-token',response.text)
            put=next(r for r in seen if r.method == 'PUT')
            self.assertNotIn('Authorization',put.headers)
            foreign=True
            seen.clear()
            self.assertEqual(client.post(route,headers=headers,content=b'\xff\xd8\xfftest').status_code,502)
            self.assertFalse(any(r.method == 'PUT' for r in seen))

    def test_dataset_read_matches_existing_public_controller(self):
        identity = '00000001-0000-0000-0000-000000000001'
        self.assertTrue(_be_allowed('GET', f'/api/v1/datasets/{identity}'))
        self.assertTrue(_be_allowed('GET', f'/api/v1/datasets/{identity}/coverage'))
        self.assertFalse(_be_allowed('POST', f'/api/v1/datasets/{identity}'))

    def test_workflow_routes_are_explicit_and_read_only_where_required(self):
        identity = '00000001-0000-0000-0000-000000000001'
        root = f'/api/v1/projects/{identity}'
        for path in (f'{root}/ai-candidates/{identity}', f'{root}/defects/{identity}',
                     f'{root}/field-inspection-tasks', f'{root}/field-inspection-tasks/{identity}',
                     f'{root}/field-inspection-tasks/{identity}/start-origin',
                     f'{root}/field-inspection-tasks/{identity}/submissions/{identity}'):
            self.assertTrue(_be_allowed('GET', path), path)
        for action in ('accept','start','submissions','reviews'):
            self.assertTrue(_be_allowed('POST', f'{root}/field-inspection-tasks/{identity}/{action}'))
        self.assertFalse(_be_allowed('POST', f'{root}/defects/{identity}'))
        self.assertFalse(_be_allowed('POST', f'{root}/field-inspection-tasks/{identity}/arbitrary'))

    def test_fixture_workflow_uses_real_login_without_disclosing_credentials(self):
        import json
        identity = '00000001-0000-0000-0000-000000000001'
        fixture = self.root / 'fixture.json'
        fixture.write_text(json.dumps({'backendUrl':'http://127.0.0.1:5000',
            'projectId':identity,'crewUserId':identity,'accounts':{
            'PM':{'email':'pm@local.test','password':'private-password'},
            'CREW':{'email':'crew@local.test','password':'private-password-crew'}}}))
        app = create_studio(self.root/'workflow', worker_app(self.root/'workflow-worker',TOKEN), TOKEN,
                            probe=lambda p: None, be_url='http://127.0.0.1:5000', fixture_file=fixture)
        seen=[]
        def handle(request):
            seen.append(request)
            if request.url.path == '/api/v1/auth/login':
                return httpx.Response(200,json={'accessToken':'private-pm-token'})
            return httpx.Response(200,json={'items':[]})
        app.state.backend_transport=httpx.MockTransport(handle)
        with TestClient(app,base_url='http://127.0.0.1:8765',client=('127.0.0.1',1234)) as client:
            context=client.get('/studio/workflow/context')
            self.assertEqual(context.status_code,200)
            self.assertNotIn('accounts',context.text)
            self.assertNotIn('password',context.text)
            self.assertEqual(client.get('/studio/workflow.js').status_code,200)
            self.assertEqual(client.get(f'/studio/workflow/frames/{identity}').status_code,404)
            self.assertEqual(client.post(f'/studio/workflow/tasks/{identity}/photo',headers={**WRITE,'Content-Type':'text/plain'},content=b'bad').status_code,415)
            response=client.post('/studio/workflow/be',headers=WRITE,json={
                'role':'PM','method':'GET','path':f'/api/v1/projects/{identity}/field-inspection-tasks'})
            self.assertEqual(response.json()['status'],200)
            self.assertEqual(seen[-1].headers['Authorization'],'Bearer private-pm-token')
            self.assertNotIn('private-pm-token',response.text)
            self.assertEqual(client.post('/studio/workflow/be',headers=WRITE,json={
                'role':'SUPERVISOR','method':'GET','path':'/api/v1/projects'}).status_code,403)
            self.assertEqual(client.post('/studio/workflow/be',headers=WRITE,json={
                'role':'PM','method':'GET','path':'/api/v1/projects/00000002-0000-0000-0000-000000000002/field-inspection-tasks'}).status_code,403)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='D:/RoadGuard-AI-LocalTest' if os.name == 'nt' else None)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        worker = worker_app(self.root / 'worker', TOKEN)
        worker.state.capacity_checker = lambda *args: None
        self.app = create_studio(self.root, worker, TOKEN,
                                 probe=lambda p: (320, 240, 1000, [(0, 0)]))
        self.app.state.capacity_check = lambda *args: None
        self.client = self.enterContext(TestClient(self.app, base_url='http://127.0.0.1:8765', client=('127.0.0.1', 12345)))

    def upload(self, name='demo.mp4'):
        return self.client.post('/studio/jobs', content=b'fake-video',
            headers={**WRITE, 'X-Video-Name': name})

    def test_host_origin_and_mutation_protection(self):
        self.assertEqual(self.client.get('/studio/config', headers={'Host':'evil.example'}).status_code, 403)
        self.assertEqual(self.client.get('/studio/config', headers={'Origin':'https://evil.example'}).status_code, 403)
        self.assertEqual(self.client.post('/studio/jobs', content=b'x').status_code, 403)
        self.assertEqual(self.client.get('/studio/config').status_code, 200)

    def test_rejects_length_mismatch_and_cleans_spool(self):
        response = self.client.post('/studio/jobs', content=b'bad', headers={**WRITE, 'Content-Length':'9'})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(list((self.root / 'incoming').iterdir()), [])
        self.assertEqual(self.client.get('/studio/jobs').json()['items'], [])

    def test_upload_history_registered_video_and_cancel(self):
        response = self.upload()
        self.assertEqual(response.status_code, 202, response.text)
        job = response.json()
        self.assertEqual(job['state'], 'QUEUED')
        self.assertEqual(self.client.get('/studio/jobs').json()['items'][0]['id'], job['id'])
        self.assertEqual(self.client.get(f"/studio/jobs/{job['id']}/video").content, b'fake-video')
        self.assertEqual(self.client.get('/studio/jobs/unknown/video').status_code, 404)
        self.assertEqual(self.client.post(f"/studio/jobs/{job['id']}/cancel", headers=WRITE).status_code, 200)

    def test_retry_only_terminal_and_uses_new_identity(self):
        job = self.upload().json()
        self.assertEqual(self.client.post(f"/studio/jobs/{job['id']}/retry", headers=WRITE).status_code, 409)
        self.client.post(f"/studio/jobs/{job['id']}/cancel", headers=WRITE)
        retry = self.client.post(f"/studio/jobs/{job['id']}/retry", headers=WRITE)
        self.assertEqual(retry.status_code, 202, retry.text)
        self.assertNotEqual(retry.json()['id'], job['id'])

    def test_annotation_is_separate_and_validated(self):
        job = self.upload().json()
        route = f"/studio/jobs/{job['id']}/annotation"
        self.assertEqual(self.client.post(route, headers=WRITE, json={'kind':'OPERATOR_ESTIMATE','latitude':91,'longitude':1,'reason':'test'}).status_code,422)
        body = {'kind':'OPERATOR_ESTIMATE','latitude':10.5,'longitude':106.2,'reason':'Test approximation'}
        self.assertEqual(self.client.post(route, headers=WRITE, json=body).status_code,200)
        self.assertEqual(self.client.get(route).json()['kind'],'OPERATOR_ESTIMATE')
        self.assertNotIn('result', self.client.get(f"/studio/jobs/{job['id']}").json())

    def test_private_routes_not_mounted_and_be_not_configured(self):
        self.assertEqual(self.client.get('/internal/v1/health').status_code,404)
        response = self.client.post('/studio/be', headers=WRITE, json={'method':'GET','path':'/api/v1/projects'})
        self.assertEqual(response.status_code,503)
        self.assertNotIn(TOKEN, self.client.get('/studio/config').text)

    def test_capacity_rechecked_after_admission_and_failed_reservation_cancelled(self):
        calls=[]
        def capacity():
            calls.append(True)
            if len(calls)==2:
                from src.api.be_worker_store import WorkerStoreError
                raise WorkerStoreError('DISK_BUDGET_EXCEEDED',507)
        self.app.state.capacity_check=capacity
        response=self.upload()
        self.assertEqual(response.status_code,507)
        self.assertEqual(len(calls),2)
        self.assertEqual(self.client.get('/studio/jobs').json()['items'][0]['state'],'CANCELLED')
        self.assertEqual(list((self.root/'incoming').iterdir()),[])

    def test_requires_loopback_backend_and_blocks_callback(self):
        with self.assertRaises(ValueError):
            create_studio(self.root, worker_app(self.root/'other', TOKEN), TOKEN,
                          probe=lambda p: None, be_url='https://public.example')

    def test_be_relay_keeps_credentials_server_side_and_forwards_preconditions(self):
        seen = []
        def handle(request):
            seen.append(request)
            return httpx.Response(412, json={'code':'concurrency_conflict'}, headers={'ETag':'"version-2"'})
        app = create_studio(self.root/'proxy', worker_app(self.root/'proxy-worker',TOKEN), TOKEN,
                            probe=lambda p: None, be_url='http://127.0.0.1:5000')
        app.state.backend_transport = httpx.MockTransport(handle)
        with TestClient(app, base_url='http://127.0.0.1:8765',client=('127.0.0.1',1234)) as client:
            identity='00000001-0000-0000-0000-000000000001'
            response=client.post('/studio/be',headers={**WRITE,'Authorization':'Bearer user-test-token'},
                json={'method':'POST','path':f'/api/v1/processing-jobs/{identity}/retry',
                      'body':{},'etag':'"version-1"','idempotencyKey':'retry-once'})
            self.assertEqual(response.json()['status'],412)
            self.assertEqual(response.json()['etag'],'"version-2"')
            self.assertEqual(seen[0].headers['If-Match'],'"version-1"')
            self.assertEqual(seen[0].headers['Idempotency-Key'],'retry-once')
            self.assertEqual(seen[0].headers['Authorization'],'Bearer user-test-token')
            for path in ('https://evil.example/x','/api/v1/internal/processing-jobs/x/results',
                         '/api/v1/projects/../auth/login','//evil.example','/api/v1/projects%2f..'):
                response=client.post('/studio/be',headers=WRITE,json={'method':'GET','path':path})
                self.assertEqual(response.status_code,403,path)
            self.assertEqual(len(seen),1)


if __name__ == '__main__':
    unittest.main()
