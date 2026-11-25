"""Mock mechanics tests: these do not certify checkpoint inference."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from src.api import be_worker_runner as runner
from src.api.be_worker_contract import SOURCE_CLASSES, validate_result
from src.api.be_worker_store import WorkerStore
from src.ingestion.embedded_srt import ExtractionError


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.store = WorkerStore(self.root / 'worker.sqlite3')
        self.checkpoint = self.root / 'model.pt'
        self.checkpoint.write_bytes(b'mock-checkpoint-not-real-model')
        self.digest = hashlib.sha256(self.checkpoint.read_bytes()).hexdigest()
        self.model = Mock(names=dict(enumerate(SOURCE_CLASSES)))
        self.model.infer.return_value = [{'sourceClass': 'repair', 'confidence': .9, 'xyxy': [10, 20, 50, 60]}]
        self.media = Mock()
        self.media.probe.return_value = (100, 80, 1000, [(0, 0.0), (1, .41), (2, .83)])
        def frames(video, directory, selected, check):
            from PIL import Image
            for index, timestamp in selected:
                path = directory / f'{index}.jpg'
                Image.new('RGB', (100, 80)).save(path)
                yield timestamp, path
        self.media.frames.side_effect = frames
        self.extractor = Mock(side_effect=ExtractionError('NO_SUBTITLE_STREAM'))
        self.worker = runner.WorkerRunner(self.root, self.store, self.checkpoint,
            checkpoint_sha256=self.digest, model_factory=lambda _: self.model,
            media=self.media, telemetry_extractor=self.extractor)
        self.addCleanup(self.worker.close)
        ids = {key: str(uuid4()) for key in ('projectId', 'jobId', 'attemptId', 'datasetId', 'sourceVideoFileId', 'modelVersionId')}
        self.payload = dict(ids, contractVersion='rg-ai-worker-v1', manifestHash='a'*64,
            checkpointSha256=self.digest, preprocessingVersion='ffmpeg-pts-v1', configVersion='ft95-cpu-v1',
            inputSha256=hashlib.sha256(b'video').hexdigest(), inputBytes=5, inputWidth=100,
            inputHeight=80, inputDurationMs=1000, sampleFps=2., maxFrames=3)

    def queue(self):
        self.store.admit(self.payload)
        path = self.root / self.payload['attemptId'] / 'input.mp4'
        path.parent.mkdir()
        path.write_bytes(b'video')
        self.store.mark_input_verified(self.payload['attemptId'], str(path))

    def test_completion_preserves_actual_pts_geometry_and_replay(self):
        self.queue()
        predictions = self.model.infer.return_value
        def infer(frame):
            self.assertTrue(Path(frame).is_file())
            return predictions
        self.model.infer.side_effect = infer
        self.worker.start()
        saved = self.worker.run_once()
        self.assertEqual(saved['state'], 'COMPLETED')
        result = validate_result(saved['result'], self.payload)
        self.assertEqual([d['timestampMs'] for d in result['detections']], [0, 830])
        self.assertEqual(result['detections'][0]['bbox'], [.1, .25, .4, .5])
        self.assertEqual(result['detections'][0]['sourceClass'], 'repair')
        self.assertEqual(result['telemetry']['sourceVideoSha256'], self.payload['inputSha256'])
        self.assertEqual(result['telemetry']['outcome'], 'NO_SUBTITLE_STREAM')
        for artifact in [result['rawArtifact'], *result['frameArtifacts']]:
            data = (self.root / self.payload['attemptId'] / 'artifacts' / artifact['artifactId']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), artifact['sha256'])
        self.assertIsNone(self.worker.run_once())
        self.assertEqual(self.store.admit(self.payload)[0]['result'], result)
        self.assertEqual(self.model.infer.call_count, 2)

    def test_raw_evidence_retains_absolute_pts_and_container_origin(self):
        pts = runner.FrameTimeline('10.125000')
        pts.extend([(0, 0.), (1, .41), (2, .83)])
        pts.source_pts.update({0: '10.125000', 1: '10.535000', 2: '10.955000'})
        self.media.probe.return_value = (100, 80, 1000, pts)
        self.queue(); self.worker.start()
        saved = self.worker.run_once()
        self.assertEqual(saved['state'], 'COMPLETED')
        result = saved['result']
        self.assertEqual([d['timestampMs'] for d in result['detections']], [0, 830])
        raw = json.loads((self.root / self.payload['attemptId'] / 'artifacts' / result['rawArtifact']['artifactId']).read_text())
        self.assertEqual(raw['timeline'], {'origin': 'format.start_time', 'originSeconds': '10.125000',
                                          'timestampUnit': 'video-relative-seconds'})
        self.assertEqual([r['sourcePtsSeconds'] for r in raw['observations']], ['10.125000', '10.955000'])

    def test_bad_geometry_fails_without_completed_result(self):
        self.queue()
        self.model.infer.return_value[0]['xyxy'] = [-1, 2, 3, 4]
        self.worker.start()
        saved = self.worker.run_once()
        self.assertEqual((saved['state'], saved['error_code']), ('FAILED', 'INVALID_MODEL_OUTPUT'))
        self.assertIsNone(saved['result'])

    def test_metadata_mismatch_never_runs_model(self):
        self.queue()
        self.media.probe.return_value = (99, 80, 1000, [(0, 0.)])
        self.worker.start()
        self.assertEqual(self.worker.run_once()['error_code'], 'INPUT_METADATA_MISMATCH')
        self.model.infer.assert_not_called()

    def test_readiness_rejects_hash_and_class_mismatch(self):
        self.checkpoint.write_bytes(b'changed')
        with self.assertRaisesRegex(runner.RunnerError, 'MODEL_HASH_MISMATCH'):
            self.worker.start()
        self.checkpoint.write_bytes(b'mock-checkpoint-not-real-model')
        self.model.names = {0: 'CRACK'}
        with self.assertRaisesRegex(runner.RunnerError, 'UNKNOWN_SOURCE_CLASS'):
            self.worker.start()

    def test_exclusive_lock_and_explicit_recovery(self):
        self.queue()
        self.store.claim_next()
        self.worker.start()
        self.assertEqual(self.store.get(self.payload['attemptId'])['state'], 'RUNNING')
        other = runner.WorkerRunner(self.root, self.store, self.checkpoint, checkpoint_sha256=self.digest,
            model_factory=lambda _: self.model)
        with self.assertRaisesRegex(runner.RunnerError, 'RUNNER_ALREADY_ACTIVE'):
            other.start(recover_running=True)
        self.worker.close()
        self.worker.start(recover_running=True)
        self.assertEqual(self.store.get(self.payload['attemptId'])['state'], 'INTERRUPTED')

    def test_cancel_after_inference_never_publishes_completion(self):
        self.queue()
        self.model.infer.side_effect = lambda _: self.store.request_cancel(self.payload['attemptId']) or []
        self.worker.start()
        self.assertEqual(self.worker.run_once()['state'], 'CANCELLED')

    def test_cancellation_committed_before_finish_wins_atomically(self):
        self.queue()
        self.store.claim_next()
        self.store.request_cancel(self.payload['attemptId'])
        saved = self.store.finish(self.payload['attemptId'], 'COMPLETED', result={'unused': True})
        self.assertEqual((saved['state'], saved['result']), ('CANCELLED', None))

    def test_frame_limit_fails_instead_of_silent_truncation(self):
        self.payload['maxFrames'] = 1
        self.queue()
        self.worker.start()
        self.assertEqual(self.worker.run_once()['error_code'], 'FRAME_LIMIT_EXCEEDED')
        self.model.infer.assert_not_called()

    def test_verified_input_is_rehashed_before_model(self):
        self.queue()
        (self.root / self.payload['attemptId'] / 'input.mp4').write_bytes(b'other')
        self.worker.start()
        self.assertEqual(self.worker.run_once()['error_code'], 'INPUT_CHECKSUM_MISMATCH')
        self.model.infer.assert_not_called()

    def test_unsupported_configuration_fails_before_model(self):
        self.payload['configVersion'] = 'unknown-config'
        self.queue()
        self.worker.start()
        self.assertEqual(self.worker.run_once()['error_code'], 'CONFIGURATION_MISMATCH')
        self.model.infer.assert_not_called()

    def test_non_monotonic_pts_fails_without_timestamp_repair(self):
        self.media.probe.return_value = (100, 80, 1000, [(0, .7), (1, .3)])
        self.queue()
        self.worker.start()
        self.assertEqual(self.worker.run_once()['error_code'], 'INVALID_FRAME_TIMESTAMP')
        self.model.infer.assert_not_called()

    def test_unknown_prediction_class_never_collapses_to_crack(self):
        self.model.infer.return_value[0]['sourceClass'] = 'CRACK'
        self.queue()
        self.worker.start()
        self.assertEqual(self.worker.run_once()['error_code'], 'UNKNOWN_SOURCE_CLASS')

    def test_invalid_confidence_never_finishes_completed(self):
        self.model.infer.return_value[0]['confidence'] = float('nan')
        self.queue()
        self.worker.start()
        self.assertEqual(self.worker.run_once()['state'], 'FAILED')

    def test_telemetry_artifact_provenance_uses_verified_video(self):
        def extract(video, output, **options):
            self.assertEqual(hashlib.sha256(video.read_bytes()).hexdigest(), self.payload['inputSha256'])
            output.write_bytes(b'unit-only-derived-srt')
            return {'stream_index': 2}
        self.extractor.side_effect = extract
        self.queue()
        self.worker.start()
        saved = self.worker.run_once()
        self.assertEqual(saved['state'], 'COMPLETED')
        telemetry = saved['result']['telemetry']
        self.assertEqual((telemetry['source'], telemetry['outcome'], telemetry['streamIndex']),
                         ('EMBEDDED', 'EXTRACTED_VALID', 2))
        artifact = telemetry['srtArtifact']
        self.assertEqual(artifact['sha256'], hashlib.sha256(b'unit-only-derived-srt').hexdigest())
        self.assertEqual(self.model.infer.call_count, 2)


class MediaProcessBoundsTests(unittest.TestCase):
    def test_nonzero_container_origin_is_shared_with_subtitle_timeline(self):
        metadata = {'streams': [{'codec_type': 'video', 'width': 100, 'height': 80}],
                    'format': {'duration': '1.000000', 'start_time': '10.125000'}}
        frames = {'frames': [{'best_effort_timestamp_time': '10.125000'},
                             {'best_effort_timestamp_time': '10.625000'}]}
        with patch.object(runner, '_bounded_command', side_effect=[json.dumps(metadata).encode(), json.dumps(frames).encode()]):
            width, height, duration, pts = runner.FFmpegMedia().probe('fixture.mp4', lambda: None)
        self.assertEqual((width, height, duration, pts), (100, 80, 1000, [(0, 0.), (1, .5)]))
        self.assertEqual(pts.origin_seconds, '10.125000')
        self.assertEqual(pts.source_pts, {0: '10.125000', 1: '10.625000'})

    def test_origin_subtraction_preserves_initial_video_gap(self):
        metadata = {'streams': [{'codec_type': 'video', 'width': 100, 'height': 80}],
                    'format': {'duration': '2', 'start_time': '10'}}
        frames = {'frames': [{'best_effort_timestamp_time': '10.250000'},
                             {'best_effort_timestamp_time': '10.750000'}]}
        with patch.object(runner, '_bounded_command', side_effect=[json.dumps(metadata).encode(), json.dumps(frames).encode()]):
            pts = runner.FFmpegMedia().probe('fixture.mp4', lambda: None)[3]
        self.assertEqual(pts, [(0, .25), (1, .75)])

    def test_frame_before_declared_origin_is_rejected_without_clamping(self):
        metadata = {'streams': [{'codec_type': 'video', 'width': 100, 'height': 80}],
                    'format': {'duration': '2', 'start_time': '10'}}
        frames = {'frames': [{'best_effort_timestamp_time': '9.999999'}]}
        with patch.object(runner, '_bounded_command', side_effect=[json.dumps(metadata).encode(), json.dumps(frames).encode()]):
            with self.assertRaisesRegex(runner.RunnerError, 'INVALID_FRAME_TIMESTAMP'):
                runner.FFmpegMedia().probe('fixture.mp4', lambda: None)

    @unittest.skipUnless(os.environ.get('ROADGUARD_TEST_FFMPEG') and os.environ.get('ROADGUARD_TEST_FFPROBE'),
                         'Explicit local FFmpeg/FFprobe required for synthetic media regression')
    def test_real_frame_selection_uses_full_budget_with_irregular_ordinals(self):
        media = runner.FFmpegMedia(os.environ['ROADGUARD_TEST_FFMPEG'], os.environ['ROADGUARD_TEST_FFPROBE'])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            video = root / 'frame-budget.mp4'
            runner._bounded_command([media.ffmpeg, '-v', 'error', '-f', 'lavfi', '-i',
                'testsrc2=s=48x32:r=30:d=12', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                '-n', str(video)], lambda: None)
            timeline = media.probe(video, lambda: None)[3]
            selected = [timeline[2 * i + i % 2] for i in range(180)]
            reference_dir = root / 'reference'
            selected_dir = root / 'selected'
            reference_dir.mkdir()
            selected_dir.mkdir()
            runner._bounded_command([media.ffmpeg, '-v', 'error', '-noautorotate', '-copyts',
                '-threads', '1', '-i', str(video), '-map', '0:v:0', '-fps_mode', 'passthrough',
                '-threads', '1', '-q:v', '2', '-n', str(reference_dir / 'frame-%06d.jpg')], lambda: None)
            frames = list(media.frames(video, selected_dir, selected, lambda: None))
            self.assertEqual([timestamp for timestamp, _ in frames], [timestamp for _, timestamp in selected])
            for (ordinal, _), (_, frame) in zip(selected, frames):
                self.assertEqual(frame.read_bytes(), (reference_dir / f'frame-{ordinal+1:06d}.jpg').read_bytes())

    @unittest.skipUnless(os.environ.get('ROADGUARD_TEST_FFMPEG') and os.environ.get('ROADGUARD_TEST_FFPROBE'),
                         'Explicit local FFmpeg/FFprobe required for synthetic media regression')
    def test_real_nonzero_video_and_embedded_cues_share_relative_clock(self):
        from src.ingestion.embedded_srt import extract_srt
        from src.ingestion.srt_parser import DJISRTParser
        media = runner.FFmpegMedia(os.environ['ROADGUARD_TEST_FFMPEG'], os.environ['ROADGUARD_TEST_FFPROBE'])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subtitle = root / 'source.srt'
            subtitle.write_text('1\n00:00:00,000 --> 00:00:01,000\n[latitude: 10.0] [longitude: 106.0]\n', encoding='utf-8')
            video = root / 'nonzero.mp4'
            runner._bounded_command([media.ffmpeg, '-v', 'error', '-f', 'lavfi', '-i',
                'color=c=black:s=100x80:r=2:d=1', '-i', str(subtitle), '-map', '0:v', '-map', '1:s',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:s', 'mov_text', '-output_ts_offset', '10',
                '-n', str(video)], lambda: None)
            width, height, duration, pts = media.probe(video, lambda: None)
            self.assertEqual((width, height, pts), (100, 80, [(0, 0.), (1, .5)]))
            # FFprobe versions differ on whether this fixture's duration includes its output offset.
            self.assertIn(duration, (1000, 11000))
            self.assertEqual(float(pts.origin_seconds), 10.)
            frames_dir = root / 'frames'; frames_dir.mkdir()
            self.assertEqual([t for t, _ in media.frames(video, frames_dir, pts, lambda: None)], [0., .5])
            output = root / 'derived.srt'
            extract_srt(video, output, ffmpeg=media.ffmpeg, ffprobe=media.ffprobe)
            rows = DJISRTParser().parse_file(output)
            self.assertTrue(rows)
            self.assertEqual(rows[0].timestamp_ms, 0)
    def test_pinned_checkpoint_exact_names_map_to_six_wire_labels(self):
        names = dict(enumerate(('Alligator crack', 'Longitudinal crack', 'Oblique crack',
                                'Pothole', 'Repair', 'Transverse crack')))
        with patch.dict(sys.modules, {'ultralytics': Mock(YOLO=Mock(return_value=Mock(names=names)))}):
            model = runner.FT95Model('mock-model.pt')
            self.assertEqual(model.names, dict(enumerate(SOURCE_CLASSES)))

    def test_model_reads_uuid_named_jpeg_without_extension(self):
        from PIL import Image
        names = dict(enumerate(runner.FT95_CHECKPOINT_CLASSES))
        native = Mock(names=names)
        native.predict.return_value = []
        with tempfile.TemporaryDirectory() as directory:
            frame = Path(directory) / str(uuid4())
            Image.new('RGB', (100, 80)).save(frame, format='JPEG')
            with patch.dict(sys.modules, {'ultralytics': Mock(YOLO=Mock(return_value=native))}):
                model = runner.FT95Model('mock-model.pt')
                self.assertEqual(model.infer(frame), [])
                self.assertIsInstance(native.predict.call_args.kwargs['source'], Image.Image)

    def test_oversized_probe_capture_is_rejected(self):
        with self.assertRaisesRegex(runner.RunnerError, 'MEDIA_RESOURCE_LIMIT'):
            runner._bounded_command([sys.executable, '-c', 'print("x" * 4096)'],
                                    lambda: None, max_output=128)

    def test_hung_media_process_is_killed_at_timeout(self):
        with self.assertRaisesRegex(runner.RunnerError, 'MEDIA_TIMEOUT'):
            runner._bounded_command([sys.executable, '-c', 'import time; time.sleep(60)'],
                                    lambda: None, timeout=.05)


if __name__ == '__main__':
    unittest.main()
