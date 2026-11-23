"""Lifespan mechanics with a fake runner, not model/inference evidence."""
import os
import json
import asyncio
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from src.api.be_worker import create_app
from src.api import be_worker_runtime as runtime

TOKEN = 'runtime-test-only-secret-1234567890'


class FakeRunner:
    def __init__(self, root, store, checkpoint, **options):
        self.store = store
        self.ready = False
        self.stop = threading.Event()
        self.ran = threading.Event()
        self.events = []
        self.crash = False

    def start(self, *, recover_running=False):
        self.events.append(('start', recover_running))
        if recover_running:
            self.store.recover_running()
        self.ready = True

    def run_once(self):
        self.ran.set()
        if self.crash:
            raise RuntimeError('sensitive-detail-not-for-health')
        self.events.append(('run', None))
        self.stop.wait(.01)
        self.events.append(('run-exit', None))
        return None

    def request_stop(self):
        self.events.append(('stop', None))
        self.stop.set()

    def close(self):
        self.events.append(('close', None))
        self.ready = False


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        directory = 'D:/RoadGuard-AI-LocalTest' if os.name == 'nt' else None
        self.temp = tempfile.TemporaryDirectory(dir=directory, prefix='runtime-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.secret = self.root / 'token-file'
        self.secret.write_text(TOKEN + '\n')
        self.model = self.root / 'checkpoint.pt'
        self.model.write_bytes(b'fake-checkpoint')
        self.binary = self.root / 'media-tool'
        self.binary.write_bytes(b'fake-binary')
        self.instances = []
        def factory(*args, **kwargs):
            runner = FakeRunner(*args, **kwargs)
            self.instances.append(runner)
            return runner
        self.options = dict(data_root=self.root / 'data', token_file=self.secret,
            checkpoint_path=self.model, ffmpeg=self.binary, ffprobe=self.binary,
            runner_factory=factory, poll_interval=.01)
        self.auth = {'Authorization': 'Bearer ' + TOKEN}

    def test_base_factory_stays_model_free(self):
        app = create_app(self.root / 'base', TOKEN)
        with TestClient(app) as client:
            self.assertEqual(client.get('/internal/v1/health', headers=self.auth).status_code, 200)
        self.assertEqual(self.instances, [])

    def test_runtime_starts_only_in_lifespan_and_joins_before_close(self):
        app = runtime.create_runtime_app(**self.options)
        self.assertEqual(self.instances, [])
        with TestClient(app) as client:
            runner = self.instances[0]
            self.assertTrue(runner.ran.wait(2))
            self.assertEqual(runner.events[0], ('start', True))
            self.assertEqual(client.get('/internal/v1/health', headers=self.auth).json(), {'status': 'ok'})
            self.assertTrue(app.state.worker_thread.is_alive())
            self.assertEqual(client.get('/internal/v1/health').status_code, 401)
        self.assertFalse(app.state.worker_thread.is_alive())
        self.assertEqual(runner.events[-1], ('close', None))
        self.assertLess(runner.events.index(('stop', None)), len(runner.events)-1)

    def test_dead_background_thread_is_not_ready_and_leaks_no_exception(self):
        factory = self.options['runner_factory']
        def crashing(*args, **kwargs):
            runner = factory(*args, **kwargs)
            runner.crash = True
            return runner
        self.options['runner_factory'] = crashing
        app = runtime.create_runtime_app(**self.options)
        with TestClient(app) as client:
            self.instances[0].ran.wait(2)
            app.state.worker_thread.join(2)
            response = client.get('/internal/v1/health', headers=self.auth)
            self.assertEqual((response.status_code, response.json()), (503, {'code': 'WORKER_NOT_READY'}))
            self.assertNotIn('sensitive', response.text)

    def test_startup_failure_is_safe_and_closes_runner(self):
        factory = self.options['runner_factory']
        def broken(*args, **kwargs):
            runner = factory(*args, **kwargs)
            def fail(**kwargs):
                raise RuntimeError('sensitive-startup-detail')
            runner.start = fail
            return runner
        self.options['runner_factory'] = broken
        app = runtime.create_runtime_app(**self.options)
        with self.assertRaisesRegex(RuntimeError, '^WORKER_STARTUP_FAILED$'):
            with TestClient(app):
                self.fail('startup must not succeed')
        self.assertEqual(self.instances[0].events[-1], ('close', None))

    def test_lifespan_recovers_uncertain_running_work_before_loop(self):
        app = runtime.create_runtime_app(**self.options)
        fixtures = Path(__file__).resolve().parents[3] / 'tests/fixtures/ai-worker-v1'
        payload = json.loads((fixtures / 'admission.json').read_text())
        app.state.store.admit(payload)
        app.state.store.mark_input_verified(payload['attemptId'], 'verified-marker')
        app.state.store.claim_next()
        with TestClient(app):
            self.assertEqual(app.state.store.get(payload['attemptId'])['state'], 'INTERRUPTED')

    def test_live_thread_with_unready_model_returns_503(self):
        app = runtime.create_runtime_app(**self.options)
        with TestClient(app) as client:
            self.instances[0].ready = False
            self.assertTrue(app.state.worker_thread.is_alive())
            self.assertEqual(client.get('/internal/v1/health', headers=self.auth).status_code, 503)

    def test_cancelling_async_wait_still_joins_owned_native_work(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        def native_work():
            entered.set()
            release.wait(2)
            finished.set()
        async def check():
            task = asyncio.create_task(runtime._await_thread(native_work))
            while not entered.is_set():
                await asyncio.sleep(.001)
            task.cancel()
            asyncio.get_running_loop().call_later(.01, task.cancel)
            asyncio.get_running_loop().call_later(.1, release.set)
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(finished.is_set())
        asyncio.run(check())

    def test_env_is_explicit_and_token_file_never_becomes_environment_token(self):
        values = {'ROADGUARD_WORKER_DATA_ROOT': str(self.root/'env-data'),
            'ROADGUARD_WORKER_TOKEN_FILE': str(self.secret),
            'ROADGUARD_WORKER_CHECKPOINT': str(self.model),
            'ROADGUARD_WORKER_FFMPEG': str(self.binary),
            'ROADGUARD_WORKER_FFPROBE': str(self.binary)}
        with patch.dict(os.environ, values, clear=True):
            app = runtime.create_app_from_env()
            self.assertIsNotNone(app)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'WORKER_CONFIGURATION_REQUIRED'):
                runtime.create_app_from_env()
        self.assertEqual(self.instances, [])

    def test_relative_paths_and_bad_secret_fail_without_value_echo(self):
        for field in ('data_root', 'token_file', 'checkpoint_path', 'ffmpeg', 'ffprobe'):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, '^WORKER_CONFIGURATION_INVALID$'):
                    runtime.create_runtime_app(**dict(self.options, **{field: 'relative-sensitive-path'}))
        self.secret.write_bytes(b'x' * 4096)
        with self.assertRaisesRegex(ValueError, '^WORKER_TOKEN_FILE_INVALID$'):
            runtime.create_runtime_app(**self.options)


if __name__ == '__main__':
    unittest.main()
