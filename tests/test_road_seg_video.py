import hashlib
import json
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np
import torch

from src.inference import mvp_video as inference
from src.inference import video_models as catalog
from tests import test_video_review_integration as integration
from tests.test_video_review_queue import browser_env
from src.api import mvp_video as api
from src.api import video_job_store as store


class Masks:
    def __init__(self, array): self.data=torch.tensor(array[None],dtype=torch.float32)
    def __len__(self): return len(self.data)


class SegmentationTests(unittest.TestCase):
    def test_checkpoint_taxonomy_missing_and_wrong_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); path=root/'road.pt'
            with patch.object(catalog,'model_directory',return_value=root),patch.object(catalog,'ROAD_WEIGHTS',path):
                missing=catalog.discover_models(refresh=True)
                self.assertIsNone(missing['segment_default'])
                with self.assertRaises(ValueError): catalog.resolve_segment_model('missing')
                path.write_bytes(b'fixture')
                with patch.object(catalog,'YOLO',return_value=SimpleNamespace(task='detect',names={0:'road'})):
                    wrong=catalog.discover_models(refresh=True)
                    self.assertIsNone(wrong['segment_default'])
                with patch.object(catalog,'YOLO',return_value=SimpleNamespace(task='segment',names={0:'sidewalk'})):
                    self.assertIsNone(catalog.discover_models(refresh=True)['segment_default'])
                with patch.object(catalog,'YOLO',return_value=SimpleNamespace(task='segment',names={0:'road'})):
                    valid=catalog.discover_models(refresh=True)
                    self.assertIsNotNone(valid['segment_default'])
                    row,weight=catalog.resolve_segment_model(valid['segment_default'])
                    self.assertEqual((row['task'],weight),('SEGMENT',path))

    def test_load_rechecks_task_and_pinned_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'road.pt';path.write_bytes(b'fixture')
            row={'id':'seg','sha256':hashlib.sha256(b'fixture').hexdigest()}
            with patch.object(catalog,'resolve_segment_model',return_value=(row,path)):
                with patch.object(inference,'YOLO',return_value=SimpleNamespace(task='detect',names={0:'road'})):
                    with self.assertRaises(ValueError): inference.load_segmenter('seg')
                with patch.object(inference,'YOLO',return_value=SimpleNamespace(task='segment',names={0:'road'})):
                    with self.assertRaisesRegex(ValueError,'MODEL_CHANGED'): inference.load_segmenter('seg',{'sha256':'changed'})

    def test_segment_on_off_missing_mask_and_outside_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); video=root/'clip.mp4'
            writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),2,(64,64))
            for value in (80,120): writer.write(np.full((64,64,3),value,np.uint8))
            writer.release()
            originals=[];cap=cv2.VideoCapture(str(video))
            while True:
                ok,frame=cap.read()
                if not ok:break
                originals.append(frame)
            cap.release()
            calls=[]
            def detect(image,**settings):
                calls.append(image.copy())
                box=SimpleNamespace(xyxy=np.array([[40,10,60,30]]),cls=np.array([0]),conf=np.array([.8]))
                return [SimpleNamespace(boxes=[box],speed={'inference':1.})]
            detector=SimpleNamespace(predict=detect)
            mask=np.zeros((64,64),np.float32);mask[:,:32]=1
            predictions=[SimpleNamespace(masks=Masks(mask),boxes=SimpleNamespace(cls=[0])),SimpleNamespace(masks=None)]
            segment=SimpleNamespace(predict=lambda *args,**kwargs:[predictions.pop(0)])
            def models(*args):return [('CRACK','fixture',detector)],[{'category':'CRACK','id':'det','version':'test','classes':{0:'crack'}}]
            with patch.object(inference,'load_models',side_effect=models),patch.object(inference,'load_segmenter',return_value=(segment,{'id':'seg'})) as loader:
                on=inference.analyze_video(video,root/'on',duration=None,sample_fps=2,segment_model='seg')
                self.assertEqual(len(on['detections']),2)
                self.assertEqual(on['detections'][0]['road_overlap'],0.)
                self.assertEqual(on['detections'][0]['road_warning'],'outside_or_partial_road_mask')
                self.assertEqual(on['frames'][1]['road_mask_status'],'missing_needs_review')
                self.assertFalse(on['frames'][0]['mask_is_ground_truth'])
                self.assertTrue((root/'on'/on['frames'][0]['road_overlay']).is_file())
                self.assertEqual(on['detections'][1]['road_warning'],'mask_missing_needs_review')
                for actual,original in zip(calls,originals):np.testing.assert_array_equal(actual,original)
                loader.reset_mock();calls.clear()
                off=inference.analyze_video(video,root/'off',duration=None,sample_fps=2)
                loader.assert_not_called()
                self.assertFalse(off['road_mask']['enabled'])
                self.assertNotIn('road_overlap',off['detections'][0])


