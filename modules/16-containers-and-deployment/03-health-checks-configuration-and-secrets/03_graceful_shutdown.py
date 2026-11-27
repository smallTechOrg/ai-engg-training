"""16.3/3  Graceful shutdown: SIGTERM, drain, finish, exit

`docker stop` sends SIGTERM and, after the grace period (10 s by default; `stop_grace_period` in
compose), SIGKILL, which cannot be caught. A service that ignores SIGTERM loses every job in flight.
A good one: (1) flips readiness to "not ready", (2) stops taking new work, (3) finishes the work in
progress within the grace period, (4) puts back what it cannot finish, (5) exits 0.

This script tests that in process: it installs a SIGTERM handler, runs a worker pool, then sends
itself a real SIGTERM with signal.raise_signal (no process is killed; the old handler is restored
afterwards). Scaled-down times (0.2 s jobs, a 1.5 s "grace period"). No model call.

Run it:   ./run 16.3/3          (Windows: run 16.3/3)
"""

import queue
import signal
import threading
import time

from labkit import lesson


class Service:
    def __init__(self, workers: int, job_seconds: dict[str, float]) -> None:
        self.jobs: queue.Queue = queue.Queue()
        self.job_seconds = job_seconds
        self.stopping = threading.Event()
        self.ready = True
        self.done: list[str] = []
        self.in_flight: set[str] = set()
        self.lock = threading.Lock()
        self.threads = [threading.Thread(target=self.loop, daemon=True) for _ in range(workers)]

    def loop(self) -> None:
        while not self.stopping.is_set():  # checked BETWEEN jobs: a job that started always finishes
            try:
                job = self.jobs.get(timeout=0.05)
            except queue.Empty:
                continue
            with self.lock:
                self.in_flight.add(job)
            time.sleep(self.job_seconds.get(job, 0.2))  # stands in for the model call
            with self.lock:
                self.in_flight.discard(job)
                self.done.append(job)

    def on_sigterm(self, signum, frame) -> None:
        # Keep the handler tiny: set flags only. The main thread does the draining.
        self.ready = False
        self.stopping.set()


def scenario(ctx, title: str, job_seconds: dict[str, float], grace: float) -> None:
    ctx.step(title)
    service = Service(workers=2, job_seconds=job_seconds)
    previous = signal.signal(signal.SIGTERM, service.on_sigterm)
    try:
        for thread in service.threads:
            thread.start()
        for number in range(1, 7):
            service.jobs.put(f"LL-{1000 + number}")
        time.sleep(0.3)
        print(f"  t=0.3s  {len(service.done)} done, {len(service.in_flight)} running, {service.jobs.qsize()} waiting; ready={service.ready}")

        print("  -> sending SIGTERM to ourselves (what `docker stop` does)")
        signal.raise_signal(signal.SIGTERM)
        print(f"  handler ran: ready={service.ready}, stopping={service.stopping.is_set()}")

        deadline = time.monotonic() + grace  # the stop_grace_period; after it Docker sends SIGKILL
        for thread in service.threads:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        stuck = [t for t in service.threads if t.is_alive()]
        leftovers = []
        while True:
            try:
                leftovers.append(service.jobs.get_nowait())
            except queue.Empty:
                break
        print(f"  finished: {sorted(service.done)}")
        print(f"  not started, put back for the next instance: {leftovers}")
        if stuck:
            print(f"  STILL RUNNING at the deadline: {sorted(service.in_flight)} -> SIGKILL would cut these off")
            print("  fix: raise stop_grace_period, make jobs shorter, or requeue unacknowledged jobs on restart")
        else:
            print("  exit code 0: every started job finished inside the grace period")
    finally:
        signal.signal(signal.SIGTERM, previous)  # leave the process the way we found it


@lesson("16.3/3", "Graceful shutdown with a SIGTERM handler")
def main(ctx):
    scenario(ctx, "Scenario A: jobs are short, the grace period is enough", {}, grace=1.5)
    scenario(ctx, "Scenario B: one job takes far longer than the grace period", {"LL-1001": 5.0}, grace=1.0)
    ctx.step("The rules")
    print("  - Uvicorn already does this for HTTP: on SIGTERM it stops accepting and waits for open requests.")
    print("  - A queue worker must do it itself (see app/worker.py in 16.2): check the flag between jobs, never inside one.")
    print("  - CMD in exec form, otherwise /bin/sh is PID 1 and the signal never reaches Python (16.1).")
    print("  - At-least-once: if a job can be cut off, make it safe to run twice (idempotent), or requeue it.")


if __name__ == "__main__":
    main()
