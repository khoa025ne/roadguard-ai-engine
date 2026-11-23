"""Strict private rg-ai-worker-v1 validation. No HTTP/framework dependency."""
import json
import math
import re
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

CONTRACT_VERSION = "rg-ai-worker-v1"
SOURCE_CLASSES = ("alligator crack", "longitudinal crack", "oblique crack", "pothole", "repair", "transverse crack")
STATES = ("AWAITING_INPUT", "QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED")
UUID_FIELDS = ("projectId", "jobId", "attemptId", "datasetId", "sourceVideoFileId", "modelVersionId")
HASH_FIELDS = ("manifestHash", "checkpointSha256", "inputSha256")
VERSION_FIELDS = ("preprocessingVersion", "configVersion")
INTEGER_LIMITS = {"inputBytes": 9223372036854775807, "inputWidth": 16384,
                  "inputHeight": 16384, "inputDurationMs": 2147483647, "maxFrames": 10000}
ADMISSION_FIELDS = frozenset(("contractVersion", "sampleFps", *UUID_FIELDS, *HASH_FIELDS, *VERSION_FIELDS, *INTEGER_LIMITS))


class ValidationError(ValueError):
    """A safe field-only error, never containing caller values or credentials."""


def _fail(field):
    raise ValidationError("Invalid " + field)


def _keys(value, fields, name):
    if type(value) is not dict or set(value) != set(fields):
        _fail(name + " fields")


def _uuid(value, name):
    try:
        parsed = UUID(value) if type(value) is str else None
    except (ValueError, AttributeError):
        parsed = None
    if parsed is None or parsed.int == 0 or str(parsed) != value:
        _fail(name)


def _integer(value, minimum, maximum, name):
    if type(value) is not int or not minimum <= value <= maximum:
        _fail(name)


def _number(value, minimum, maximum, name, exclusive_min=False):
    if type(value) not in (int, float):
        _fail(name)
    if not minimum <= value <= maximum or not math.isfinite(value) or (exclusive_min and value == minimum):
        _fail(name)


def _hash(value, name):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        _fail(name)


def validate_admission(payload):
    """Return a detached normalized JSON object; reject missing/extra fields."""
    _keys(payload, ADMISSION_FIELDS, "admission")
    if payload["contractVersion"] != CONTRACT_VERSION:
        _fail("contractVersion")
    for name in UUID_FIELDS:
        _uuid(payload[name], name)
    for name in HASH_FIELDS:
        _hash(payload[name], name)
    for name in VERSION_FIELDS:
        if type(payload[name]) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", payload[name]) is None:
            _fail(name)
    for name, maximum in INTEGER_LIMITS.items():
        _integer(payload[name], 1, maximum, name)
    _number(payload["sampleFps"], 0, 30, "sampleFps", exclusive_min=True)
    return dict(payload, sampleFps=float(payload["sampleFps"]))


