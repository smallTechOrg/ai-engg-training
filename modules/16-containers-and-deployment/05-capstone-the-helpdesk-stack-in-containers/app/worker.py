"""Worker: takes jobs from the queue, calls the model, stores the result.

SIGTERM (docker stop) lets the current job finish, then the loop ends. A heartbeat file lets
the container healthcheck (`python -m app.worker --check`) tell a stuck worker from a busy one.
"""

import os
import signal
import sys
import tempfile
import time
from pathlib import Path

from openai import OpenAI

from app import settings
from app.jobs import make_queue

HEARTBEAT = Path(tempfile.gettempdir()) / "worker-heartbeat"
SYSTEM_PROMPT = "You are the IT helpdesk assistant at Larkspur Labs. Answer in two sentences."
MAX_ATTEMPTS = 3
stopping = False


def request_stop(signum, frame) -> None:
    global stopping
    stopping = True


def handle(job: dict, client: OpenAI) -> dict:
    done = client.chat.completions.create(
        model=settings.get("LLM_MODEL"),
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": job["text"]}],
    )
    return {"job_id": job["id"], "status": "done", "reply": done.choices[0].message.content}


def run() -> None:
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    bad = settings.problems()
    if bad:  # fail fast, with every problem listed
        sys.exit("worker: refusing to start: " + "; ".join(bad))
    jobs = make_queue()
    client = OpenAI(base_url=settings.get("LLM_BASE_URL"), api_key=settings.get("LLM_API_KEY"))
    while not stopping:
        HEARTBEAT.touch()
        job = jobs.pop(timeout=2)
        if job is None:
            continue
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                jobs.set_result(job["id"], handle(job, client))
                break
            except Exception as exc:
                if attempt == MAX_ATTEMPTS:
                    jobs.set_result(job["id"], {"job_id": job["id"], "status": "failed", "error": type(exc).__name__})
                else:
                    time.sleep(2 * attempt)
    print("worker: stopped cleanly", flush=True)


if __name__ == "__main__":
    if "--check" in sys.argv:
        fresh = HEARTBEAT.exists() and time.time() - HEARTBEAT.stat().st_mtime < 30
        sys.exit(0 if fresh else 1)
    run()
