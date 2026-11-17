import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api import mvp_video as api
from src.inference import mvp_video as inference


class MVPVideo28Tests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(api.router)
        self.client = TestClient(app)

    def test_exact_po_models(self):
        self.assertEqual([m[2].name for m in inference.MODELS],
                         ["roadguard_crack_yolo11n_v1.pt", "best (1).pt"])
        self.assertEqual([m[0] for m in inference.MODELS], ["CRACK", "POTHOLE"])

    def test_wrong_mapping_fails_closed(self):
        from types import SimpleNamespace
        with patch.object(inference, "YOLO", return_value=SimpleNamespace(task="detect", names={0:"crack"})):
            with self.assertRaisesRegex(ValueError, "Pothole"):
                inference.load_models()

    def test_missing_checkpoint_no_fallback(self):
        with patch.object(inference, "MODELS", [("CRACK", "missing", Path("missing.pt"), {"crack"})]):
            with self.assertRaises(FileNotFoundError):
                inference.load_models()

    def test_pending_contract_does_not_process_upload(self):
        with patch.object(api, "LIMITS", None):
            self.assertEqual(self.client.post('/api/mvp-video/upload', files={"file":("v.mp4",b'x')}).status_code, 503)

    def test_invalid_video_releases_admission(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(api, "RUNS", Path(directory)), patch.object(api, "LIMITS", {"bytes":2,"seconds":1,"fps":1}):
            response = self.client.post('/api/mvp-video/upload', files={"file":("../v.mp4",b'123')})
            self.assertEqual(response.status_code, 422)
            self.assertFalse(api.LOCK.locked())
            self.assertFalse(list(Path(directory).rglob('source.video')))

    def test_failed_processing_exposes_error_and_releases_slot(self):
        job_id = 'a' * 32
        with tempfile.TemporaryDirectory() as directory, patch.object(api, "RUNS", Path(directory)):
            (Path(directory) / job_id).mkdir()
            api.JOBS[job_id] = {"job_id":job_id,"status":"QUEUED"}
            with patch.object(api, "analyze_video", side_effect=ValueError("secret-token")):
                api.execute(job_id, 'missing', {"seconds":1,"fps":1})
            job = api.JOBS.pop(job_id)
            self.assertEqual(job['status'], 'FAILED')
            self.assertNotIn('secret-token', str(job['error']))
            self.assertFalse(api.LOCK.locked())

    def test_report_requires_success_and_approved_config(self):
        api.JOBS['test-report'] = {"status":"FAILED"}
        try:
            with patch.object(api, "REPORT_ENABLED", False):
                self.assertEqual(self.client.post('/api/mvp-video/test-report/report').status_code, 503)
            with patch.object(api, "REPORT_ENABLED", True):
                self.assertEqual(self.client.post('/api/mvp-video/test-report/report').status_code, 409)
        finally:
            api.JOBS.pop('test-report')

    def test_source_file_is_never_public(self):
        api.JOBS['test-artifact'] = {"result":{"frames":[]}}
        try:
            self.assertEqual(self.client.get('/api/mvp-video/test-artifact/files/source.video').status_code,404)
        finally:
            api.JOBS.pop('test-artifact')

    def test_ai_report_sends_only_aggregates_and_saves_text(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        client = MagicMock()
        client.with_options.return_value = client
        client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Báo cáo kiểm thử tiếng Việt"))])
        job_id = 'b' * 32
        api.JOBS[job_id] = {"job_id":job_id,"status":"COMPLETED", "result":{
            "summary":{"counts":{"CRACK":1,"POTHOLE":2}}, "models":[{"label":"Crack V1", "path":"PRIVATE_PATH"}],
            "limitations":"Chưa có GT", "frames":[{"image":"PRIVATE_IMAGE"}]}}
        try:
            with tempfile.TemporaryDirectory() as directory, patch.object(api, 'RUNS', Path(directory)), patch.object(api, 'REPORT_ENABLED', True), patch.dict('os.environ', {'KDV_MODEL':'qwen-test','KDV_BASE_URL':'http://localhost:9999/v1'}), patch('src.curation.kdv_inspector.KDVInspector', return_value=SimpleNamespace(is_available=True,_client=client,model='qwen-test')):
                (Path(directory)/job_id).mkdir()
                response = self.client.post('/api/mvp-video/'+job_id+'/report')
                self.assertEqual(response.status_code,200)
                self.assertEqual((Path(directory)/job_id/'report_vi.txt').read_text(encoding='utf-8'), response.json()['text'])
                payload = str(client.chat.completions.create.call_args)
                self.assertNotIn('PRIVATE_PATH',payload)
                self.assertNotIn('PRIVATE_IMAGE',payload)
                self.assertIn('POTHOLE',payload)
        finally:
            api.JOBS.pop(job_id)


if __name__ == '__main__':
    unittest.main()
