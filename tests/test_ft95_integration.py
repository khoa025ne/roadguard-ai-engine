import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api import mvp_video as api
from src.api import video_job_store as store
from src.inference import video_models as models


class FT95Tests(unittest.TestCase):
    def test_unified_selection_runs_one_model_and_legacy_remains_selectable(self):
        unified={'id':'ft','task':'ROAD_DAMAGE','status':'available','name':'ft.pt'}
        legacy=[{'id':t,'task':t,'status':'available','name':t+'.pt'} for t in ['CRACK','POTHOLE']]
        with patch.object(models,'discover_models',return_value={'models':[unified]+legacy}),patch.object(models,'model_directory',return_value=Path.cwd()):
            self.assertEqual(len(models.resolve_models({'CRACK':'ft','POTHOLE':'ft'})),1)
            self.assertEqual(len(models.resolve_models({'CRACK':'CRACK','POTHOLE':'POTHOLE'})),2)
            with self.assertRaisesRegex(ValueError,'MODEL_UNAVAILABLE'):models.resolve_models({'CRACK':'ft','POTHOLE':'POTHOLE'})

    def test_review_revisions_survive_recovery_and_approved_is_immutable(self):
        with tempfile.TemporaryDirectory() as td,patch.object(api,'RUNS',Path(td)),patch.object(api,'JOBS',{}):
            job={'job_id':uuid.uuid4().hex,'status':'COMPLETED','result':{'detections':[{'class_name':'Pothole','confidence':.7}]}}
            store.save(api.RUNS,job)
            app=FastAPI();app.include_router(api.router);client=TestClient(app)
            url=f'/api/mvp-video/{job["job_id"]}/review'
            self.assertEqual(client.post(url,json={'detection_index':5,'status':'approved'}).status_code,422)
            a=client.post(url,json={'detection_index':0,'status':'pending_review'});self.assertEqual(a.status_code,200)
            b=client.post(url,json={'detection_index':0,'status':'approved'});self.assertEqual(b.status_code,200)
            self.assertEqual(b.json()['previous_revision'],a.json()['id'])
            api.JOBS.clear()
            self.assertEqual(client.post(url,json={'detection_index':0,'status':'pending_review'}).status_code,409)
            saved=store.read(api.RUNS,job['job_id'])
            self.assertEqual(saved['result'],job['result'])
            self.assertEqual(saved['reviews']['0']['status'],'approved')
            self.assertEqual(len(list((api.RUNS/job['job_id']).glob('review_*.json'))),2)


if __name__=='__main__':unittest.main()
