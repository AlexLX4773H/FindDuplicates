"""A busy scan can be queued, reordered, and removed without starting another scan."""
import os
import sys
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import BackgroundTasks
from fastapi.responses import JSONResponse

import src.web.app as webapp
from src.web.app import (
    STATE,
    ScanCancelled,
    _CANCEL,
    add_scan_log,
    cancel_queued_scan,
    reorder_queue,
    run_scan_job,
)
from src.web.app import QueueReorderPayload, RunJobPayload
from src.web.jobs import ScanJobCreatePayload, job_manager


def test_busy_scan_queues_reorders_and_removes_without_starting():
    saved = {
        "is_scanning": STATE["is_scanning"],
        "queue": list(STATE.get("queue") or []),
        "running_entry": STATE.get("running_entry"),
        "active_scan_info": STATE.get("active_scan_info"),
    }
    job = job_manager.create_job(ScanJobCreatePayload(
        name="Queue Probe",
        target_type="manga",
        paths=["/tmp/queue-probe"],
        mode="name",
    ))
    try:
        STATE["is_scanning"] = True
        STATE["queue"] = []
        STATE["running_entry"] = {
            "queue_id": "q_running",
            "job_id": None,
            "job_name": "Current",
            "target": "manga",
            "mode": "name",
            "paths": [],
        }
        busy = run_scan_job(job["id"], BackgroundTasks(), RunJobPayload(queue=False))
        assert isinstance(busy, JSONResponse), busy
        assert busy.status_code == 409

        queued = run_scan_job(job["id"], BackgroundTasks(), RunJobPayload(queue=True))
        second = run_scan_job(job["id"], BackgroundTasks(), RunJobPayload(queue=True))
        assert queued["status"] == "queued"
        assert second["status"] == "queued"
        assert [entry["queue_id"] for entry in STATE["queue"]] == [queued["queue_id"], second["queue_id"]]
        assert STATE["running_entry"]["queue_id"] == "q_running"

        moved = reorder_queue(QueueReorderPayload(queue_id=second["queue_id"], direction="up"))
        assert [entry["queue_id"] for entry in moved["queue"]] == [second["queue_id"], queued["queue_id"]]

        removed = cancel_queued_scan(second["queue_id"])
        assert removed["status"] == "removed"
        assert [entry["queue_id"] for entry in STATE["queue"]] == [queued["queue_id"]]
        assert STATE["is_scanning"] is True
        assert STATE["running_entry"]["queue_id"] == "q_running"

        cancelling = cancel_queued_scan("q_running")
        assert cancelling["status"] == "cancelling"
        assert _CANCEL.is_set()
        assert STATE["is_scanning"] is True
        assert STATE["running_entry"]["queue_id"] == "q_running"
    finally:
        _CANCEL.clear()
        job_manager.delete_job(job["id"])
        STATE["is_scanning"] = saved["is_scanning"]
        STATE["queue"] = saved["queue"]
        STATE["running_entry"] = saved["running_entry"]
        STATE["active_scan_info"] = saved["active_scan_info"]


def test_cancel_flag_stops_the_scan_thread_at_the_next_log():
    webapp._SCAN_THREAD_ID = threading.get_ident()
    _CANCEL.set()
    try:
        try:
            add_scan_log("this line should not be stored", "INFO")
        except ScanCancelled:
            return
        raise AssertionError("cancel flag should stop the scan thread")
    finally:
        _CANCEL.clear()
        webapp._SCAN_THREAD_ID = None


if __name__ == "__main__":
    test_busy_scan_queues_reorders_and_removes_without_starting()
    test_cancel_flag_stops_the_scan_thread_at_the_next_log()
    print("ok")
