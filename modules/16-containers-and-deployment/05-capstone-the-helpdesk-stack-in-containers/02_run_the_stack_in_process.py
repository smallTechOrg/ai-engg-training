"""16.5/2  Capstone, part 2: the stack's own code, run in one process

The API (app/api.py), the worker's job handler and stop handler (app/worker.py) and the settings
check (app/settings.py) are the exact modules the containers run. Here they run together in one
process so you can test the stack's behaviour without Docker: the queue is the in-memory twin of
Redis (REDIS_URL is removed from the environment for this script), the model call is real.

Steps: settings check, readiness, submit tickets, a worker thread processes them, then a real
SIGTERM (raise_signal; nothing is killed) triggers the worker's stop handler.

Makes 4 model calls.

Run it:   ./run 16.5/2          (Windows: run 16.5/2)
"""

import os
import signal
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from labkit import lesson

HERE = Path(__file__).parent
TICKETS = [
    "The VPN disconnects every ten minutes when I work from home.",
    "My laptop screen is cracked and flickers.",
    "Outlook keeps rejecting my password since I changed it yesterday.",
    "Excel crashes every time I open the finance workbook.",
]


@lesson("16.5/2", "Capstone: run the stack's code in process")
def main(ctx):
    for name in ("REDIS_URL", "CHROMA_URL", "LLM_API_KEY_FILE"):
        os.environ.pop(name, None)  # in-memory queue, no vector store, key from the plain variable
    os.environ["LLM_BASE_URL"] = ctx.settings.base_url
    os.environ["LLM_MODEL"] = ctx.model
    os.environ["LLM_API_KEY"] = ctx.settings.api_key  # never printed
    sys.path.insert(0, str(HERE))
    from app import api, settings, worker  # the files the containers run

    ctx.step("Settings check (what the container does at start-up)")
    print("  problems with the current settings:", settings.problems() or "none")
    saved = os.environ.pop("LLM_MODEL")
    print("  with LLM_MODEL missing:           ", settings.problems())
    os.environ["LLM_MODEL"] = saved

    ctx.step("Readiness")
    client = TestClient(api.app)
    print("  GET /health/live  ->", client.get("/health/live").status_code)
    print("  GET /health/ready ->", client.get("/health/ready").status_code, client.get("/health/ready").json())

    ctx.step("Submit tickets: instant 202s")
    ids = []
    for text in TICKETS:
        reply = client.post("/tickets", json={"text": text})
        ids.append(reply.json()["job_id"])
        print(f"  {reply.status_code} {reply.json()}")

    ctx.step("A worker thread runs app.worker.handle on each job (real model call)")

    class RecordingClient:
        """Wraps the OpenAI client so token usage is counted; the worker code itself is unchanged."""

        def __init__(self, inner):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
            self.inner = inner

        def create(self, **kwargs):
            done = self.inner.chat.completions.create(**kwargs)
            ctx.record_usage(done.usage, quiet=True)
            return done

    recording = RecordingClient(ctx.client)
    worker.stopping = False

    def loop():
        while not worker.stopping:
            job = api.jobs.pop(timeout=0.2)
            if job is None:
                continue
            try:
                api.jobs.set_result(job["id"], worker.handle(job, recording))
            except Exception as exc:
                api.jobs.set_result(job["id"], {"job_id": job["id"], "status": "failed", "error": type(exc).__name__})

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    deadline = time.time() + 120  # hard cap
    while time.time() < deadline:
        states = [client.get(f"/tickets/{i}").json()["status"] for i in ids]
        print("  poll:", states)
        if all(s != "queued" for s in states):
            break
        time.sleep(1.0)
    for job_id, text in zip(ids, TICKETS):
        result = client.get(f"/tickets/{job_id}").json()
        print(f"  [{result['status']}] {text[:48]!r} -> {(result.get('reply') or result.get('error') or '')[:90]}")

    ctx.step("SIGTERM: the worker's real stop handler")
    previous = signal.signal(signal.SIGTERM, worker.request_stop)
    try:
        print("  worker.stopping before:", worker.stopping)
        signal.raise_signal(signal.SIGTERM)
        print("  worker.stopping after: ", worker.stopping)
    finally:
        signal.signal(signal.SIGTERM, previous)
    thread.join(timeout=5)
    print("  worker thread ended:", not thread.is_alive())
    ctx.note("In the container, the same flag ends the loop after the current job and the worker prints 'stopped cleanly' (exit 0).")


if __name__ == "__main__":
    main()
