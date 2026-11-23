"""Private HTTP boundary exercises actual durable store and byte publication."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from src.api.be_worker import create_app

FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures/ai-worker-v1"
TOKEN = "test-only-service-credential-123456789"


class WorkerHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = create_app(self.root, TOKEN)
        self.app.state.capacity_checker = lambda *args: None
        self.client = TestClient(self.app)
        self.auth = {"Authorization": "Bearer " + TOKEN}
        self.payload = json.loads((FIXTURES / "admission.json").read_text())
        self.video = b"video-bytes"
        self.payload.update(inputBytes=len(self.video), inputSha256=hashlib.sha256(self.video).hexdigest())
        self.url = "/internal/v1/jobs/" + self.payload["attemptId"]

    def admit(self):
        return self.client.post("/internal/v1/jobs", json=self.payload, headers=self.auth)

    def upload(self, data=None, **headers):
        return self.client.put(self.url + "/input", content=self.video if data is None else data,
                               headers={**self.auth, "X-Content-SHA256": self.payload["inputSha256"], **headers})

    def test_all_routes_authenticate_before_parsing(self):
        for method, path in [("get", "/internal/v1/health"), ("post", "/internal/v1/jobs"),
                             ("get", self.url), ("put", self.url + "/input"),
                             ("get", self.url + "/result"), ("post", self.url + "/cancel"),
                             ("get", self.url + "/artifacts/" + self.payload["jobId"]),
                             ("get", "/docs"), ("get", "/unknown")]:
            with self.subTest(path=path):
                response = self.client.request(method, path, content=b"invalid")
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json(), {"code": "UNAUTHORIZED"})

    def test_token_strength_is_configuration_error(self):
        for token in ("short", "é" * 40, "x" * 31):
            with self.assertRaises(ValueError):
                create_app(self.root, token)

    def test_wrong_token_and_framework_errors_use_safe_codes(self):
        self.assertEqual(self.client.get("/internal/v1/health", headers={"Authorization": "Bearer wrong"}).status_code, 401)
        response = self.client.get("/unknown", headers=self.auth)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"code": "NOT_FOUND"})

    def test_admission_replay_conflict_and_safe_state(self):
        self.assertEqual(self.admit().status_code, 202)
        self.assertEqual(self.admit().status_code, 200)
        response = self.client.post("/internal/v1/jobs", json=dict(self.payload, inputWidth=1), headers=self.auth)
        self.assertEqual(response.status_code, 409)
        state = self.client.get(self.url, headers=self.auth).json()
        self.assertEqual(state["state"], "AWAITING_INPUT")
        self.assertNotIn("input_marker", state)
        self.assertNotIn("payload", state)
        self.assertNotIn("result", state)

    def test_json_decoder_rejects_duplicate_nonfinite_and_control_body_limit(self):
        for body in (b'{"sampleFps":1,"sampleFps":2}', b'{"sampleFps":NaN}', b"[]", b"x" * 65537):
            response = self.client.post("/internal/v1/jobs", content=body, headers=self.auth)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json(), {"code": "INVALID_INPUT"})

    def test_upload_checksum_size_headers_replay_and_cancel(self):
        self.admit()
        self.assertEqual(self.upload(b"x" * len(self.video)).status_code, 422)
        self.assertFalse((self.root / self.payload["attemptId"] / "input.mp4").exists())
        self.assertEqual(self.upload(self.video + b"x").status_code, 422)
        self.assertEqual(self.upload(**{"X-Content-SHA256": "a" * 64}).status_code, 422)
        self.assertEqual(self.upload().status_code, 200)
        self.assertEqual(self.upload().status_code, 200)
        self.assertEqual((self.root / self.payload["attemptId"] / "input.mp4").read_bytes(), self.video)
        state = self.client.get(self.url, headers=self.auth).json()
        self.assertEqual(state["state"], "QUEUED")
        self.assertEqual(self.client.get(self.url + "/result", headers=self.auth).status_code, 409)
        self.assertEqual(self.client.post(self.url + "/cancel", headers=self.auth).json()["state"], "CANCELLED")
        self.assertEqual(self.client.post(self.url + "/cancel", headers=self.auth).status_code, 200)

    def test_capacity_failure_has_safe_error(self):
        from src.api.be_worker_store import WorkerStoreError
        self.admit()
        def fail(*args):
            raise WorkerStoreError("DISK_BUDGET_EXCEEDED", 507)
        self.app.state.capacity_checker = fail
        self.assertEqual(self.upload().status_code, 507)

    def test_canonical_ids_and_artifact_allowlist(self):
        self.admit()
        self.assertEqual(self.client.get(self.url.upper(), headers=self.auth).status_code, 404)
        self.assertEqual(self.client.get(self.url + "/artifacts/input.mp4", headers=self.auth).status_code, 404)
        self.assertEqual(self.client.get(self.url + "/artifacts/" + self.payload["jobId"], headers=self.auth).status_code, 409)

    def test_actual_stream_bytes_are_bounded_even_with_matching_length_header(self):
        self.admit()
        response = self.upload(self.video + b"extra", **{"Content-Length": str(len(self.video))})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.app.state.store.get(self.payload["attemptId"])["state"], "AWAITING_INPUT")
        self.assertEqual(list((self.root / self.payload["attemptId"]).iterdir()), [])

    def test_published_input_without_marker_reconciles_only_after_verified_replay(self):
        self.admit()
        path = self.root / self.payload["attemptId"] / "input.mp4"
        path.parent.mkdir()
        path.write_bytes(self.video)
        self.assertEqual(self.upload().status_code, 200)
        self.assertEqual(self.app.state.store.get(self.payload["attemptId"])["state"], "QUEUED")
        path.write_bytes(b"tampered")
        self.assertEqual(self.upload().status_code, 422)
        self.assertEqual(path.read_bytes(), b"tampered")

    def test_concurrent_identical_uploads_publish_once_and_reconcile(self):
        self.admit()
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: self.upload().status_code, range(2)))
        self.assertEqual(statuses, [200, 200])
        directory = self.root / self.payload["attemptId"]
        self.assertEqual([path.name for path in directory.iterdir()], ["input.mp4"])
        self.assertEqual((directory / "input.mp4").read_bytes(), self.video)

    def test_default_capacity_checker_rejects_over_budget_reservation(self):
        from src.api.be_worker import check_capacity
        from src.api.be_worker_store import WorkerStoreError
        self.payload["inputBytes"] = 40 * 1024 ** 3
        self.admit()
        with self.assertRaises(WorkerStoreError) as caught:
            check_capacity(self.root, self.payload, self.app.state.store)
        self.assertEqual(caught.exception.code, "DISK_BUDGET_EXCEEDED")
        self.assertEqual(caught.exception.status_code, 507)

    def complete(self):
        self.admit()
        self.upload()
        self.app.state.store.claim_next()
        result = json.loads((FIXTURES / "result.json").read_text())
        result.update(self.payload)
        result["telemetry"]["sourceVideoSha256"] = self.payload["inputSha256"]
        artifact = result["rawArtifact"]
        content = b'{"synthetic":true}'
        artifact.update(bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
        path = self.root / self.payload["attemptId"] / "artifacts" / artifact["artifactId"]
        path.parent.mkdir()
        path.write_bytes(content)
        self.app.state.store.finish(self.payload["attemptId"], "COMPLETED", result=result)
        return result, path, content

    def test_completed_result_artifacts_enforce_manifest_hash_and_ownership(self):
        result, path, content = self.complete()
        self.assertEqual(self.client.get(self.url + "/result", headers=self.auth).json(), result)
        artifact_url = self.url + "/artifacts/" + path.name
        response = self.client.get(artifact_url, headers=self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, content)
        unknown = self.url + "/artifacts/" + self.payload["jobId"]
        (path.parent / self.payload["jobId"]).write_bytes(b"private")
        self.assertEqual(self.client.get(unknown, headers=self.auth).status_code, 404)
        path.write_bytes(b"corruption")
        self.assertEqual(self.client.get(artifact_url, headers=self.auth).status_code, 422)

    def test_symlinked_attempt_directory_is_rejected(self):
        self.admit()
        outside = self.root / "outside"
        outside.mkdir()
        link = self.root / self.payload["attemptId"]
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Host does not grant symlink creation")
        self.assertEqual(self.upload().status_code, 422)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
