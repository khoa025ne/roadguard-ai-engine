"""Private worker golden fixtures, strict admission and geometry checks."""
import copy
import json
import unittest
from pathlib import Path

from src.api.be_worker_contract import (
    ValidationError, validate_admission, canonical_admission, validate_result,
    normalized_bbox, seconds_to_ms, SOURCE_CLASSES,
)

FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures/ai-worker-v1"


class WorkerContractTests(unittest.TestCase):
    def setUp(self):
        self.admission = json.loads((FIXTURES / "admission.json").read_text())

    def test_golden_admission_and_canonical_replay(self):
        self.assertEqual(validate_admission(self.admission), self.admission)
        reverse = dict(reversed(list(self.admission.items())))
        self.assertEqual(canonical_admission(reverse), canonical_admission(self.admission))
        changed = dict(self.admission, inputWidth=640)
        self.assertNotEqual(canonical_admission(changed), canonical_admission(self.admission))

    def test_reject_unknown_url_path_and_missing_keys(self):
        for name in ("url", "inputPath", "callbackUrl"):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                validate_admission(dict(self.admission, **{name: "sensitive"}))
        for name in self.admission:
            payload = dict(self.admission)
            del payload[name]
            with self.subTest(name=name), self.assertRaises(ValidationError):
                validate_admission(payload)

    def test_strict_admission_negatives(self):
        cases = {"inputBytes": [True, 0, 9223372036854775808, "1", 1.0],
                 "inputWidth": [0, 16385], "maxFrames": [0, 10001],
                 "sampleFps": [False, 0, 31, float("nan"), float("inf")],
                 "checkpointSha256": ["A" * 64, "x" * 64],
                 "attemptId": ["../secret", "00000000-0000-0000-0000-000000000000"],
                 "configVersion": ["../config", "a" * 129],
                 "contractVersion": ["other"]}
        for name, values in cases.items():
            for value in values:
                with self.subTest(name=name, value=value), self.assertRaises(ValidationError):
                    validate_admission(dict(self.admission, **{name: value}))

    def test_geometry_and_timestamp_conversion(self):
        self.assertEqual(normalized_bbox([100, 50, 300, 150], 1000, 500), [0.1, 0.1, 0.2, 0.2])
        self.assertEqual(seconds_to_ms(1.2345), 1235)
        for bbox in ([0, 0, 0, 1], [2, 0, 1, 1], [-1, 0, 1, 1], [0, 0, 1001, 1], [0, 0, float("nan"), 1]):
            with self.subTest(bbox=bbox), self.assertRaises(ValidationError):
                normalized_bbox(bbox, 1000, 500)
        for seconds in (-1, float("nan"), True):
            with self.assertRaises(ValidationError):
                seconds_to_ms(seconds)

    def test_golden_result_preserves_six_labels_and_identities(self):
        result = json.loads((FIXTURES / "result.json").read_text())
        self.assertEqual(validate_result(result, self.admission), result)
        self.assertEqual(set(d["sourceClass"] for d in result["detections"]), set(SOURCE_CLASSES))
        self.assertEqual(validate_result(copy.deepcopy(result), self.admission), result)

    def test_result_rejects_identity_geometry_class_and_artifact_mismatch(self):
        original = json.loads((FIXTURES / "result.json").read_text())
        changes = [("identity", "attemptId", self.admission["jobId"]),
                   ("detection", "sourceClass", "CRACK"),
                   ("detection", "confidence", 1.01),
                   ("detection", "timestampMs", 60001),
                   ("detection", "bbox", [0.9, 0, 0.2, 1]),
                   ("detection", "frameArtifactId", self.admission["jobId"])]
        for target, key, value in changes:
            result = copy.deepcopy(original)
            (result if target == "identity" else result["detections"][0])[key] = value
            with self.subTest(key=key), self.assertRaises(ValidationError):
                validate_result(result, self.admission)

    def test_malformed_json_types_always_raise_safe_validation_error(self):
        result = json.loads((FIXTURES / "result.json").read_text())
        result["detections"][0]["frameArtifactId"] = []
        with self.assertRaises(ValidationError):
            validate_result(result, self.admission)
        with self.assertRaises(ValidationError):
            validate_admission(dict(self.admission, sampleFps=10 ** 1000))

    def test_negative_fixture_mutations(self):
        negatives = json.loads((FIXTURES / "negative-admissions.json").read_text())
        for case in negatives:
            with self.subTest(name=case["name"]), self.assertRaises(ValidationError):
                validate_admission(dict(self.admission, **{case["field"]: case["value"]}))


if __name__ == "__main__":
    unittest.main()
