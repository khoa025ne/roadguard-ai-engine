"""Integration regression for the existing local job router and Review Queue."""
import copy
import json
import socket
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from src.api import mvp_video as api
from src.api import video_job_store as store
from tests.test_video_review_queue import browser_env


def application():
    from src.api.ui_server import app
    return app


class VideoReviewIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patch = patch.object(api, 'RUNS', self.root/'runs'); self.patch.start()
        self.jobs = dict(api.JOBS); api.JOBS.clear()
        self.client = TestClient(application())

    def tearDown(self):
        self.client.close()
        for key in list(api.SERVICE_LEASES):
            if key.startswith(str(self.root)):
                api.SERVICE_LEASES.pop(key).release()
        api.JOBS.clear(); api.JOBS.update(self.jobs)
        self.patch.stop(); self.temp.cleanup()

    def make_job(self, negative=False):
        jid = uuid.uuid4().hex
        folder = store.directory(api.RUNS, jid); folder.mkdir(parents=True)
        frames=[]
        for i in range(2):
            name=f'original_{i:08d}.jpg'
            image=np.zeros((80,100,3),dtype=np.uint8)
            cv2.line(image,(4,4),(90,70),(255,255,255),2)
            cv2.imwrite(str(folder/name),image)
            frames.append({'frame':i,'timestamp_s':i/2,'original':name,'image':name})
        clip=folder/'clip.mp4'
        writer=cv2.VideoWriter(str(clip),cv2.VideoWriter_fourcc(*'mp4v'),2,(100,80))
        for _ in range(2):writer.write(image)
        writer.release();clip.replace(folder/'source.video')
        ds=[] if negative else [{'frame':i,'timestamp_s':i/2,'bbox':[1,2,20,30],
            'class_name':'crack','category':'CRACK','confidence':.8,'model':'fixture',
            'model_version':'test','local_class_id':0} for i in range(2)]
        result={'frames':frames,'detections':ds,'models':[],
                'summary':{'counts':{'CRACK':len(ds)},'sampled_frames':2,'runtime_seconds':0,'source_fps':2},
                'limitations':'Dữ liệu thử; chưa xác minh chất lượng AI'}
        (folder/'analysis.json').write_text(json.dumps(result),encoding='utf-8')
        job={'job_id':jid,'status':'COMPLETED','created_at':store.now(),'sequence':0,
             'source_name':'fixture.mp4','source_sha256':api.hashlib.sha256((folder/'source.video').read_bytes()).hexdigest(),
             'result':result,'sample_fps':2}
        api.JOBS[jid]=job;store.save(api.RUNS,job);api.local_report(job)
        return job,folder

    def context(self, job):
        path=f"/api/mvp-video/{job['job_id']}/review-queue"
        response=self.client.get(path+'/api/state')
        self.assertEqual(response.status_code,200,response.text)
        return path,response.json()

    def test_job_review_report_rerun_and_legacy_guard(self):
        job,folder=self.make_job();raw=(folder/'analysis.json').read_bytes()
        path,context=self.context(job)
        self.assertEqual(context['source']['source_job_id'],job['job_id'])
        item=next(iter(context['state']['detections'].values()))
        body={'base_revision':0,'reviewer':'Tester','confirm':True,'items':[item]}
        self.assertEqual(self.client.post(path+'/api/review',json=body).status_code,201)
        self.assertEqual(self.client.post(path+'/api/review',json=body).status_code,409)
        self.assertEqual((folder/'analysis.json').read_bytes(),raw)
        self.assertEqual(self.client.get(path+'/api/state').json()['state']['coverage'],{})
        draft=self.client.post(path+'/api/report/draft',json={'base_revision':1,'reviewer':'Tester'}).json()
        ready=self.client.post(path+'/api/report/ready',json={'base_revision':draft['revision'],'reviewer':'Tester','confirm':True})
        self.assertEqual(ready.status_code,201,ready.text)
        approved=self.client.post(path+'/api/report/approve',json={'base_revision':ready.json()['revision'],
            'reviewer':'Tester','confirm':True,'accept_limits':True})
        self.assertEqual(approved.status_code,201,approved.text)
        self.assertEqual(approved.json()['overview']['approved_physical_ids'],1)
        approved_path=folder/'review/reports/v000003.json';approved_bytes=approved_path.read_bytes()
        self.client.post(path+'/api/report/draft',json={'base_revision':1,'reviewer':'Tester'})
        self.assertEqual(approved_path.read_bytes(),approved_bytes)
        (folder/'analysis.json').write_text(json.dumps({**job['result'],'limitations':'rerun'}),encoding='utf-8')
        self.assertEqual(self.client.get(path+'/api/state').status_code,409)
        self.assertEqual(approved_path.read_bytes(),approved_bytes)
        legacy,legacy_dir=self.make_job();legacy['reviews']={'0':{'status':'approved'}}
        url=f"/api/mvp-video/{legacy['job_id']}/review-queue/api/state"
        self.assertEqual(self.client.get(url).status_code,409)
        self.assertFalse((legacy_dir/'review_source.json').exists())

    def test_permissions_and_negative_video(self):
        job,folder=self.make_job(negative=True);path,context=self.context(job)
        self.assertEqual(context['state']['detections'],{})
        coverage={'frame':0,'scope':'regions','fully_inspected':True,
                  'verified_regions':[[0,0,40,40]],'unverified_regions':[[10,10,20,20]]}
        body={'base_revision':0,'reviewer':'Tester','confirm':True,'coverage':[coverage]}
        self.assertEqual(self.client.post(path+'/api/review',json=body).status_code,201)
        draft=self.client.post(path+'/api/report/draft',json={'base_revision':1,'reviewer':'Tester'}).json()
        ready=self.client.post(path+'/api/report/ready',json={'base_revision':draft['revision'],'reviewer':'Tester','confirm':True})
        self.assertEqual(ready.status_code,201,ready.text)
        self.assertEqual(self.client.get(path+'/api/state',headers={'Origin':'https://foreign.example'}).status_code,403)
        remote=TestClient(application(),client=('10.0.0.5',3210))
        for suffix in ['/', '/ui.js', '/api/state', '/api/frame/0','/api/video','/api/report/v000001.json']:
            self.assertEqual(remote.get(path+suffix).status_code,403)
        self.assertEqual(remote.post(path+'/api/review',json=body).status_code,403)
        self.assertEqual(self.client.get(path+'/api/state',headers={'Host':'evil.example'}).status_code,403)

    def test_upload_start_to_review_uses_existing_job_lifecycle(self):
        seed,seed_folder=self.make_job()
        def fixture_inference(source, output, **options):
            for frame in seed['result']['frames']:
                shutil.copyfile(seed_folder/frame['original'],Path(output)/frame['original'])
            result=copy.deepcopy(seed['result'])
            (Path(output)/'analysis.json').write_text(json.dumps(result),encoding='utf-8')
            return result
        with patch.object(api,'analyze_video',side_effect=fixture_inference):
            uploaded=self.client.post('/api/mvp-video/upload',data={'prepare_only':'true','sample_fps':'2'},
                files={'file':('fixture.mp4',(seed_folder/'source.video').read_bytes())})
            self.assertEqual(uploaded.status_code,200,uploaded.text)
            jid=uploaded.json()['job_id']
            self.assertEqual(self.client.post(f'/api/mvp-video/{jid}/start').status_code,200)
            for _ in range(100):
                result=self.client.get(f'/api/mvp-video/{jid}').json()
                if result['status'] in store.TERMINAL:break
                time.sleep(.05)
            self.assertEqual(result['status'],'COMPLETED',result)
        path,context=self.context(api.JOBS[jid])
        self.assertEqual(context['source_binding']['job_id'],jid)
        self.assertEqual(context['state']['revision'],0)
        self.assertEqual(len(context['state']['detections']),2)

    def test_integrated_browser_e2e(self):
        job,folder=self.make_job()
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        server=uvicorn.Server(uvicorn.Config(application(),log_level='error'))
        thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
        try:
            for _ in range(100):
                if server.started:break
                time.sleep(.05)
            self.assertTrue(server.started)
            script=Path(__file__).with_name('browser_video_review_integration.cjs')
            result=subprocess.run(['node',str(script),f'http://127.0.0.1:{port}',job['job_id']],
                                  capture_output=True,text=True,env=browser_env(),timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
            self.assertTrue((folder/'review/revisions/r000001.json').is_file())
            self.assertEqual(json.loads((folder/'review/reports/v000003.json').read_text(encoding='utf-8'))['status'],'approved')
        finally:
            server.should_exit=True;thread.join(timeout=10);sock.close()


if __name__=='__main__':unittest.main()
