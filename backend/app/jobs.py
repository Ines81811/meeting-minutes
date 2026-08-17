import threading
from typing import Literal

Status = Literal["pending", "processing", "done", "failed"]

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def create_job(transcript_id: str) -> None:
    with _lock:
        _jobs[transcript_id] = {"status": "pending", "error": None}


def set_status(transcript_id: str, status: Status, error: str | None = None) -> None:
    with _lock:
        _jobs[transcript_id] = {"status": status, "error": error}


def get_status(transcript_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(transcript_id)
        return dict(job) if job else None
