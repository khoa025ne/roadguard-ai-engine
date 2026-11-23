"""Private single-owner FT95 runner; no public routes or implicit restart retry.

CPU is the default. Injected media/model implementations are test seams and do
not constitute real inference evidence. All subprocess outputs and work have
explicit bounds; native model prediction is cooperative only between frames.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid5

from .be_worker_contract import (SOURCE_CLASSES, ValidationError, normalized_bbox,
                                 seconds_to_ms, validate_result)
from .be_worker import _publish, _safe_path, _verify_file
from .be_worker_store import WorkerStoreError
from ..ingestion.embedded_srt import ExtractionError, extract_srt

FT95_SHA256 = 'bc14e1f0378310640d0e04583982ebb377475211d6d42837f2db494e32ed95a0'
PREPROCESSING_VERSION = 'ffmpeg-pts-v1'
CONFIG_VERSION = 'ft95-cpu-v1'
FT95_CHECKPOINT_CLASSES = ('Alligator crack', 'Longitudinal crack', 'Oblique crack',
                          'Pothole', 'Repair', 'Transverse crack')


class RunnerError(RuntimeError):
    pass


def _hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded_command(arguments, check, *, timeout=120, max_output=32*1024*1024):
    """File-backed capture avoids an unbounded pipe; kill and reap on all exits."""
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(arguments, stdout=output, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                check()
                if time.monotonic() >= deadline:
                    raise RunnerError('MEDIA_TIMEOUT')
                if os.fstat(output.fileno()).st_size > max_output:
                    raise RunnerError('MEDIA_RESOURCE_LIMIT')
                time.sleep(.05)
            if process.returncode:
                raise RunnerError('MEDIA_DECODE_FAILED')
            if os.fstat(output.fileno()).st_size > max_output:
                raise RunnerError('MEDIA_RESOURCE_LIMIT')
            output.seek(0)
            return output.read()
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()


class FrameTimeline(list):
    """Video-relative PTS with the exact container origin/source PTS retained."""
    def __init__(self, origin_seconds):
        super().__init__()
        self.origin_seconds = origin_seconds
        self.source_pts = {}


class FFmpegMedia:
    def __init__(self, ffmpeg='ffmpeg', ffprobe='ffprobe'):
        self.ffmpeg, self.ffprobe = str(ffmpeg), str(ffprobe)

    def probe(self, video, check):
        metadata = json.loads(_bounded_command([self.ffprobe, '-v', 'error', '-show_streams',
            '-show_format', '-of', 'json', str(video)], check, max_output=1024*1024))
        streams = [s for s in metadata['streams'] if s.get('codec_type') == 'video']
        if len(streams) != 1:
            raise RunnerError('INPUT_METADATA_MISMATCH')
        stream = streams[0]
        duration = seconds_to_ms(float(metadata['format']['duration']))
        # FFmpeg subtitle extraction (without -copyts) subtracts this same
        # input origin. Do not rebase to the first video frame: that would erase
        # a real video/subtitle gap when another stream starts earlier.
        origin_text = metadata['format'].get('start_time')
        try:
            origin = Decimal(origin_text)
            if not origin.is_finite():
                raise InvalidOperation
        except (InvalidOperation, TypeError, ValueError):
            raise RunnerError('INVALID_FRAME_TIMESTAMP') from None
        width, height = int(stream['width']), int(stream['height'])
        if width * height > 16_777_216:
            raise RunnerError('MEDIA_RESOURCE_LIMIT')
        # One record per decoded frame. nb_frames/r_frame_rate are never clocks.
        raw = _bounded_command([self.ffprobe, '-v', 'error', '-select_streams', 'v:0',
            '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time',
            '-of', 'json', str(video)], check)
        rows = json.loads(raw)['frames']
        pts = FrameTimeline(origin_text)
        previous = -1.0
        for index, row in enumerate(rows):
            try:
                source_text = row['best_effort_timestamp_time']
                source = Decimal(source_text)
                if not source.is_finite():
                    raise InvalidOperation
                timestamp = float(source - origin)
            except (KeyError, InvalidOperation, TypeError, ValueError, OverflowError):
                raise RunnerError('INVALID_FRAME_TIMESTAMP') from None
            if not math.isfinite(timestamp) or timestamp < 0 or timestamp <= previous:
                raise RunnerError('INVALID_FRAME_TIMESTAMP')
            if seconds_to_ms(timestamp) > duration:
                raise RunnerError('INVALID_FRAME_TIMESTAMP')
            pts.append((index, timestamp))
            pts.source_pts[index] = source_text
            previous = timestamp
        if not pts:
            raise RunnerError('NO_VIDEO_FRAMES')
        return width, height, duration, pts

    def frames(self, video, directory, selected, check):
        # Use source frame ordinals from the same decoder's PTS probe. select
        # changes no timestamp; passthrough prohibits duplicate/drop synthesis.
        expression = '+'.join(f'eq(n\\,{index})' for index, _ in selected)
        if os.name == 'nt' and len(expression) > 24000:
            raise RunnerError('MEDIA_RESOURCE_LIMIT')
        pattern = directory / 'frame-%06d.jpg'
        _bounded_command([self.ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin',
            '-noautorotate', '-copyts', '-threads', '1', '-i', str(video), '-map', '0:v:0',
            '-vf', f'select={expression}', '-fps_mode', 'passthrough', '-threads', '1',
            '-frames:v', str(len(selected)), '-q:v', '2', '-n', str(pattern)], check, timeout=600)
        paths = sorted(directory.glob('frame-*.jpg'))
        if len(paths) != len(selected):
            raise RunnerError('FRAME_EXTRACTION_MISMATCH')
        for (_, timestamp), path in zip(selected, paths):
            check()
            yield timestamp, path


class FT95Model:
    def __init__(self, checkpoint):
        from ultralytics import YOLO
        self.model = YOLO(str(checkpoint))
        self.checkpoint_names = self.model.names
        if self.checkpoint_names != dict(enumerate(FT95_CHECKPOINT_CLASSES)):
            raise RunnerError('UNKNOWN_SOURCE_CLASS')
        # Explicit pinned-checkpoint adapter, never a catch-all case folding or
        # crack-class fallback. Preserve original spelling in raw predictions.
        self.names = dict(enumerate(SOURCE_CLASSES))

    def infer(self, frame):
        from PIL import Image
        # Published artifacts deliberately have UUID-only filenames. Passing a
        # PIL image avoids Ultralytics' extension-based filesystem discovery.
        with Image.open(frame) as image:
            predictions = self.model.predict(source=image.convert('RGB'), device='cpu', verbose=False,
                imgsz=640, conf=.25, iou=.7, max_det=1000, save=False)
        result = []
        for prediction in predictions:
            for box in prediction.boxes:
                class_id = int(box.cls.item())
                if class_id not in self.names:
                    raise RunnerError('UNKNOWN_SOURCE_CLASS')
                label = self.names[class_id]
                result.append({'sourceClass': label, 'confidence': float(box.conf.item()),
                               'checkpointClassName': self.checkpoint_names[class_id],
                               'xyxy': [float(v) for v in box.xyxy[0].tolist()]})
        return result


class WorkerRunner:
    def __init__(self, root, store, checkpoint_path, *, checkpoint_sha256=FT95_SHA256,
                 preprocessing_version=PREPROCESSING_VERSION, config_version=CONFIG_VERSION,
                 model_factory=None, media=None, telemetry_extractor=extract_srt,
                 max_attempt_seconds=3600):
        self.root = Path(root).resolve()
        self.store = store
        self.checkpoint = Path(checkpoint_path).resolve()
        self.checkpoint_sha256 = checkpoint_sha256
        self.preprocessing_version = preprocessing_version
        self.config_version = config_version
        self.model_factory = model_factory or FT95Model
        self.media = media or FFmpegMedia()
        self.telemetry_extractor = telemetry_extractor
        if max_attempt_seconds <= 0:
            raise ValueError('Positive attempt timeout required')
        self.max_attempt_seconds = max_attempt_seconds
        self.model = None
        self._lock = None
        self._busy = threading.Lock()
        self._stop = threading.Event()

    @property
    def ready(self):
        return self._lock is not None and self.model is not None and not self._stop.is_set()

    def start(self, *, recover_running=False):
        """Acquire OS lock, validate/load model once, optionally interrupt old work."""
        if self.ready:
            return self
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = (self.root / '.runner.lock').open('a+b')
        try:
            self._lock.seek(0)
            if os.name == 'nt':
                import msvcrt
                if self._lock.read(1) == b'':
                    self._lock.write(b'0')
                    self._lock.flush()
                self._lock.seek(0)
                msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lock.close()
            self._lock = None
            raise RunnerError('RUNNER_ALREADY_ACTIVE') from None
        try:
            if not self.checkpoint.is_file():
                raise RunnerError('MODEL_MISSING')
            if _hash_file(self.checkpoint) != self.checkpoint_sha256:
                raise RunnerError('MODEL_HASH_MISMATCH')
            self.model = self.model_factory(self.checkpoint)
            names = self.model.names
            values = list(names.values()) if isinstance(names, dict) else list(names)
            if len(values) != 6 or set(values) != set(SOURCE_CLASSES):
                raise RunnerError('UNKNOWN_SOURCE_CLASS')
            if recover_running:
                self.store.recover_running()
            self._stop.clear()
            return self
        except BaseException:
            self.close()
            raise

    def request_stop(self):
        """Cooperative: caller must join active run_once before close releases lock."""
        self._stop.set()

    def close(self):
        self.request_stop()
        with self._busy:
            self.model = None
            if self._lock is not None:
                self._lock.close()
                self._lock = None

    def run_once(self):
        """Run one FIFO verified record; return durable terminal record or None."""
        if not self.ready:
            raise RunnerError('RUNNER_NOT_READY')
        with self._busy:
            if not self.ready:
                raise RunnerError('RUNNER_NOT_READY')
            record = self.store.claim_next()
            if record is None:
                return None
            attempt = record['attemptId']
            deadline = time.monotonic() + self.max_attempt_seconds
            def check():
                if self._stop.is_set():
                    raise RunnerError('RUNNER_STOPPED')
                if self.store.get(attempt)['cancellation_requested']:
                    raise RunnerError('CANCELLED')
                if time.monotonic() >= deadline:
                    raise RunnerError('ATTEMPT_TIMEOUT')
            try:
                result = self._execute(record, check)
                check()
                return self.store.finish(attempt, 'COMPLETED', result=result)
            except Exception as exc:
                if isinstance(exc, RunnerError):
                    code = str(exc)
                elif isinstance(exc, WorkerStoreError):
                    code = exc.code
                elif isinstance(exc, ValidationError):
                    code = 'INVALID_MODEL_OUTPUT'
                else:
                    code = 'INFERENCE_FAILED'
                if self.store.get(attempt)['cancellation_requested']:
                    code = 'CANCELLED'
                state = 'CANCELLED' if code == 'CANCELLED' else ('INTERRUPTED' if code == 'RUNNER_STOPPED' else 'FAILED')
                return self.store.finish(attempt, state, error_code=code)

    def _execute(self, record, check):
        payload = record['payload']
        attempt = payload['attemptId']
        check()
        if payload['checkpointSha256'] != self.checkpoint_sha256:
            raise RunnerError('MODEL_HASH_MISMATCH')
        if (payload['preprocessingVersion'] != self.preprocessing_version or
                payload['configVersion'] != self.config_version):
            raise RunnerError('CONFIGURATION_MISMATCH')
        video = _safe_path(self.root, attempt, 'input.mp4')
        if record['input_marker'] != str(video):
            raise RunnerError('UNVERIFIED_INPUT')
        _verify_file(video, {'bytes': payload['inputBytes'], 'sha256': payload['inputSha256']})
        width, height, duration, pts = self.media.probe(video, check)
        if (width, height, duration) != (payload['inputWidth'], payload['inputHeight'], payload['inputDurationMs']):
            raise RunnerError('INPUT_METADATA_MISMATCH')
        selected = []
        next_time = 0.
        previous = -1.
        for index, timestamp in pts:
            if not math.isfinite(timestamp) or timestamp < 0 or timestamp <= previous or seconds_to_ms(timestamp) > duration:
                raise RunnerError('INVALID_FRAME_TIMESTAMP')
            previous = timestamp
            if timestamp + 1e-9 >= next_time:
                selected.append((index, timestamp))
                # Grid schedule: each observation retains its actual decoded PTS.
                next_time = (math.floor(timestamp * payload['sampleFps']) + 1) / payload['sampleFps']
        if not selected:
            raise RunnerError('NO_VIDEO_FRAMES')
        if len(selected) > payload['maxFrames']:
            raise RunnerError('FRAME_LIMIT_EXCEEDED')
        directory = _safe_path(self.root, attempt, 'artifacts')
        directory.mkdir(exist_ok=True)
        namespace = UUID(attempt)
        def identity(name):
            return str(uuid5(namespace, name))
        def publish(path, name, media_type, frame=False):
            artifact_id = identity(name)
            destination = _safe_path(self.root, attempt, 'artifacts', artifact_id)
            size = path.stat().st_size
            if size <= 0 or size > (width*height*3+65536 if frame else 64*1024*1024):
                raise RunnerError('ARTIFACT_RESOURCE_LIMIT')
            metadata = {'artifactId': artifact_id, 'sha256': _hash_file(path), 'bytes': size, 'mediaType': media_type}
            with path.open('r+b') as source:
                os.fsync(source.fileno())
            try:
                _publish(path, destination)
            except FileExistsError:
                _verify_file(destination, metadata)
            if frame:
                metadata.update(width=width, height=height)
            return metadata
        result = dict(payload, resultId=identity('result'), frameArtifacts=[], detections=[],
            telemetry=None, roadMaskStatus='NOT_AVAILABLE', limitations=['ROAD_MASK_NOT_AVAILABLE'])
        with tempfile.TemporaryDirectory(prefix='.runner-', dir=video.parent) as work:
            work = Path(work)
            observed = []
            from PIL import Image
            for ordinal, (timestamp, frame) in enumerate(self.media.frames(video, work, selected, check)):
                check()
                if ordinal >= len(selected) or timestamp != selected[ordinal][1]:
                    raise RunnerError('FRAME_EXTRACTION_MISMATCH')
                with Image.open(frame) as image:
                    if image.format != 'JPEG' or image.size != (width, height):
                        raise RunnerError('FRAME_EXTRACTION_MISMATCH')
                    image.verify()
                artifact = publish(frame, f'frame:{ordinal}', 'image/jpeg', frame=True)
                result['frameArtifacts'].append(artifact)
                predictions = self.model.infer(directory / artifact['artifactId'])
                check()
                if not isinstance(predictions, list) or len(predictions) > 1000:
                    raise RunnerError('INVALID_MODEL_OUTPUT')
                for index, prediction in enumerate(predictions):
                    if prediction['sourceClass'] not in SOURCE_CLASSES:
                        raise RunnerError('UNKNOWN_SOURCE_CLASS')
                    detection = {'detectionId': identity(f'detection:{ordinal}:{index}'),
                        'frameArtifactId': artifact['artifactId'], 'timestampMs': seconds_to_ms(timestamp),
                        'sourceClass': prediction['sourceClass'], 'confidence': prediction['confidence'],
                        'bbox': normalized_bbox(prediction['xyxy'], width, height)}
                    result['detections'].append(detection)
                observation = {'timestampSeconds': timestamp, 'frameArtifactId': artifact['artifactId'],
                               'pixelPredictions': predictions}
                if isinstance(pts, FrameTimeline):
                    observation['sourcePtsSeconds'] = pts.source_pts[selected[ordinal][0]]
                observed.append(observation)
            if len(observed) != len(selected):
                raise RunnerError('FRAME_EXTRACTION_MISMATCH')
            telemetry = {'source': 'NONE', 'outcome': 'EXTRACTION_FAILED',
                'sourceVideoSha256': payload['inputSha256'], 'streamIndex': None,
                'extractorVersion': 'embedded-srt-v1', 'srtArtifact': None}
            srt = work / 'telemetry.srt'
            try:
                options = {'timeout': 60, 'max_bytes': 16*1024*1024}
                if isinstance(self.media, FFmpegMedia):
                    options.update(ffmpeg=self.media.ffmpeg, ffprobe=self.media.ffprobe)
                proof = self.telemetry_extractor(video, srt, **options)
                telemetry.update(source='EMBEDDED', outcome='EXTRACTED_VALID', streamIndex=proof['stream_index'],
                    srtArtifact=publish(srt, 'telemetry', 'application/x-subrip'))
            except ExtractionError as exc:
                code = str(exc)
                telemetry['outcome'] = code if code in {'NO_SUBTITLE_STREAM', 'UNSUPPORTED_STREAM',
                    'INVALID_TELEMETRY', 'TELEMETRY_AMBIGUOUS'} else 'EXTRACTION_FAILED'
            except (OSError, ValueError, KeyError, subprocess.SubprocessError):
                pass
            check()
            result['telemetry'] = telemetry
            if telemetry['outcome'] != 'EXTRACTED_VALID':
                result['limitations'].append('MEASURED_TELEMETRY_NOT_AVAILABLE')
            raw = work / 'raw.json'
            raw.write_text(json.dumps({'contractVersion': payload['contractVersion'], 'admission': payload,
                'resultId': result['resultId'], 'observations': observed, 'detections': result['detections'],
                'timeline': {'origin': 'format.start_time', 'originSeconds': pts.origin_seconds,
                             'timestampUnit': 'video-relative-seconds'} if isinstance(pts, FrameTimeline) else None,
                'telemetry': telemetry, 'roadMaskStatus': result['roadMaskStatus'], 'limitations': result['limitations']},
                sort_keys=True, separators=(',', ':'), allow_nan=False), encoding='utf-8')
            result['rawArtifact'] = publish(raw, 'raw', 'application/json')
            return validate_result(result, payload)
