"""Local-mode contract, resource guard, recovery and model-isolation regression tests."""
import io
import json
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import mvp_video as api
from src.api import video_job_store as store
from src.inference import video_models as catalog
from src.inference.mvp_video import probe_video, sample_indices


class LocalVideoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runs = patch.object(api, 'RUNS', self.root / 'runs')
        self.runs.start()
        self.before = dict(api.JOBS)
        api.JOBS.clear()
        app = FastAPI()
        app.include_router(api.router)
        self.client = TestClient(app)

    def tearDown(self):
        api.JOBS.clear()
        api.JOBS.update(self.before)
        self.runs.stop()
        self.temp.cleanup()

    def job(self, status='COMPLETED'):
        jid = uuid.uuid4().hex
        job = {'job_id':jid,'created_at':store.now(),'status':status,'sequence':0,
               'result':{'models':[],'summary':{'counts':{'CRACK':0,'POTHOLE':0}},
                         'frames':[], 'limitations':'Chưa có GT'}}
        api.JOBS[jid] = job
        store.save(api.RUNS, job)
        return job

    def video(self):
        path = self.root / 'clip.mp4'
        writer = cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),25,(64,64))
        for _ in range(25):
            writer.write(np.zeros((64,64,3),dtype=np.uint8))
        writer.release()
        return path.read_bytes()

    def test_sampling_300_seconds_is_600_frames_at_25fps(self):
        frames = sample_indices(7500,25,2)
        self.assertEqual(len(frames),600)
        self.assertEqual(frames[:4],[0,12,25,37])
        self.assertEqual(len(sample_indices(100,25,None)),100)
        self.assertEqual(sample_indices(15,29.97,None),list(range(15)))

    def test_native_and_fps_options(self):
        self.assertIsNone(api.rate('native'))
        for fps in [1,2,5,10]:
            self.assertEqual(api.rate(str(fps)),fps)
        self.assertEqual(self.client.post('/api/mvp-video/upload',data={'sample_fps':'0'},files={'file':('v.mp4',b'x')}).status_code,422)

    def test_local_probe_does_not_truncate_at_300_seconds(self):
        cap = SimpleNamespace(isOpened=lambda:True,release=lambda:None,
            get=lambda p:{cv2.CAP_PROP_FPS:25,cv2.CAP_PROP_FRAME_COUNT:9000,
                          cv2.CAP_PROP_FRAME_WIDTH:1920,cv2.CAP_PROP_FRAME_HEIGHT:1080}.get(p,0))
        with patch('src.inference.mvp_video.cv2.VideoCapture',return_value=cap):
            value=probe_video('fixture',duration=None,sample_fps=2,max_frames=None)
        self.assertEqual(value['sampled_frames'],720)
        self.assertEqual(value['duration_seconds'],360)

    def test_public_mode_cannot_be_enabled(self):
        config=api.settings();config['mode']='public'
        with patch('src.api.mvp_video.json.loads',return_value=config):
            with self.assertRaisesRegex(ValueError,'PUBLIC_RELEASE_BLOCKED'):
                api.settings()

    def test_second_process_cannot_use_same_result_directory(self):
        from filelock import FileLock
        api.RUNS.mkdir(parents=True)
        lease=FileLock(str(api.RUNS/'.service.lock'))
        with lease:
            app=FastAPI();app.include_router(api.router)
            local=TestClient(app,client=('127.0.0.1',43210))
            response=local.get('/api/mvp-video/jobs')
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()['detail']['code'],'LOCAL_SERVICE_IN_USE')

    def test_remote_client_and_cross_origin_denied(self):
        self.assertEqual(self.client.get('/api/mvp-video/jobs',headers={'Origin':'https://foreign.example'}).status_code,403)
        app=FastAPI();app.include_router(api.router)
        remote=TestClient(app,client=('192.0.2.1',1234))
        self.assertEqual(remote.get('/api/mvp-video/jobs').status_code,403)

    def test_history_survives_memory_reset_and_interrupts_unfinished_job(self):
        done=self.job();running=self.job('RUNNING')
        api.JOBS.clear()
        value=self.client.get('/api/mvp-video/jobs').json()
        states={j['job_id']:j['status'] for j in value['jobs']}
        self.assertEqual(states[done['job_id']],'COMPLETED')
        self.assertEqual(states[running['job_id']],'INTERRUPTED')
        self.assertTrue(self.client.get('/api/mvp-video/'+running['job_id']+'/logs').json()['events'])

    def test_logs_are_sequenced_and_not_deleted_by_reads(self):
        job=self.job()
        for _ in range(3):api.event(job,'inference','INFO','FRAME_PROCESSED','Đã xử lý frame.')
        path='/api/mvp-video/'+job['job_id']+'/logs'
        self.assertEqual([e['sequence'] for e in self.client.get(path+'?after=1').json()['events']],[2,3])
        self.assertEqual(len(self.client.get(path).json()['events']),3)

    def test_local_report_never_calls_llm(self):
        job=self.job()
        with patch('src.curation.kdv_inspector.KDVInspector',side_effect=AssertionError('No API')):
            response=self.client.post('/api/mvp-video/'+job['job_id']+'/report/local')
        self.assertEqual(response.status_code,200)
        self.assertTrue((api.RUNS/job['job_id']/'report_local.html').is_file())
        self.assertEqual(response.json()['provider'],'local-statistics')

    def test_model_corrupt_isolated_and_default_missing_no_fallback(self):
        models=self.root/'models';models.mkdir()
        for name in ['roadguard_crack_yolo11n_v1.pt','broken.pt','legacy.pt']:(models/name).write_bytes(b'fixture')
        def inspect(path):
            if path.name=='broken.pt':raise ValueError('private-password')
            return {'task':'CRACK' if 'crack' in path.name else 'POTHOLE','classes':{0:'crack'},'version':'test','sha256':'a'*64}
        with patch.object(catalog,'model_directory',return_value=models),patch.object(catalog,'inspect_checkpoint',side_effect=inspect), patch.object(catalog,'ROAD_WEIGHTS',models/'missing-segment.pt'):
            value=catalog.discover_models(refresh=True)
        self.assertIsNone(value['defaults']['POTHOLE'])
        self.assertEqual(len(value['models']),3)
        self.assertNotIn('private-password',json.dumps(value))

    def test_client_path_cannot_select_model(self):
        with self.assertRaisesRegex(ValueError,'MODEL_UNAVAILABLE'):
            catalog.resolve_models({'CRACK':'../../weights.pt','POTHOLE':'anything'})

    def test_low_disk_has_actionable_code(self):
        with patch('src.api.mvp_video.shutil.disk_usage',return_value=SimpleNamespace(free=1)):
            response=self.client.get('/api/mvp-video/config')
        self.assertEqual(response.status_code,507)
        self.assertEqual(response.json()['detail']['code'],'DISK_SPACE_LOW')

    def test_upload_replay_same_identity_and_queue_capacity(self):
        video=self.video()
        with patch.object(api.WORKER,'submit') as submit:
            response=self.client.post('/api/mvp-video/upload',files={'file':('test.mp4',video)},headers={'Idempotency-Key':'fixture-one'})
            self.assertEqual(response.status_code,200,response.text)
            jid=response.json()['job_id']
            replay=self.client.post('/api/mvp-video/upload',files={'file':('test.mp4',video)},headers={'Idempotency-Key':'fixture-one'})
            self.assertEqual(replay.json()['job_id'],jid)
            self.assertEqual(submit.call_count,1)
            conflict=self.client.post('/api/mvp-video/upload',data={'sample_fps':'5'},files={'file':('test.mp4',video)},headers={'Idempotency-Key':'fixture-one'})
            self.assertEqual(conflict.status_code,409)
            for _ in range(3):self.job('QUEUED')
            full=self.client.post('/api/mvp-video/upload',files={'file':('test.mp4',video)})
            self.assertEqual(full.status_code,429)
            self.assertEqual(full.json()['detail']['code'],'QUEUE_FULL')

    def test_cancel_preserves_saved_results(self):
        job=self.job('QUEUED')
        response=self.client.post('/api/mvp-video/'+job['job_id']+'/cancel')
        self.assertTrue(response.json()['cancel_requested'])
        api.execute(job['job_id'],'unused',{'seconds':None,'fps':2})
        self.assertEqual(job['status'],'CANCELLED')
        self.assertTrue((api.RUNS/job['job_id']/'job.json').is_file())

    def test_prepared_job_survives_restart_and_start_is_idempotent(self):
        with patch.object(api.WORKER,'submit') as submit:
            r=self.client.post('/api/mvp-video/upload',data={'sample_fps':'native','prepare_only':'true'},files={'file':('v.mp4',self.video())})
            self.assertEqual(r.status_code,200,r.text)
            jid=r.json()['job_id']
            self.assertEqual(submit.call_count,0)
            api.JOBS.clear()
            prepared=self.client.get('/api/mvp-video/'+jid).json()
            self.assertEqual(prepared['status'],'READY')
            self.assertEqual(prepared['video']['sampled_frames'],25)
            self.assertEqual(self.client.post('/api/mvp-video/'+jid+'/start').status_code,200)
            self.assertEqual(self.client.post('/api/mvp-video/'+jid+'/start').status_code,200)
            self.assertEqual(submit.call_count,1)

    def test_only_one_inference_worker_runs_and_queued_cancel_never_infers(self):
        first,second=self.job('QUEUED'),self.job('QUEUED')
        entered=threading.Event();release=threading.Event();active=0;peak=0
        def inference(*args,**kwargs):
            nonlocal active,peak
            active+=1;peak=max(peak,active);entered.set();release.wait(5);active-=1
            return {'models':[],'summary':{'counts':{}},'frames':[],'limitations':'Fixture'}
        with patch.object(api,'analyze_video',side_effect=inference):
            a=api.WORKER.submit(api.execute,first['job_id'],'unused',{'fps':2})
            self.assertTrue(entered.wait(5))
            b=api.WORKER.submit(api.execute,second['job_id'],'unused',{'fps':2})
            self.client.post('/api/mvp-video/'+second['job_id']+'/cancel')
            release.set();a.result(timeout=10);b.result(timeout=10)
        self.assertEqual(peak,1)
        self.assertEqual(first['status'],'COMPLETED')
        self.assertEqual(second['status'],'CANCELLED')


if __name__=='__main__':unittest.main()
