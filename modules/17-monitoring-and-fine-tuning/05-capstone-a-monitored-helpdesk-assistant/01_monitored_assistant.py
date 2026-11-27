"""17.5/1  The monitored assistant: logs, traces, metrics and a budget guard in one wrapper

Capstone. This wraps the helpdesk assistant from module 01 (classify, then reply) so every ticket leaves:
  - a JSON log line carrying the trace id (17.1),
  - a trace with classify and reply spans (17.1),
  - metrics for requests, latency, tokens, dollars and budget left, named as the 17.2 dashboard expects,
  - a budget guard that checks before each model call (17.3).
Six tickets run with plenty of budget. Then you read back the log, one trace and the metrics.
Scripts 2 and 3 have their own copy of this wrapper (lessons never import each other).

Run it:   ./run 17.5/1          (Windows: run 17.5/1)
     or:  python modules/17-monitoring-and-fine-tuning/05-capstone-a-monitored-helpdesk-assistant/01_monitored_assistant.py
"""

import io
import json
import logging
import time
from pathlib import Path

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

from labkit import lesson


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"event": record.getMessage(), **getattr(record, "fields", {})}, sort_keys=True)


log = logging.getLogger("helpdesk.capstone")
log.propagate = False
LOG_BUFFER = io.StringIO()
_handler = logging.StreamHandler(LOG_BUFFER)
_handler.setFormatter(JsonFormatter())
log.handlers = [_handler]
log.setLevel(logging.INFO)

CATEGORIES = ("network", "hardware", "software", "access", "other")
PRICE_IN_PER_M = 0.50  # invented prices, dollars per million tokens
PRICE_OUT_PER_M = 1.50
TICKETS = json.loads(Path(__file__).with_name("tickets.json").read_text(encoding="utf-8"))


class BudgetExceeded(Exception):
    pass


