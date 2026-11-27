"""02.4/2  Retries, timeouts and idempotency

New since script 1: some failures are TRANSIENT (a timeout, a busy service). Your program, not
the model, should retry those, quietly, with a short wait that grows (backoff). Three rules:

  1. retry only transient errors, and only a few times;
  2. put a TIMEOUT on every tool call so one slow call cannot freeze the loop;
  3. make actions IDEMPOTENT: a retried `reset_password` must not send two reset links.
     An idempotency key (a stable id for "this action") lets the tool recognise a repeat.

Parts 1-3 are offline demos of each rule. Part 4 runs the real model against a flaky tool.

Run it:   ./run 02.4/2          (Windows: run 02.4/2)
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from labkit import lesson

MAX_STEPS = 4
BACKOFF_SECONDS = (0.05, 0.1)  # tiny in the lesson; real systems use seconds


class TransientError(Exception):
    """A failure worth retrying (timeout, 503, connection reset)."""


def with_retries(function, *args, log=None):
    """Run function; retry TransientError with backoff. Other exceptions pass straight through."""
    for attempt in range(1, len(BACKOFF_SECONDS) + 2):
        try:
            return function(*args)
        except TransientError as error:
            if log is not None:
                log.append(f"attempt {attempt} failed: {error}")
            if attempt > len(BACKOFF_SECONDS):
                raise
            time.sleep(BACKOFF_SECONDS[attempt - 1])


def with_timeout(function, seconds, *args):
    """Raise TransientError if the call takes longer than `seconds`. (The thread cannot be killed; it is abandoned.)"""
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(function, *args).result(timeout=seconds)
    except FutureTimeout:
        raise TransientError(f"timed out after {seconds}s") from None
    finally:
        pool.shutdown(wait=False)


# ---- idempotent action -------------------------------------------------------------------
SENT_LINKS = []  # the real world effect, so we can count it


def reset_password(username: str, idempotency_key: str, _seen={}) -> dict:
    if idempotency_key in _seen:
        return {**_seen[idempotency_key], "note": "repeat of an earlier request: nothing sent again"}
    SENT_LINKS.append(username)
    _seen[idempotency_key] = {"username": username, "result": "reset link sent (simulated)"}
    return _seen[idempotency_key]


# ---- a flaky read tool for the model -----------------------------------------------------
FLAKY = {"calls": 0}


def lookup_ticket(ticket_id: str) -> dict:
    FLAKY["calls"] += 1
    if FLAKY["calls"] == 1:
        raise TransientError("ticket service busy (503)")
    return {"ticket_id": ticket_id, "subject": "VPN drops every ten minutes", "status": "open"}


TOOLS = [{"type": "function", "function": {
    "name": "lookup_ticket", "description": "Read a helpdesk ticket by id such as LL-2090.",
    "parameters": {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]}}}]


@lesson("02.4/2", "Retries, timeouts and idempotency")
def main(ctx):
    ctx.step("1. Retry a transient failure with backoff")
    state, log = {"n": 0}, []

    def flaky():
        state["n"] += 1
        if state["n"] < 3:
            raise TransientError("connection reset")
        return "ok"

    ctx.note(f"Result: {with_retries(flaky, log=log)}")
    ctx.show_data("Retry log", log)
    ctx.note(f"Two waits of {BACKOFF_SECONDS[0]}s and {BACKOFF_SECONDS[1]}s, then success. If all three failed, the error is raised to the caller.")

    ctx.step("2. A timeout so a slow tool cannot freeze the loop")
    try:
        with_timeout(time.sleep, 0.05, 1)  # a call that takes 1s against a 0.05s limit
    except TransientError as error:
        ctx.note(f"Caught: {error}. The loop can retry or report it, instead of waiting a minute.")

    ctx.step("3. Idempotency: the same request twice sends ONE reset link")
    first = reset_password("dmorgan", idempotency_key="LL-2090:reset:dmorgan")
    second = reset_password("dmorgan", idempotency_key="LL-2090:reset:dmorgan")  # e.g. a retry after a timeout
    ctx.show_data("First call", first)
    ctx.show_data("Second call (same key)", second)
    ctx.note(f"Links actually sent: {len(SENT_LINKS)}. Without the key a retry after a lost response would send two.")
    ctx.note("Retrying a READ is always safe. Retrying a WRITE is safe only if it is idempotent.")

    ctx.step("4. The real model against a tool whose first call fails")
    messages = [
        {"role": "system", "content": "You are the Larkspur Labs helpdesk agent. Use lookup_ticket, then answer in one sentence."},
        {"role": "user", "content": "What is ticket LL-2090 about?"},
    ]
    for turn in range(1, MAX_STEPS + 1):
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, tools=TOOLS)
        message = response.choices[0].message
        if not message.tool_calls:
            ctx.show_response(response)
            break
        ctx.record_usage(response.usage, quiet=True)
        messages.append({"role": "assistant", "content": message.content, "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in message.tool_calls]})
        for call in message.tool_calls:
            attempts = []
            try:
                args = json.loads(call.function.arguments or "{}")
                result = with_retries(lambda: lookup_ticket(**args), log=attempts)
            except (ValueError, TypeError) as error:
                args, result = call.function.arguments, {"error": "bad_arguments", "message": str(error)}
            except TransientError as error:
                args, result = call.function.arguments, {"error": "unavailable", "message": f"{error}; tried {len(attempts)} times"}
            ctx.show_tool_call(call.function.name, args, json.dumps(result))
            if attempts:
                ctx.note("Hidden from the model: " + "; ".join(attempts))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
    else:
        ctx.note(f"Stopped at the cap of {MAX_STEPS} calls.")
    ctx.note("The model never saw the failed first attempt: the retry layer absorbed it. That is the point of retrying below the model.")


if __name__ == "__main__":
    main()
