import unittest
import tempfile
import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import patch
from src.ingestion.embedded_srt import select_subtitle, extract_srt, ExtractionError

class EmbeddedSrtTests(unittest.TestCase):
    VALID_SRT = b'1\n00:00:00,000 --> 00:00:01,000\n[latitude: 10.5] [longitude: 106.5]\n\n'

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.video = Path(self.folder.name) / 'video with spaces; literal.mp4'
        self.video.write_bytes(b'video fixture')
        self.output = Path(self.folder.name) / 'out.srt'
        self.temporary = self.output.with_name('out.srt.extracting')

    def tools(self, payload=None, failure=None, fail_at=1, before_publish=None):
        payload = self.VALID_SRT if payload is None else payload
        calls = 0
        def run(args, **kwargs):
            nonlocal calls
            calls += 1
            self.assertIsInstance(args, list)
            self.assertFalse(kwargs.get('shell', False))
            self.assertEqual(kwargs['timeout'], 60)
            if failure is not None and calls == fail_at:
                if calls == 2:
                    Path(args[-1]).write_bytes(b'partial tool output')
                raise failure
            if calls == 1:
                self.assertEqual(args[-1], str(self.video))
                return subprocess.CompletedProcess(args, 0, json.dumps({'streams': [
                    {'index': 2, 'codec_type': 'subtitle', 'codec_name': 'mov_text'}]}).encode())
            self.assertEqual(args[args.index('-map') + 1], '0:2')
            Path(args[-1]).write_bytes(payload)
            if before_publish:
                before_publish()
            return subprocess.CompletedProcess(args, 0)
        return patch('src.ingestion.embedded_srt.subprocess.run', side_effect=run)

    def assert_no_artifacts(self):
        self.assertFalse(self.output.exists())
        self.assertFalse(self.temporary.exists())

    def test_valid_extraction_publishes_exact_bytes_and_provenance(self):
        with self.tools():
            result = extract_srt(self.video, self.output)
        self.assertEqual(self.output.read_bytes(), self.VALID_SRT)
        self.assertFalse(self.temporary.exists())
        self.assertEqual(result, {'status': 'EXTRACTED_VALID', 'stream_index': 2,
                                 'cue_count': 1, 'gps_cue_count': 1,
                                 'srt_sha256': hashlib.sha256(self.VALID_SRT).hexdigest()})

    def test_invalid_utf8_is_rejected_even_with_parseable_gps(self):
        with self.tools(self.VALID_SRT + b'\xff'):
            with self.assertRaisesRegex(ExtractionError, '^INVALID_TELEMETRY$'):
                extract_srt(self.video, self.output)
        self.assert_no_artifacts()

    def test_timeout_cleans_partial_output_at_either_tool(self):
        for stage in (1, 2):
            with self.subTest(stage=stage), self.tools(
                    failure=subprocess.TimeoutExpired('tool', 60), fail_at=stage):
                with self.assertRaisesRegex(ExtractionError, '^EXTRACTION_TIMEOUT$'):
                    extract_srt(self.video, self.output)
            self.assert_no_artifacts()

    def test_tool_failures_clean_artifacts(self):
        for failure in (subprocess.CalledProcessError(1, 'tool'), FileNotFoundError('tool')):
            for stage in (1, 2):
                with self.subTest(failure=failure, stage=stage), self.tools(failure=failure, fail_at=stage):
                    with self.assertRaisesRegex(ExtractionError, '^EXTRACTION_FAILED$'):
                        extract_srt(self.video, self.output)
                self.assert_no_artifacts()

    def test_oversized_output_is_rejected_after_extraction(self):
        with self.tools():
            with self.assertRaisesRegex(ExtractionError, '^OUTPUT_TOO_LARGE$'):
                extract_srt(self.video, self.output, max_bytes=len(self.VALID_SRT) - 1)
        self.assert_no_artifacts()

    def test_invalid_telemetry_is_rejected(self):
        for payload in (b'', b'ordinary text', self.VALID_SRT.replace(b'10.5', b'99.5')):
            with self.subTest(payload=payload), self.tools(payload):
                with self.assertRaisesRegex(ExtractionError, '^INVALID_TELEMETRY$'):
                    extract_srt(self.video, self.output)
            self.assert_no_artifacts()

    def test_existing_output_is_preserved(self):
        self.output.write_bytes(b'existing artifact')
        with self.assertRaises(FileExistsError):
            extract_srt(self.video, self.output)
        self.assertEqual(self.output.read_bytes(), b'existing artifact')
        self.assertFalse(self.temporary.exists())

    def test_racing_output_is_preserved(self):
        with self.tools(before_publish=lambda: self.output.write_bytes(b'other owner')):
            with self.assertRaises(FileExistsError):
                extract_srt(self.video, self.output)
        self.assertEqual(self.output.read_bytes(), b'other owner')
        self.assertFalse(self.temporary.exists())

    def test_other_attempt_temporary_is_preserved(self):
        self.temporary.write_bytes(b'in progress')
        with self.assertRaises(FileExistsError):
            extract_srt(self.video, self.output)
        self.assertEqual(self.temporary.read_bytes(), b'in progress')
        self.assertFalse(self.output.exists())

    def test_overlapping_attempt_cannot_delete_active_temporary(self):
        def second_attempt():
            with self.assertRaises(FileExistsError):
                extract_srt(self.video, self.output)
            self.assertEqual(self.temporary.read_bytes(), self.VALID_SRT)
        with self.tools(before_publish=second_attempt):
            extract_srt(self.video, self.output)
        self.assertEqual(self.output.read_bytes(), self.VALID_SRT)
        self.assertFalse(self.temporary.exists())

    def test_malformed_probe_is_a_controlled_error(self):
        for probe in (None, [], {'streams': None}, {'streams': [None]},
                      {'streams': [{'codec_type': 'subtitle', 'codec_name': 'srt', 'index': True}]}):
            with self.subTest(probe=probe):
                with self.assertRaisesRegex(ExtractionError, '^INVALID_PROBE$'):
                    select_subtitle(probe)

    def test_selects_unique_text_subtitle(self):
        self.assertEqual(select_subtitle({'streams':[{'index':2,'codec_type':'subtitle','codec_name':'mov_text'}]}),2)
    def test_no_subtitle_is_distinct(self):
        with self.assertRaisesRegex(ExtractionError, 'NO_SUBTITLE_STREAM'):
            select_subtitle({'streams':[{'index':1,'codec_type':'data'}]})
    def test_ambiguous_is_not_silently_selected(self):
        with self.assertRaisesRegex(ExtractionError, 'TELEMETRY_AMBIGUOUS'):
            select_subtitle({'streams':[{'index':i,'codec_type':'subtitle','codec_name':'mov_text'} for i in [1,2]]})
    def test_unsupported_is_distinct(self):
        with self.assertRaisesRegex(ExtractionError, 'UNSUPPORTED_STREAM'):
            select_subtitle({'streams':[{'index':1,'codec_type':'subtitle','codec_name':'dvd_subtitle'}]})
    def test_missing_input_does_not_launch_tools(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                extract_srt(Path(folder)/'absent.mp4',Path(folder)/'out.srt')

if __name__ == '__main__': unittest.main()