def canonical_admission(payload):
    return json.dumps(validate_admission(payload), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def seconds_to_ms(seconds):
    _number(seconds, 0, 2147483.647, "timestamp")
    return int((Decimal(str(seconds)) * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def normalized_bbox(pixel_xyxy, width, height):
    _integer(width, 1, 16384, "width")
    _integer(height, 1, 16384, "height")
    if type(pixel_xyxy) is not list or len(pixel_xyxy) != 4:
        _fail("bbox")
    x1, y1, x2, y2 = pixel_xyxy
    for coordinate in pixel_xyxy:
        _number(coordinate, 0, max(width, height), "bbox")
    if not (x1 < x2 <= width and y1 < y2 <= height):
        _fail("bbox")
    return [x1 / width, y1 / height, (x2 - x1) / width, (y2 - y1) / height]


def _artifact(value, frame=False):
    fields = {"artifactId", "sha256", "bytes", "mediaType"}
    if frame:
        fields |= {"width", "height"}
    _keys(value, fields, "artifact")
    _uuid(value["artifactId"], "artifactId")
    _hash(value["sha256"], "artifact sha256")
    _integer(value["bytes"], 1, 9223372036854775807, "artifact bytes")
    if value["mediaType"] != ("image/jpeg" if frame else "application/json"):
        _fail("artifact mediaType")
    if frame:
        _integer(value["width"], 1, 16384, "frame width")
        _integer(value["height"], 1, 16384, "frame height")


def validate_result(payload, admission):
    """Validate immutable result metadata; bytes/hash verification is transport's job."""
    expected = validate_admission(admission)
    _keys(payload, ADMISSION_FIELDS | {"resultId", "rawArtifact", "frameArtifacts", "detections",
                                       "telemetry", "roadMaskStatus", "limitations"}, "result")
    actual = validate_admission({k: payload[k] for k in ADMISSION_FIELDS})
    if canonical_admission(actual) != canonical_admission(expected):
        _fail("result admission identity")
    _uuid(payload["resultId"], "resultId")
    _artifact(payload["rawArtifact"])
    frames = payload["frameArtifacts"]
    if type(frames) is not list or len(frames) > expected["maxFrames"]:
        _fail("frameArtifacts")
    artifact_ids = {payload["rawArtifact"]["artifactId"]}
    frame_ids = set()
    for frame in frames:
        _artifact(frame, frame=True)
        identity = frame["artifactId"]
        if identity in artifact_ids:
            _fail("duplicate artifactId")
        artifact_ids.add(identity)
        frame_ids.add(identity)
    detections = payload["detections"]
    if type(detections) is not list or len(detections) > expected["maxFrames"] * 1000:
        _fail("detections")
    detection_ids = set()
    for detection in detections:
        _keys(detection, {"detectionId", "frameArtifactId", "timestampMs", "sourceClass", "confidence", "bbox"}, "detection")
        _uuid(detection["detectionId"], "detectionId")
        if detection["detectionId"] in detection_ids:
            _fail("duplicate detectionId")
        detection_ids.add(detection["detectionId"])
        _uuid(detection["frameArtifactId"], "frameArtifactId")
        if detection["frameArtifactId"] not in frame_ids:
            _fail("frameArtifactId")
        _integer(detection["timestampMs"], 0, expected["inputDurationMs"], "timestampMs")
        if detection["sourceClass"] not in SOURCE_CLASSES:
            _fail("sourceClass")
        _number(detection["confidence"], 0, 1, "confidence")
        bbox = detection["bbox"]
        if type(bbox) is not list or len(bbox) != 4:
            _fail("bbox")
        for value in bbox:
            _number(value, 0, 1, "bbox")
        if bbox[2] <= 0 or bbox[3] <= 0 or bbox[0] + bbox[2] > 1 or bbox[1] + bbox[3] > 1:
            _fail("bbox")
    telemetry = payload["telemetry"]
    _keys(telemetry, {"source", "outcome", "sourceVideoSha256", "streamIndex", "extractorVersion", "srtArtifact"}, "telemetry")
    if telemetry["sourceVideoSha256"] != expected["inputSha256"]:
        _fail("telemetry sourceVideoSha256")
    if telemetry["source"] not in ("EMBEDDED", "PAIRED_SRT", "NONE"):
        _fail("telemetry source")
    if telemetry["outcome"] not in ("EXTRACTED_VALID", "NO_SUBTITLE_STREAM", "UNSUPPORTED_STREAM", "INVALID_TELEMETRY", "TELEMETRY_AMBIGUOUS", "EXTRACTION_FAILED"):
        _fail("telemetry outcome")
    if telemetry["streamIndex"] is not None:
        _integer(telemetry["streamIndex"], 0, 2147483647, "streamIndex")
    if type(telemetry["extractorVersion"]) is not str or not 1 <= len(telemetry["extractorVersion"]) <= 128:
        _fail("extractorVersion")
    if telemetry["srtArtifact"] is not None:
        srt = telemetry["srtArtifact"]
        _keys(srt, {"artifactId", "sha256", "bytes", "mediaType"}, "srtArtifact")
        _uuid(srt["artifactId"], "srtArtifactId")
        _hash(srt["sha256"], "srt sha256")
        _integer(srt["bytes"], 1, 16777216, "srt bytes")
        if srt["mediaType"] != "application/x-subrip" or srt["artifactId"] in artifact_ids:
            _fail("srtArtifact")
    if telemetry["outcome"] == "EXTRACTED_VALID" and (telemetry["srtArtifact"] is None or telemetry["source"] == "NONE"):
        _fail("valid telemetry artifact")
    if payload["roadMaskStatus"] not in ("AVAILABLE", "NOT_AVAILABLE"):
        _fail("roadMaskStatus")
    if type(payload["limitations"]) is not list or len(payload["limitations"]) > 32:
        _fail("limitations")
    for limitation in payload["limitations"]:
        if type(limitation) is not str or re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", limitation) is None:
            _fail("limitations")
    return json.loads(json.dumps(payload, allow_nan=False))
