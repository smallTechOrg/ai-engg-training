"""16.2/2  The API answers at once, a worker does the slow model call

A model call takes seconds. If the API makes it while the caller waits, ten tickets at once mean
ten stuck connections. The pattern in the compose stack: the API puts the ticket on a QUEUE and
answers "202 queued" in milliseconds; a separate WORKER takes jobs off the queue, calls the model
and stores the result; the caller polls for it. Here everything runs in one process (an in-memory
queue, a worker thread, FastAPI's TestClient) so you can watch the pattern; in compose the queue
is Redis and the worker is its own container (app/jobs.py and app/worker.py).

Makes about 4 model calls.

Run it:   ./run 16.2/2          (Windows: run 16.2/2)
"""

import queue
import threading
import time
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from labkit import lesson

SYSTEM_PROMPT = "You are the IT helpdesk assistant at Larkspur Labs. Answer in two sentences."
TICKETS = [
    "My VPN keeps dropping every few minutes.",
    "Outlook says my password is wrong after I changed it yesterday.",
    "The printer on floor 2 shows an offline error.",
    "BOOM-POISON this ticket always crashes the handler.",  # shows the failed state
]
MAX_ATTEMPTS = 2


class Ticket(BaseModel):
    text: str


@lesson("16.2/2", "The API answers at once, a worker does the model call")
def main(ctx):
    jobs: queue.Queue = queue.Queue()
    results: dict[str, dict] = {}  # in compose this is Redis
    stop = threading.Event()
    attempts_seen: dict[str, int] = {}

    # ---- the API: put on the queue, answer 202 immediately ----
    app = FastAPI()

    @app.post("/tickets", status_code=202)
    def submit(ticket: Ticket) -> dict:
        job_id = uuid.uuid4().hex[:8]
        jobs.put({"id": job_id, "text": ticket.text})
        return {"job_id": job_id, "status": "queued"}

    @app.get("/tickets/{job_id}")
    def status(job_id: str) -> dict:
        return results.get(job_id, {"job_id": job_id, "status": "queued"})

    # ---- the worker: the same loop as app/worker.py ----
    def handle(job: dict) -> str:
        attempts_seen[job["id"]] = attempts_seen.get(job["id"], 0) + 1
        if "BOOM" in job["text"]:
            raise RuntimeError("handler crashed")
        if attempts_seen[job["id"]] == 1 and "printer" in job["text"]:
            raise TimeoutError("simulated transient provider error")  # succeeds on the retry
        done = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": job["text"]}],
        )
        ctx.record_usage(done.usage, quiet=True)
        return done.choices[0].message.content

    def worker() -> None:
        while not stop.is_set():
            try:
                job = jobs.get(timeout=0.2)
            except queue.Empty:
                continue
            for attempt in range(1, MAX_ATTEMPTS + 1):  # hard cap on retries
                try:
                    results[job["id"]] = {"job_id": job["id"], "status": "done", "reply": handle(job)}
                    break
                except Exception as exc:
                    if attempt == MAX_ATTEMPTS:
                        results[job["id"]] = {"job_id": job["id"], "status": "failed", "error": type(exc).__name__}
                    else:
                        print(f"  worker: job {job['id']} attempt {attempt} failed ({type(exc).__name__}), retrying")

    ctx.step("The API accepts every ticket without waiting for the model")
    client = TestClient(app)
    ids = []
    started = time.perf_counter()
    for text in TICKETS:
        reply = client.post("/tickets", json={"text": text})
        ids.append(reply.json()["job_id"])
        print(f"  POST /tickets -> {reply.status_code} {reply.json()}")
    print(f"  all {len(TICKETS)} tickets accepted in {(time.perf_counter() - started) * 1000:.0f} ms; queue length {jobs.qsize()}")

    ctx.step("Start the worker and poll for results")
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    deadline = time.time() + 120  # hard cap so the lesson always ends
    while time.time() < deadline:
        states = [client.get(f"/tickets/{i}").json()["status"] for i in ids]
        print("  poll:", states)
        if all(s != "queued" for s in states):
            break
        time.sleep(1.0)
    stop.set()
    thread.join(timeout=5)

    ctx.step("The results")
    for job_id, text in zip(ids, TICKETS):
        result = client.get(f"/tickets/{job_id}").json()
        shown = result.get("reply") or f"error: {result.get('error')}"
        print(f"  [{result['status']:<6}] {text[:45]!r}\n           -> {shown[:140]}")
    ctx.note("The poison ticket ended as 'failed' after its retries instead of looping forever or killing the worker.")
    ctx.note("In compose, results live in Redis, so the API container and the worker container can differ and restart independently.")


if __name__ == "__main__":
    main()
