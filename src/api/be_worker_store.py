"""Durable private-worker admission; no inference, HTTP or filesystem cleanup.

Database and verified input markers are trusted operator/worker inputs, never wire
paths. Each operation owns a separate SQLite connection and short transaction.
The exclusive runner startup owner must explicitly call ``recover_running``.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from .be_worker_contract import canonical_admission, validate_admission


TERMINAL_STATES = frozenset({"COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED"})
ACTIVE_STATES = ("AWAITING_INPUT", "QUEUED", "RUNNING")
INPUT_TIMEOUT_SECONDS = 15 * 60


class WorkerStoreError(Exception):
    """Stable private-worker error suitable for transport mapping."""

    def __init__(self, code, status_code=409):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class WorkerStore:
    def __init__(self, db_path, *, clock=time.time, reservation_limit_bytes=None):
        self.db_path = str(Path(db_path).resolve())
        self.clock = clock
        if reservation_limit_bytes is not None and (
                type(reservation_limit_bytes) is not int or reservation_limit_bytes < 1):
            raise ValueError("Reservation limit must be a positive integer")
        self.reservation_limit_bytes = reservation_limit_bytes
        # No memory-only database: acknowledged acceptance must survive restart.
        if str(db_path) == ":memory:":
            raise ValueError("A durable database path is required")
        with self._transaction() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS worker_attempts (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    attempt_id TEXT NOT NULL UNIQUE,
                    payload_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    reservation_bytes TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN (
                        'AWAITING_INPUT','QUEUED','RUNNING','COMPLETED',
                        'FAILED','CANCELLED','INTERRUPTED')),
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    input_deadline REAL NOT NULL,
                    input_marker TEXT,
                    cancellation_requested INTEGER NOT NULL DEFAULT 0,
                    result_json TEXT,
                    error_code TEXT
                )
            """)
            connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS worker_one_running
                ON worker_attempts(state) WHERE state = 'RUNNING'""")

    @contextmanager
    def _transaction(self):
        connection = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _record(row):
        if row is None:
            return None
        return {
            "attemptId": row["attempt_id"],
            "payload_hash": row["payload_hash"],
            "payload": json.loads(row["payload_json"]),
            "reservation_bytes": int(row["reservation_bytes"]),
            "state": row["state"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "input_deadline": row["input_deadline"],
            "input_marker": row["input_marker"],
            "cancellation_requested": bool(row["cancellation_requested"]),
            "result": json.loads(row["result_json"]) if row["result_json"] is not None else None,
            "error_code": row["error_code"],
        }

    def _find(self, connection, attempt_id, *, required=True):
        row = connection.execute("SELECT * FROM worker_attempts WHERE attempt_id = ?", (attempt_id,)).fetchone()
        if row is None and required:
            raise WorkerStoreError("ATTEMPT_NOT_FOUND", 404)
        return self._record(row)

    def _expire(self, connection, now):
        return connection.execute("""UPDATE worker_attempts
            SET state='FAILED', error_code='INPUT_TIMEOUT', updated_at=?
            WHERE state='AWAITING_INPUT' AND input_deadline <= ?""", (now, now)).rowcount

    def expire_awaiting_input(self):
        with self._transaction() as connection:
            return self._expire(connection, self.clock())

    def admit(self, payload):
        """Return (durable record, replay); identical terminal replays stay terminal."""
        normalized = validate_admission(payload)
        canonical = canonical_admission(normalized)
        digest = hashlib.sha256(canonical).hexdigest()
        reservation = normalized["inputBytes"] + normalized["maxFrames"] * (
            normalized["inputWidth"] * normalized["inputHeight"] * 3 + 65536) + 64 * 1024 * 1024
        attempt_id = normalized["attemptId"]
        with self._transaction() as connection:
            now = self.clock()
            self._expire(connection, now)
            existing = self._find(connection, attempt_id, required=False)
            if existing is not None:
                if existing["payload_hash"] != digest:
                    raise WorkerStoreError("ADMISSION_CONFLICT")
                return existing, True
            active = connection.execute("""SELECT COUNT(*) FROM worker_attempts
                WHERE state IN ('AWAITING_INPUT','QUEUED','RUNNING')""").fetchone()[0]
            if active >= 4:
                raise WorkerStoreError("QUEUE_FULL", 429)
            if (self.reservation_limit_bytes is not None and
                    self._reserved(connection) + reservation > self.reservation_limit_bytes):
                raise WorkerStoreError("DISK_BUDGET", 507)
            connection.execute("""INSERT INTO worker_attempts
                (attempt_id,payload_hash,payload_json,reservation_bytes,state,created_at,updated_at,input_deadline)
                VALUES (?,?,?,?,'AWAITING_INPUT',?,?,?)""",
                (attempt_id, digest, canonical.decode("utf-8"), str(reservation), now, now, now + INPUT_TIMEOUT_SECONDS))
            return self._find(connection, attempt_id), False

    def get(self, attempt_id):
        with self._transaction() as connection:
            return self._find(connection, attempt_id, required=False)

    @staticmethod
    def _reserved(connection):
        # Python integer summation avoids overflow for the contract's int64 sizes.
        return sum(int(row[0]) for row in connection.execute("""SELECT reservation_bytes
            FROM worker_attempts WHERE state IN ('AWAITING_INPUT','QUEUED','RUNNING')"""))

    def active_reservation_bytes(self):
        with self._transaction() as connection:
            return self._reserved(connection)

    def list_active(self):
        with self._transaction() as connection:
            return [self._record(row) for row in connection.execute("""SELECT * FROM worker_attempts
                WHERE state IN ('AWAITING_INPUT','QUEUED','RUNNING') ORDER BY sequence""")]

    def mark_input_verified(self, attempt_id, marker):
        """Internal-only publication after trusted byte/hash/rename verification."""
        if not isinstance(marker, str) or not marker.strip():
            raise ValueError("A nonempty verified input marker is required")
        with self._transaction() as connection:
            record = self._find(connection, attempt_id)
            now = self.clock()
            if record["state"] == "AWAITING_INPUT" and record["input_deadline"] <= now:
                # Commit expiry before reporting rejection, with no clock-boundary
                # gap between the deadline check and publication transaction.
                self._expire(connection, now)
            else:
                return self._publish_verified(connection, record, marker, now)
        raise WorkerStoreError("INVALID_STATE")

    def _publish_verified(self, connection, record, marker, now):
        attempt_id = record["attemptId"]
        if record["input_marker"] is not None:
            if record["input_marker"] != marker:
                raise WorkerStoreError("INPUT_CONFLICT")
            return record
        if record["state"] != "AWAITING_INPUT":
            raise WorkerStoreError("INVALID_STATE")
        connection.execute("""UPDATE worker_attempts
            SET input_marker=?, state='QUEUED', updated_at=? WHERE attempt_id=?""",
            (marker, now, attempt_id))
        return self._find(connection, attempt_id)

    def claim_next(self):
        """Atomically claim the earliest admitted queued attempt, if none runs."""
        with self._transaction() as connection:
            if connection.execute("SELECT 1 FROM worker_attempts WHERE state='RUNNING'").fetchone():
                return None
            row = connection.execute("""SELECT attempt_id FROM worker_attempts
                WHERE state='QUEUED' ORDER BY sequence LIMIT 1""").fetchone()
            if row is None:
                return None
            connection.execute("""UPDATE worker_attempts SET state='RUNNING',updated_at=?
                WHERE attempt_id=?""", (self.clock(), row["attempt_id"]))
            return self._find(connection, row["attempt_id"])

    def request_cancel(self, attempt_id):
        with self._transaction() as connection:
            record = self._find(connection, attempt_id)
            if record["state"] in TERMINAL_STATES or record["cancellation_requested"]:
                return record
            state = "RUNNING" if record["state"] == "RUNNING" else "CANCELLED"
            connection.execute("""UPDATE worker_attempts SET state=?,
                cancellation_requested=1, updated_at=? WHERE attempt_id=?""",
                (state, self.clock(), attempt_id))
            return self._find(connection, attempt_id)

    def finish(self, attempt_id, state, *, result=None, error_code=None):
        """Runner acknowledgment; persisted results are immutable, never generated here."""
        if state not in TERMINAL_STATES:
            raise ValueError("A terminal state is required")
        if state == "COMPLETED" and not isinstance(result, dict):
            raise ValueError("Completion requires a result JSON object")
        if state != "COMPLETED" and result is not None:
            raise ValueError("Only completion can contain a result")
        result_json = _json(result) if result is not None else None
        with self._transaction() as connection:
            record = self._find(connection, attempt_id)
            if record["state"] in TERMINAL_STATES:
                if record["state"] != state:
                    raise WorkerStoreError("INVALID_STATE")
                saved_json = _json(record["result"]) if record["result"] is not None else None
                if saved_json != result_json or record["error_code"] != error_code:
                    raise WorkerStoreError("RESULT_CONFLICT")
                return record
            if record["state"] != "RUNNING":
                raise WorkerStoreError("INVALID_STATE")
            # Linearize completion against cancellation under the same write
            # transaction. A cancellation committed before this acknowledgment
            # wins even if inference passed its final cooperative check.
            if state == "COMPLETED" and record["cancellation_requested"]:
                state, result_json, error_code = "CANCELLED", None, "CANCELLED"
            connection.execute("""UPDATE worker_attempts SET state=?,result_json=?,
                error_code=?,updated_at=? WHERE attempt_id=?""",
                (state, result_json, error_code, self.clock(), attempt_id))
            return self._find(connection, attempt_id)

    def recover_running(self):
        """Exclusive runner startup only: never silently rerun uncertain inference."""
        with self._transaction() as connection:
            return connection.execute("""UPDATE worker_attempts SET state='INTERRUPTED',
                error_code='WORKER_RESTARTED',updated_at=? WHERE state='RUNNING'""",
                (self.clock(),)).rowcount

    def get_result(self, attempt_id):
        with self._transaction() as connection:
            record = self._find(connection, attempt_id)
            if record["state"] != "COMPLETED":
                raise WorkerStoreError("RESULT_NOT_READY")
            return record["result"]
