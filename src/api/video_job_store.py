"""Local job receipts and append-only events. Results survive process restarts."""
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

GUARD = threading.RLock()
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED"}


def now():
    return datetime.now(timezone.utc).isoformat()


def directory(root, job_id):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise ValueError("JOB_NOT_FOUND")
    path = root / job_id
    if path.is_symlink() or path.resolve().parent != root.resolve():
        raise ValueError("JOB_NOT_FOUND")
    return path


def save(root, job):
    with GUARD:
        folder = directory(root, job["job_id"])
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / "job.json"
        temp = folder / "job.json.tmp"
        temp.write_text(json.dumps(job, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        temp.replace(target)


def read(root, job_id):
    with GUARD:
        return json.loads((directory(root, job_id) / "job.json").read_text(encoding="utf-8"))


def append(root, job, stage, severity, code, message, details=None):
    with GUARD:
        job["sequence"] = job.get("sequence", 0) + 1
        event = {"sequence": job["sequence"], "timestamp": now(), "job_id": job["job_id"],
                 "stage": stage, "severity": severity, "code": code, "message": message,
                 "details": details or {}}
        with (directory(root, job["job_id"]) / "events.jsonl").open("a", encoding="utf-8") as out:
            out.write(json.dumps(event, ensure_ascii=False) + "\n")
        job["stage"] = stage
        job["updated_at"] = now()
        save(root, job)
        return event


def events(root, job_id, after=0):
    path = directory(root, job_id) / "events.jsonl"
    result = []
    if path.is_file():
        with GUARD, path.open(encoding="utf-8") as stream:
            for line in stream:
                event = json.loads(line)
                if event["sequence"] > after:
                    result.append(event)
                    if len(result) == 1000:
                        break
    return result
