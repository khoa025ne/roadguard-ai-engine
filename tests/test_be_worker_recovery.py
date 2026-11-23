"""SQLite admission, crash recovery and independent-connection contention."""
import concurrent.futures
import json
from pathlib import Path
import tempfile
import threading
import unittest
import uuid

from src.api.be_worker_store import WorkerStore, WorkerStoreError


FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures/ai-worker-v1"


class WorkerRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "worker.sqlite3"
        self.now = 1000.0
        self.store = WorkerStore(self.path, clock=lambda: self.now)
        self.payload = json.loads((FIXTURES / "admission.json").read_text())

    def admit(self):
        payload = dict(self.payload, attemptId=str(uuid.uuid4()))
        return self.store.admit(payload)[0]

    def queued(self):
        record = self.admit()
        return self.store.mark_input_verified(record["attemptId"], "verified-input")

    def assertCode(self, code, fn):
        with self.assertRaises(WorkerStoreError) as context:
            fn()
        self.assertEqual(context.exception.code, code)

    def test_replay_reopen_and_changed_payload_conflict(self):
        record, replay = self.store.admit(self.payload)
        self.assertFalse(replay)
        reopened = WorkerStore(self.path, clock=lambda: self.now)
        other, replay = reopened.admit(dict(reversed(list(self.payload.items()))))
        self.assertTrue(replay)
        self.assertEqual(record, other)
        self.assertCode("ADMISSION_CONFLICT", lambda: reopened.admit(dict(self.payload, maxFrames=1)))

    def test_capacity_includes_awaiting_input_and_replay(self):
        records = [self.admit() for _ in range(4)]
        self.assertTrue(self.store.admit(records[0]["payload"])[1])
        self.assertCode("QUEUE_FULL", self.admit)
        self.store.request_cancel(records[0]["attemptId"])
        self.assertEqual(self.admit()["state"], "AWAITING_INPUT")

    def test_awaiting_input_expires_at_fifteen_minutes(self):
        record = self.admit()
        self.now += 899
        self.assertEqual(self.store.expire_awaiting_input(), 0)
        self.now += 1
        self.assertEqual(self.store.expire_awaiting_input(), 1)
        saved = self.store.get(record["attemptId"])
        self.assertEqual((saved["state"], saved["error_code"]), ("FAILED", "INPUT_TIMEOUT"))
        self.assertCode("INVALID_STATE", lambda: self.store.mark_input_verified(record["attemptId"], "late"))

    def test_admission_expires_stale_reservations_and_queue_does_not_expire(self):
        queued = self.queued()
        stale = [self.admit() for _ in range(3)]
        self.now += 900
        self.admit()
        self.assertEqual(self.store.get(queued["attemptId"])["state"], "QUEUED")
        for record in stale:
            self.assertEqual(self.store.get(record["attemptId"])["state"], "FAILED")

    def test_input_marker_is_durable_idempotent_and_immutable(self):
        record = self.queued()
        reopened = WorkerStore(self.path)
        self.assertEqual(reopened.get(record["attemptId"])["input_marker"], "verified-input")
        self.assertEqual(reopened.mark_input_verified(record["attemptId"], "verified-input"), record)
        self.assertCode("INPUT_CONFLICT", lambda: reopened.mark_input_verified(record["attemptId"], "other"))
        with self.assertRaises(ValueError):
            reopened.mark_input_verified(record["attemptId"], "")

    def test_fifo_and_one_running(self):
        first = self.queued()
        second = self.queued()
        self.assertEqual(self.store.claim_next()["attemptId"], first["attemptId"])
        self.assertIsNone(WorkerStore(self.path).claim_next())
        self.store.finish(first["attemptId"], "FAILED", error_code="MODEL_MISSING")
        self.assertEqual(self.store.claim_next()["attemptId"], second["attemptId"])

    def test_restart_interrupts_running_preserves_queue_and_never_reruns(self):
        running = self.queued()
        queued = self.queued()
        self.store.claim_next()
        reopened = WorkerStore(self.path)
        self.assertEqual(reopened.get(running["attemptId"])["state"], "RUNNING")
        self.assertEqual(reopened.recover_running(), 1)
        self.assertEqual(reopened.recover_running(), 0)
        self.assertEqual(reopened.get(running["attemptId"])["state"], "INTERRUPTED")
        self.assertEqual(reopened.claim_next()["attemptId"], queued["attemptId"])

    def test_running_cancel_retains_slot_until_runner_acknowledges(self):
        record = self.queued()
        self.store.claim_next()
        for _ in range(3):
            self.admit()
        cancelled = self.store.request_cancel(record["attemptId"])
        self.assertEqual(cancelled["state"], "RUNNING")
        self.assertTrue(cancelled["cancellation_requested"])
        self.assertCode("QUEUE_FULL", self.admit)
        self.assertIsNone(self.store.claim_next())
        self.store.finish(record["attemptId"], "CANCELLED")
        self.admit()

    def test_completion_result_is_durable_immutable_and_detached(self):
        record = self.queued()
        self.store.claim_next()
        result = {"detections": [{"detectionId": str(uuid.uuid4())}]}
        saved = self.store.finish(record["attemptId"], "COMPLETED", result=result)
        reopened = WorkerStore(self.path)
        self.assertEqual(reopened.get_result(record["attemptId"]), result)
        self.assertEqual(reopened.finish(record["attemptId"], "COMPLETED", result=result), saved)
        self.assertCode("RESULT_CONFLICT", lambda: reopened.finish(record["attemptId"], "COMPLETED", result={}))
        self.assertCode("INVALID_STATE", lambda: reopened.finish(record["attemptId"], "FAILED"))
        self.assertEqual(reopened.request_cancel(record["attemptId"]), saved)
        numeric = dict(result, score=1)
        numeric_record = self.queued()
        self.store.claim_next()
        self.store.finish(numeric_record["attemptId"], "COMPLETED", result=numeric)
        self.assertCode("RESULT_CONFLICT", lambda: self.store.finish(
            numeric_record["attemptId"], "COMPLETED", result=dict(numeric, score=1.0)))
        result["detections"].clear()
        self.assertEqual(len(reopened.get_result(record["attemptId"])["detections"]), 1)

    def test_invalid_transitions_and_result_access(self):
        record = self.admit()
        self.assertCode("INVALID_STATE", lambda: self.store.finish(record["attemptId"], "COMPLETED", result={}))
        self.assertCode("RESULT_NOT_READY", lambda: self.store.get_result(record["attemptId"]))
        self.assertCode("ATTEMPT_NOT_FOUND", lambda: self.store.request_cancel(str(uuid.uuid4())))
        self.assertIsNone(self.store.get(str(uuid.uuid4())))

    def concurrent(self, count, operation):
        stores = [WorkerStore(self.path) for _ in range(count)]
        barrier = threading.Barrier(count)
        def run(store):
            barrier.wait()
            try:
                return operation(store)
            except WorkerStoreError as exc:
                return exc.code
        with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
            return list(pool.map(run, stores))

    def test_concurrent_duplicate_admission_creates_one_slot(self):
        results = self.concurrent(8, lambda store: store.admit(self.payload))
        self.assertEqual(sum(not replay for _, replay in results), 1)
        for _ in range(3):
            self.admit()
        self.assertCode("QUEUE_FULL", self.admit)

    def test_concurrent_capacity_cannot_overadmit(self):
        results = self.concurrent(8, lambda store: store.admit(dict(self.payload, attemptId=str(uuid.uuid4()))))
        self.assertEqual(sum(isinstance(result, tuple) for result in results), 4)
        self.assertEqual(results.count("QUEUE_FULL"), 4)

    def test_concurrent_claim_has_exactly_one_winner(self):
        for _ in range(4):
            self.queued()
        results = self.concurrent(8, lambda store: store.claim_next())
        self.assertEqual(sum(result is not None for result in results), 1)

    def test_disk_reservations_are_atomic_durable_and_released_at_terminal(self):
        reservation = self.payload["inputBytes"] + self.payload["maxFrames"] * (
            self.payload["inputWidth"] * self.payload["inputHeight"] * 3 + 65536) + 64 * 1024 * 1024
        limited = WorkerStore(self.path, clock=lambda: self.now, reservation_limit_bytes=reservation)
        record, _ = limited.admit(self.payload)
        self.assertEqual(limited.active_reservation_bytes(), reservation)
        self.assertEqual(len(limited.list_active()), 1)
        self.assertTrue(limited.admit(self.payload)[1])
        self.assertCode("DISK_BUDGET", lambda: limited.admit(dict(self.payload, attemptId=str(uuid.uuid4()))))
        self.store.request_cancel(record["attemptId"])
        self.assertEqual(limited.active_reservation_bytes(), 0)
        self.assertEqual(limited.list_active(), [])
        limited.admit(dict(self.payload, attemptId=str(uuid.uuid4())))

    def test_queued_cancellation_is_terminal_and_cannot_be_claimed(self):
        record = self.queued()
        cancelled = self.store.request_cancel(record["attemptId"])
        self.assertEqual(cancelled["state"], "CANCELLED")
        self.assertEqual(self.store.request_cancel(record["attemptId"]), cancelled)
        self.assertIsNone(self.store.claim_next())

    def test_expired_input_publication_commits_timeout_before_rejection(self):
        record = self.admit()
        self.now += 900
        self.assertCode("INVALID_STATE", lambda: self.store.mark_input_verified(record["attemptId"], "late"))
        reopened = WorkerStore(self.path)
        self.assertEqual(reopened.get(record["attemptId"])["error_code"], "INPUT_TIMEOUT")
        self.assertEqual(reopened.active_reservation_bytes(), 0)

    def test_concurrent_disk_budget_cannot_overreserve(self):
        reservation = self.payload["inputBytes"] + self.payload["maxFrames"] * (
            self.payload["inputWidth"] * self.payload["inputHeight"] * 3 + 65536) + 64 * 1024 * 1024
        barrier = threading.Barrier(8)
        def run(_):
            store = WorkerStore(self.path, reservation_limit_bytes=reservation)
            barrier.wait()
            try:
                return store.admit(dict(self.payload, attemptId=str(uuid.uuid4())))
            except WorkerStoreError as exc:
                return exc.code
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(run, range(8)))
        self.assertEqual(sum(isinstance(result, tuple) for result in results), 1)
        self.assertEqual(results.count("DISK_BUDGET"), 7)


if __name__ == "__main__":
    unittest.main()
