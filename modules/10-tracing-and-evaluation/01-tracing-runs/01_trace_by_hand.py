"""10.1/1  Tracing by hand: a span recorder in 40 lines

A trace is a tree of spans. A span is one unit of work with a start time, an end time,
its inputs, its outputs, the tokens it used, and a pointer to its parent span.

This script builds a tiny span recorder with nothing but the standard library, wraps a
two-step chain with it (classify the ticket, then write a reply), and prints the trace as
a tree with the latency and tokens of every span. Tracing tools such as LangSmith,
Langfuse or OpenTelemetry collect exactly this, store it and draw it for you.

Run it:   ./run 10.1/1          (Windows: run 10.1/1)
"""

import time
import uuid
from contextlib import contextmanager

from labkit import lesson

TICKET = (
    "Since this morning the VPN disconnects every ten minutes when I work from home. "
    "I have to log in again each time and it kills my video calls. - Jonas (Engineering)"
)
CATEGORIES = ["network", "hardware", "software", "access", "other"]

# Invented example prices in US dollars per million tokens. Put your provider's real prices here.
PRICE_IN_PER_MILLION = 0.10
PRICE_OUT_PER_MILLION = 0.40


class Tracer:
    """Records spans. `with tracer.span(...)` opens one; spans opened inside it become its children."""

    def __init__(self):
        self.spans = []  # every span, in the order it started
        self._open = []  # the stack of spans that have started and not ended yet

    @contextmanager
    def span(self, name, kind, inputs):
        record = {
            "id": uuid.uuid4().hex[:8],
            "parent_id": self._open[-1]["id"] if self._open else None,
            "name": name,
            "kind": kind,  # "chain" for our own code, "llm" for one model call
            "inputs": inputs,
            "outputs": None,
            "tokens_in": None,
            "tokens_out": None,
            "error": None,
            "start": time.perf_counter(),
            "end": None,
        }
        self.spans.append(record)
        self._open.append(record)
        try:
            yield record  # the code inside the `with` block fills in outputs and tokens
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            record["end"] = time.perf_counter()
            self._open.pop()


def seconds(span):
    return span["end"] - span["start"]


def tokens_of(span, spans):
    """Tokens of this span plus all its descendants (a parent 'costs' what its children cost)."""
    tokens_in, tokens_out = span["tokens_in"] or 0, span["tokens_out"] or 0
    for child in spans:
        if child["parent_id"] == span["id"]:
            child_in, child_out = tokens_of(child, spans)
            tokens_in, tokens_out = tokens_in + child_in, tokens_out + child_out
    return tokens_in, tokens_out


def print_tree(ctx, spans, parent_id=None, prefix=""):
    children = [s for s in spans if s["parent_id"] == parent_id]
    for index, span in enumerate(children):
        last = index == len(children) - 1
        branch = "`- " if last else "|- "
        tokens_in, tokens_out = tokens_of(span, spans)
        cost = (tokens_in * PRICE_IN_PER_MILLION + tokens_out * PRICE_OUT_PER_MILLION) / 1_000_000
        label = f"{prefix}{branch}{span['kind']:<5} {span['name']}"
        ctx.note(f"{label:<34} {seconds(span):6.2f}s   {tokens_in:>5} in {tokens_out:>5} out   ${cost:.6f}")
        print_tree(ctx, spans, span["id"], prefix + ("   " if last else "|  "))


def usage_numbers(response):
    usage = getattr(response, "usage", None)
    return getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None)


@lesson("10.1/1", "Tracing by hand")
def main(ctx):
    tracer = Tracer()

    ctx.step("Run a two-step chain inside spans")
    ctx.note("The chain: classify the ticket (model call 1), then write a reply that uses the category (model call 2).")
    ctx.note("Each step runs inside `with tracer.span(...)`. The outer span is the whole chain.")

    with tracer.span("helpdesk_reply", "chain", {"ticket": TICKET}) as root:
        with tracer.span("classify", "llm", {"ticket": TICKET}) as span:
            messages = [
                {"role": "system", "content": "Classify the IT helpdesk ticket. Answer with exactly one word from: " + ", ".join(CATEGORIES) + "."},
                {"role": "user", "content": TICKET},
            ]
            span["inputs"] = {"messages": messages}
            response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, temperature=0)
            ctx.record_usage(response.usage, quiet=True)
            answer = (response.choices[0].message.content or "").strip().lower()
            category = next((c for c in CATEGORIES if c in answer), "other")
            span["outputs"] = {"raw": answer, "category": category}
            span["tokens_in"], span["tokens_out"] = usage_numbers(response)
        ctx.note(f"classify -> {category!r} (raw reply: {answer[:60]!r})")

        with tracer.span("reply", "llm", {"category": category}) as span:
            messages = [
                {"role": "system", "content": f"You are the Larkspur Labs IT helpdesk. The ticket is a {category} problem. Reply to the employee in at most three short sentences."},
                {"role": "user", "content": TICKET},
            ]
            span["inputs"] = {"messages": messages}
            response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, temperature=0.3)
            ctx.record_usage(response.usage, quiet=True)
            reply = response.choices[0].message.content or ""
            span["outputs"] = {"reply": reply}
            span["tokens_in"], span["tokens_out"] = usage_numbers(response)
        ctx.show_messages([{"role": "assistant", "content": reply}], label="Reply produced by the chain")
        root["outputs"] = {"category": category, "reply": reply}

    ctx.step("Print the trace as a tree")
    ctx.note("Latency is wall-clock time per span. A parent's tokens are the sum of its children's.")
    ctx.note(f"Cost uses invented example prices: ${PRICE_IN_PER_MILLION}/M in, ${PRICE_OUT_PER_MILLION}/M out.")
    print_tree(ctx, tracer.spans)
    if any(s["tokens_in"] is None for s in tracer.spans if s["kind"] == "llm"):
        ctx.note("Some model calls reported no usage, so their tokens count as 0 here.")
    overhead = seconds(root) - sum(seconds(s) for s in tracer.spans if s["parent_id"] == root["id"])
    ctx.note(f"Time in the chain but outside any model call (our own code): {overhead * 1000:.1f} ms")

    ctx.step("Look at one span the way a tracing tool stores it")
    first = tracer.spans[1]
    shown = {**first, "start": None, "end": None}
    shown["start_ms"] = round((first["start"] - root["start"]) * 1000, 1)  # offsets from the start of the trace
    shown["end_ms"] = round((first["end"] - root["start"]) * 1000, 1)
    del shown["start"], shown["end"]
    ctx.show_data("The 'classify' span", shown)
    ctx.note("parent_id links it to the chain span; that link is all a tool needs to draw the tree.")


if __name__ == "__main__":
    main()