class SegmentationAPITests(integration.VideoReviewIntegrationTest):
    # Use the same isolated real-app harness, without inheriting unrelated cases.
    test_integrated_browser_e2e = None
    test_job_review_report_rerun_and_legacy_guard = None
    test_permissions_and_negative_video = None
    test_upload_start_to_review_uses_existing_job_lifecycle = None

    def test_upload_segment_validation_and_reload(self):
        job,folder=self.make_job()
        cfg=self.client.get('/api/mvp-video/config').json()
        seg=cfg['segment_default'];self.assertTrue(seg)
        video=(folder/'source.video').read_bytes()
        bad=self.client.post('/api/mvp-video/upload',data={'road_mask_enabled':'true','segment_model':cfg['defaults']['CRACK'],'prepare_only':'true'},files={'file':('clip.mp4',video)})
        self.assertEqual(bad.status_code,422)
        with patch.object(api,'resolve_segment_model',side_effect=ValueError('missing')):
            self.assertEqual(self.client.post('/api/mvp-video/upload',data={'road_mask_enabled':'true'},files={'file':('clip.mp4',video)}).status_code,422)
        on=self.client.post('/api/mvp-video/upload',data={'road_mask_enabled':'true','segment_model':seg,'prepare_only':'true'},
            files={'file':('clip.mp4',video)},headers={'Idempotency-Key':'seg-fixture'})
        self.assertEqual(on.status_code,200,on.text)
        jid=on.json()['job_id'];api.JOBS.pop(jid)
        saved=self.client.get('/api/mvp-video/'+jid).json()
        self.assertTrue(saved['segment']['enabled']);self.assertEqual(saved['segment']['model']['id'],seg)
        replay=self.client.post('/api/mvp-video/upload',data={'road_mask_enabled':'true','segment_model':seg,'prepare_only':'true'},files={'file':('clip.mp4',video)},headers={'Idempotency-Key':'seg-fixture'})
        self.assertEqual(replay.status_code,200,replay.text);self.assertTrue(replay.json()['replayed'])
        self.assertEqual(self.client.post('/api/mvp-video/upload',data={'prepare_only':'true'},files={'file':('clip.mp4',video)},headers={'Idempotency-Key':'seg-fixture'}).status_code,409)
        with patch.object(api,'resolve_segment_model') as resolver:
            off=self.client.post('/api/mvp-video/upload',data={'road_mask_enabled':'false','prepare_only':'true'},files={'file':('clip.mp4',video)})
            self.assertEqual(off.status_code,200);resolver.assert_not_called()

    def test_segment_browser_reload(self):
        import socket, time, uvicorn
        job,folder=self.make_job()
        mask=np.zeros((80,100),np.uint8);mask[:,:40]=255
        cv2.imwrite(str(folder/'roadmask_00000000.png'),mask)
        cv2.imwrite(str(folder/'road_overlay_00000000.jpg'),np.full((80,100,3),(100,80,10),np.uint8))
        job['result']['road_mask']={'enabled':True,'model':{'name':'fixture','version':'test'}}
        job['result']['frames'][0].update(road_mask='roadmask_00000000.png',road_overlay='road_overlay_00000000.jpg',road_mask_status='predicted_unreviewed')
        job['result']['frames'][1]['road_mask_status']='missing_needs_review'
        job['result']['detections'][0]['road_warning']='outside_or_partial_road_mask'
        (folder/'analysis.json').write_text(json.dumps(job['result']),encoding='utf-8');store.save(api.RUNS,job)
        self.assertEqual(self.client.get(f"/api/mvp-video/{job['job_id']}/files/roadmask_00000000.png").status_code,200)
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        server=uvicorn.Server(uvicorn.Config(integration.application(),log_level='error'))
        thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
        try:
            for _ in range(100):
                if server.started:break
                time.sleep(.05)
            proc=subprocess.run(['node',str(Path(__file__).with_name('browser_road_seg_video.cjs')),f'http://127.0.0.1:{port}',job['job_id']],env=browser_env(),capture_output=True,text=True,timeout=60)
            self.assertEqual(proc.returncode,0,proc.stdout+'\n'+proc.stderr)
        finally:server.should_exit=True;thread.join(timeout=10);sock.close()


if __name__=='__main__':unittest.main()
