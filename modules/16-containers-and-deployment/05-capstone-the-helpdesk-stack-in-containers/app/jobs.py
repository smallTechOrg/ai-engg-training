"""The job queue the API and the worker share.

RedisQueue is what runs in the compose stack (API and worker are different containers, so
they need a shared store). MemoryQueue is the same interface inside one process: tests and
the lesson scripts use it, and so does the API when REDIS_URL is not set.
"""

import json
import os
import queue
import threading


class MemoryQueue:
    def __init__(self) -> None:
        self._jobs: queue.Queue = queue.Queue()
        self._results: dict[str, dict] = {}
        self._lock = threading.Lock()

    def push(self, job: dict) -> None:
        self._jobs.put(job)

    def pop(self, timeout: float = 1.0) -> dict | None:
        try:
            return self._jobs.get(timeout=timeout)
        except queue.Empty:
            return None

    def set_result(self, job_id: str, result: dict) -> None:
        with self._lock:
            self._results[job_id] = result

    def get_result(self, job_id: str) -> dict | None:
        with self._lock:
            return self._results.get(job_id)

    def ping(self) -> bool:
        return True


class RedisQueue:
    """Same interface on Redis: a list for jobs (LPUSH / BRPOP) and one key per result."""

    JOBS = "helpdesk:jobs"

    def __init__(self, url: str) -> None:
        import redis  # installed in the image (pyproject.toml), not needed for the lesson scripts

        self._r = redis.Redis.from_url(url, decode_responses=True, socket_timeout=5, socket_connect_timeout=2)

    def push(self, job: dict) -> None:
        self._r.lpush(self.JOBS, json.dumps(job))

    def pop(self, timeout: float = 1.0) -> dict | None:
        item = self._r.brpop([self.JOBS], timeout=max(1, int(timeout)))
        return json.loads(item[1]) if item else None

    def set_result(self, job_id: str, result: dict) -> None:
        self._r.set(f"helpdesk:result:{job_id}", json.dumps(result), ex=3600)

    def get_result(self, job_id: str) -> dict | None:
        raw = self._r.get(f"helpdesk:result:{job_id}")
        return json.loads(raw) if raw else None

    def ping(self) -> bool:
        return bool(self._r.ping())


def make_queue():
    url = os.environ.get("REDIS_URL", "").strip()
    return RedisQueue(url) if url else MemoryQueue()