class BudgetGuard:
    """Checks before each model call, charges after it. Estimates tokens when the endpoint reports none."""

    def __init__(self, max_dollars, max_calls):
        self.max_dollars, self.max_calls = max_dollars, max_calls
        self.dollars, self.calls = 0.0, 0

    def check(self):
        if self.calls >= self.max_calls:
            raise BudgetExceeded(f"call cap {self.max_calls} reached")
        if self.dollars >= self.max_dollars:
            raise BudgetExceeded(f"dollar cap ${self.max_dollars:.6f} reached")

    def charge(self, usage, prompt, reply):
        t_in, t_out = getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None)
        if t_in is None or t_out is None:
            t_in, t_out = max(1, len(prompt) // 4), max(1, len(reply) // 4)
        self.calls += 1
        cost = t_in * PRICE_IN_PER_M / 1e6 + t_out * PRICE_OUT_PER_M / 1e6
        self.dollars += cost
        return t_in, t_out, cost


class Assistant:
    """The helpdesk assistant with logs, traces, metrics and a budget guard around every model call."""

    def __init__(self, ctx, guard, extra_processors=()):
        self.ctx, self.guard = ctx, guard
        self.reg = CollectorRegistry()
        self.requests = Counter("helpdesk_requests_total", "Tickets handled", ["category", "status"], registry=self.reg)
        self.latency = Histogram("helpdesk_llm_latency_seconds", "Model call latency", buckets=(0.25, 0.5, 1, 2, 5, 10), registry=self.reg)
        self.tokens = Counter("helpdesk_llm_tokens_total", "Tokens used", ["direction"], registry=self.reg)
        self.cost = Counter("helpdesk_llm_cost_dollars_total", "Estimated spend", registry=self.reg)
        self.left = Gauge("helpdesk_budget_remaining_dollars", "Budget minus spend", registry=self.reg)
        self.left.set(guard.max_dollars)
        self.exporter = InMemorySpanExporter()
        provider = TracerProvider(resource=Resource.create({"service.name": "larkspur-helpdesk"}))
        provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        for p in extra_processors:
            provider.add_span_processor(p)
        self.provider = provider
        self.tracer = provider.get_tracer("larkspur.helpdesk")
        self.records = []  # one dict per ticket, for the SLO report

    def _call(self, span, system, user):
        self.guard.check()  # raises BudgetExceeded BEFORE any money is spent
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        start = time.perf_counter()
        try:
            r = self.ctx.client.chat.completions.create(model=self.ctx.model, messages=messages)
        finally:
            self.latency.observe(time.perf_counter() - start)
        text = (r.choices[0].message.content or "").strip()
        t_in, t_out, dollars = self.guard.charge(r.usage, system + user, text)
        self.ctx.record_usage(r.usage, quiet=True)
        self.tokens.labels(direction="in").inc(t_in)
        self.tokens.labels(direction="out").inc(t_out)
        self.cost.inc(dollars)
        self.left.set(max(0.0, self.guard.max_dollars - self.guard.dollars))
        span.set_attribute("llm.tokens.in", t_in)
        span.set_attribute("llm.tokens.out", t_out)
        return text

    def handle(self, ticket):
        """One ticket: classify, then reply. Returns a record; never raises for model or budget problems."""
        category, status, reply, trace_id = "other", "ok", "", ""
        began = time.perf_counter()
        with self.tracer.start_as_current_span("handle_ticket") as root:
            root.set_attribute("ticket.id", ticket["id"])
            trace_id = format(root.get_span_context().trace_id, "032x")
            try:
                with self.tracer.start_as_current_span("classify") as span:
                    word = self._call(span, "Classify the IT ticket as one of: " + ", ".join(CATEGORIES) + ". Answer with the single word.", ticket["text"])
                    guess = (word.split() or ["other"])[0].strip(".,").lower()
                    category = guess if guess in CATEGORIES else "other"
                    span.set_attribute("ticket.category", category)
                with self.tracer.start_as_current_span("reply") as span:
                    reply = self._call(span, f"You are the Larkspur Labs IT helpdesk. Category: {category}. Reply in two sentences.", ticket["text"])
            except BudgetExceeded as exc:
                status = "blocked"
                root.set_attribute("budget.blocked", str(exc))
            except Exception as exc:  # a model error is a data point, not a crash
                status = "error"
                root.set_attribute("error.type", type(exc).__name__)
            root.set_attribute("ticket.category", category)
            root.set_attribute("ticket.status", status)
        seconds = time.perf_counter() - began
        self.requests.labels(category=category, status=status).inc()
        log.info("ticket", extra={"fields": {"id": ticket["id"], "category": category, "status": status, "trace_id": trace_id, "seconds": round(seconds, 2)}})
        record = {"id": ticket["id"], "category": category, "status": status, "reply": reply, "seconds": seconds, "trace_id": trace_id}
        self.records.append(record)
        return record


def sample(registry, name, **labels):
    """Read one value back out of the registry (what a scrape of /metrics would contain)."""
    value = registry.get_sample_value(name, labels)
    return 0.0 if value is None else value


def print_tree(spans, console, only_trace=None):
    children = {}
    for s in spans:
        if only_trace and format(s.context.trace_id, "032x") != only_trace:
            continue
        children.setdefault(s.parent.span_id if s.parent else None, []).append(s)

    def walk(parent, depth):
        for s in sorted(children.get(parent, []), key=lambda x: x.start_time):
            keep = ("ticket.category", "ticket.status", "llm.tokens.in", "llm.tokens.out", "budget.blocked")
            attrs = ", ".join(f"{k}={v}" for k, v in s.attributes.items() if k in keep)
            console.print(f"{'  ' * depth}- {s.name} ({(s.end_time - s.start_time) / 1e6:.0f} ms) {attrs}", markup=False, highlight=False)
            walk(s.context.span_id, depth + 1)

    walk(None, 0)


@lesson("17.5/1", "The monitored assistant")
def main(ctx):
    ctx.step("Build the assistant with a comfortable budget")
    assistant = Assistant(ctx, BudgetGuard(max_dollars=0.01, max_calls=40))
    ctx.note("Budget: $0.01 and 40 calls for six tickets (twelve calls). That is plenty, so nothing should be blocked.")

    ctx.step("Handle the six tickets")
    for ticket in TICKETS:
        rec = assistant.handle(ticket)
        ctx.console.print(f"{rec['id']}  {rec['category']:9} {rec['status']:8} {rec['seconds']:.1f}s  {rec['reply'][:70]}", markup=False)

    ctx.step("Read the logs (pillar 1)")
    for line in LOG_BUFFER.getvalue().splitlines()[:3]:
        ctx.console.print(line, markup=False, highlight=False)
    ctx.note("... one line per ticket, each with its trace id.")

    ctx.step("Read one trace (pillar 2)")
    print_tree(assistant.exporter.get_finished_spans(), ctx.console, only_trace=assistant.records[0]["trace_id"])

    ctx.step("Read the metrics (pillar 3)")
    text = generate_latest(assistant.reg).decode("utf-8")
    for line in text.splitlines():
        if line.startswith("helpdesk_") and "_bucket" not in line and "_created" not in line:
            ctx.console.print(line, markup=False, highlight=False)
    ok = sum(1 for r in assistant.records if r["status"] == "ok")
    ctx.note(f"{ok} of {len(assistant.records)} tickets ok. Next, script 2 shrinks the budget and checks the SLO.")


if __name__ == "__main__":
    main()
