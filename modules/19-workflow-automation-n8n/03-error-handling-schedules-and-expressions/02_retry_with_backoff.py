"""19.3/2  Retry, backoff and when NOT to retry

n8n's per-node "Retry On Fail" waits a FIXED time between tries. This script reproduces that in code on a
flaky in-process "agent", compares it with exponential backoff plus jitter, and shows the rule that matters
most: retry transient failures (timeouts, 429, 5xx) and never client errors (400, 422), because repeating a
bad request only repeats the failure. Time is simulated, so nothing actually sleeps. No model, no network.

Run it:   ./run 19.3/2          (Windows: run 19.3/2)
     or:  python modules/19-workflow-automation-n8n/03-error-handling-schedules-and-expressions/02_retry_with_backoff.py
"""

import random

from labkit import lesson

RETRYABLE = {408, 429, 500, 502, 503, 504}


class Flaky:
    """Fails with `status` for the first `failures` calls, then succeeds."""

    def __init__(self, failures, status=503):
        self.failures, self.status, self.calls = failures, status, 0

    def __call__(self):
        self.calls += 1
        return (self.status, "error") if self.calls <= self.failures else (200, "ok")


def run_with_retry(call, max_tries, wait_for, clock, log):
    """wait_for(try_no) -> seconds to wait before the NEXT try. Returns (status, tries)."""
    for attempt in range(1, max_tries + 1):
        status, _ = call()
        log(f"    try {attempt} at t={clock[0]:5.1f}s -> {status}")
        if status == 200:
            return status, attempt
        if status not in RETRYABLE:
            log("    not retryable: stopping at once")
            return status, attempt
        if attempt < max_tries:
            clock[0] += wait_for(attempt)
    log(f"    giving up after {max_tries} tries (the hard cap)")
    return status, max_tries


@lesson("19.3/2", "Retry, backoff and when not to retry")
def main(ctx):
    log = print
    rng = random.Random(7)  # fixed seed: the same jitter every run

    ctx.step("Fixed wait: what n8n's Retry On Fail does (maxTries=3, waitBetweenTries=2000 ms)")
    clock = [0.0]
    status, tries = run_with_retry(Flaky(failures=2), 3, lambda n: 2.0, clock, log)
    ctx.note(f"Result {status} after {tries} tries, {clock[0]:.1f}s of waiting.")

    ctx.step("The cap in action: the agent is down for good")
    clock = [0.0]
    status, tries = run_with_retry(Flaky(failures=99), 3, lambda n: 2.0, clock, log)
    ctx.note(f"Result {status}: n8n would now mark the node failed and hand over to your error handling (19.3/3).")

    ctx.step("Exponential backoff with jitter: 1s, 2s, 4s ... plus up to 50% random")
    clock = [0.0]
    backoff = lambda n: (2 ** (n - 1)) * (1 + 0.5 * rng.random())  # noqa: E731
    status, tries = run_with_retry(Flaky(failures=3, status=429), 5, backoff, clock, log)
    ctx.note(f"Result {status} after {tries} tries, {clock[0]:.1f}s waiting. Jitter stops many clients retrying in lockstep.")

    ctx.step("A client error is never retried")
    clock = [0.0]
    status, tries = run_with_retry(Flaky(failures=99, status=422), 5, lambda n: 2.0, clock, log)
    ctx.note(f"422 on try {tries}: the ticket field was empty; a fifth try would fail the same way.")

    ctx.step("Where each piece lives in n8n")
    for where, what in (
        ("node settings: Retry On Fail, Max Tries, Wait Between Tries", "fixed wait only; no backoff built in"),
        ("node settings: On Error = Continue (using error output)", "sends the failed item down a second output"),
        ("HTTP Request option: Never Error / status handling", "treat a 4xx as data instead of a failure"),
        ("Loop with a Wait node and an IF node", "the way to build real backoff on the canvas"),
    ):
        print(f"  {where}\n      {what}")


if __name__ == "__main__":
    main()
