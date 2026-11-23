"""Opt-in private worker runtime. Importing this module starts no work/server.

Operator entrypoint: uvicorn src.api.be_worker_runtime:create_app_from_env
--factory --host 127.0.0.1. No host binding is performed by either factory.
Mounted token files are read only; token values are never environment settings.
"""
import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
import threading

from .be_worker import create_app


async def _await_thread(action, *args, **kwargs):
    """Cancellation cannot orphan startup or release the lock before join."""
    pending = asyncio.create_task(asyncio.to_thread(action, *args, **kwargs))
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(pending)
            break
        except asyncio.CancelledError:
            if pending.cancelled():
                raise
            cancelled = True
        except BaseException:
            if cancelled:
                raise asyncio.CancelledError() from None
            raise
    if cancelled:
        raise asyncio.CancelledError()
    return result


def _absolute_path(value, *, existing=False):
    try:
        if not isinstance(value, (str, Path)) or not str(value):
            raise ValueError()
        path = Path(value)
        if not path.is_absolute() or (existing and not path.is_file()):
            raise ValueError()
        return path
    except (TypeError, ValueError, OSError):
        raise ValueError('WORKER_CONFIGURATION_INVALID') from None


def _read_token(path):
    try:
        with path.open('rb') as source:
            data = source.read(1025)
        if len(data) > 1024:
            raise ValueError()
        token = data.decode('ascii').rstrip('\r\n')
        if len(token) < 32 or any(ord(char) <= 32 or ord(char) >= 127 for char in token):
            raise ValueError()
        return token
    except (OSError, UnicodeError, ValueError):
        raise ValueError('WORKER_TOKEN_FILE_INVALID') from None


def create_runtime_app(*, data_root, token_file, checkpoint_path, ffmpeg, ffprobe,
                       runner_factory=None, poll_interval=.25):
    """Build authenticated transport; exclusive runner starts only in lifespan.

    Windows local mutable data must reside on D:. Linux paths must be absolute.
    Shutdown awaits current native model work: there is no unsafe thread kill,
    lock release while running, or falsely reported successful timed shutdown.
    The injected runner_factory is a mechanics-test seam, not real readiness.
    """
    root = _absolute_path(data_root)
    if os.name == 'nt' and (root.drive.lower() != 'd:' or root.resolve().drive.lower() != 'd:'):
        raise ValueError('WORKER_CONFIGURATION_INVALID')
    token_path = _absolute_path(token_file, existing=True)
    checkpoint = _absolute_path(checkpoint_path, existing=True)
    ffmpeg_path = _absolute_path(ffmpeg, existing=True)
    ffprobe_path = _absolute_path(ffprobe, existing=True)
    if type(poll_interval) not in (int, float) or not 0 < poll_interval <= 60:
        raise ValueError('WORKER_CONFIGURATION_INVALID')
    token = _read_token(token_path)
    app = create_app(root, token)
    app.state.worker_runner = None
    app.state.worker_thread = None
    stop = threading.Event()
    failed = threading.Event()

    def ready():
        runner = app.state.worker_runner
        thread = app.state.worker_thread
        return bool(runner is not None and runner.ready and thread is not None and
                    thread.is_alive() and not stop.is_set() and not failed.is_set())

    app.state.readiness_checker = ready

    @asynccontextmanager
    async def lifespan(application):
        # The transport owns storage helpers used by the runner. Keep imports
        # local to prevent a module cycle and model/dependency loading on import.
        from .be_worker_runner import WorkerRunner, FFmpegMedia
        factory = runner_factory or WorkerRunner
        runner = factory(application.state.data_root, application.state.store, checkpoint,
                         media=FFmpegMedia(ffmpeg_path, ffprobe_path))
        application.state.worker_runner = runner
        stop.clear()
        failed.clear()
        try:
            await _await_thread(runner.start, recover_running=True)
        except BaseException as exc:
            runner.close()
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise RuntimeError('WORKER_STARTUP_FAILED') from None

        def loop():
            try:
                while not stop.is_set():
                    application.state.store.expire_awaiting_input()
                    record = runner.run_once()
                    if record is None:
                        stop.wait(poll_interval)
            except Exception:
                # Raw model/storage errors may contain paths or configuration.
                # Readiness drops; do not emit those errors from thread logging.
                failed.set()
                runner.request_stop()

        thread = threading.Thread(target=loop, name='roadguard-private-worker', daemon=False)
        application.state.worker_thread = thread
        try:
            thread.start()
            yield
        finally:
            stop.set()
            runner.request_stop()
            try:
                if thread.ident is not None:
                    await _await_thread(thread.join)
            finally:
                runner.close()

    app.router.lifespan_context = lifespan
    return app


def create_app_from_env():
    """Uvicorn --factory target; all five paths are required, with no defaults."""
    fields = {'data_root': 'ROADGUARD_WORKER_DATA_ROOT',
              'token_file': 'ROADGUARD_WORKER_TOKEN_FILE',
              'checkpoint_path': 'ROADGUARD_WORKER_CHECKPOINT',
              'ffmpeg': 'ROADGUARD_WORKER_FFMPEG',
              'ffprobe': 'ROADGUARD_WORKER_FFPROBE'}
    settings = {key: os.environ.get(variable) for key, variable in fields.items()}
    if any(not value for value in settings.values()):
        raise ValueError('WORKER_CONFIGURATION_REQUIRED')
    return create_runtime_app(**settings)
