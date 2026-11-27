"""17.5/3  Serve the metrics, scrape them, evaluate alert rules, optionally export traces

The monitored assistant (copied from script 1) runs the batch, serves its metrics on a free
loopback port, and we scrape them back with an HTTP GET like Prometheus would. Three alert rules
are then evaluated on the scraped numbers in plain Python, with the PromQL you would use in
Prometheus shown next to each:
  error ratio above 5%, any blocked ticket, budget left under 20%.
If an OTLP endpoint is configured and reachable (OTEL_EXPORTER_OTLP_ENDPOINT, e.g. Jaeger), the
traces are also exported there; if not, the script says so and carries on. No service is required.

Run it:   ./run 17.5/3          (Windows: run 17.5/3)
     or:  python modules/17-monitoring-and-fine-tuning/05-capstone-a-monitored-helpdesk-assistant/03_serve_scrape_and_alert.py
"""

import io
import json
import logging
import time
import os
import urllib.request
from pathlib import Path

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import start_http_server
from prometheus_client.parser import text_string_to_metric_families

from labkit.services import SERVICES, probe

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


@lesson("17.5/3", "Serve, scrape, alert")
def main(ctx):
    ctx.step("Is a trace backend configured and reachable?")
    processors = []
    state, detail = probe(SERVICES["OTEL_EXPORTER_OTLP_ENDPOINT"])
    if state == "ok":
        endpoint = os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"].strip().rstrip("/")
        processors.append(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint + "/v1/traces", timeout=5)))
        ctx.note(f"Yes: exporting traces to the OTLP endpoint ({detail}).")
    else:
        ctx.note(f"No ({detail}). Traces stay in memory only. Start Jaeger with the compose file in lesson 17.1 to see them in a UI.")

    ctx.step("Run the batch with a budget that leaves room to spare")
    assistant = Assistant(ctx, BudgetGuard(max_dollars=0.01, max_calls=40), extra_processors=processors)
    for ticket in TICKETS:
        rec = assistant.handle(ticket)
        ctx.console.print(f"{rec['id']}  {rec['status']:8} {rec['category']}", markup=False)

    ctx.step("Serve the metrics on a free port and scrape them")
    server, _thread = start_http_server(0, addr="127.0.0.1", registry=assistant.reg)
    port = server.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5) as resp:
        body = resp.read().decode("utf-8")
    server.shutdown()
    values = {}
    for family in text_string_to_metric_families(body):
        for s in family.samples:
            values[(s.name, tuple(sorted(s.labels.items())))] = s.value
    ctx.note(f"scraped {len(body.splitlines())} lines from http://127.0.0.1:{port}/metrics")

    ctx.step("Evaluate three alert rules on the scraped values")
    total = sum(v for (n, _), v in values.items() if n == "helpdesk_requests_total")
    errors = sum(v for (n, lab), v in values.items() if n == "helpdesk_requests_total" and ("status", "error") in lab)
    blocked = sum(v for (n, lab), v in values.items() if n == "helpdesk_requests_total" and ("status", "blocked") in lab)
    left = values.get(("helpdesk_budget_remaining_dollars", ()), 0.0)
    rules = [
        ("error ratio above 5%", errors / total > 0.05 if total else False, 'sum(rate(helpdesk_requests_total{status="error"}[5m])) / sum(rate(helpdesk_requests_total[5m])) > 0.05'),
        ("a ticket was blocked by the budget", blocked > 0, 'increase(helpdesk_requests_total{status="blocked"}[10m]) > 0'),
        ("less than 20% of the budget left", left < 0.2 * assistant.guard.max_dollars, "helpdesk_budget_remaining_dollars < 0.2 * 0.01"),
    ]
    for name, firing, promql in rules:
        ctx.console.print(f"{'FIRING ' if firing else 'quiet  '} {name}", markup=False)
        ctx.console.print(f"         PromQL: {promql}", markup=False, highlight=False)
    ctx.note(f"{int(total)} tickets, {int(errors)} errors, {int(blocked)} blocked, ${left:.6f} budget left.")
    ctx.note("In Prometheus these rules live in a rules file and Alertmanager sends the notification. Here we only evaluate them; no alert is sent.")

    ctx.step("Flush traces")
    assistant.provider.force_flush(timeout_millis=5000)
    assistant.provider.shutdown()
    ctx.note("Done. Metrics were scraped over HTTP; traces were " + ("sent to the OTLP endpoint." if processors else "kept in memory."))


if __name__ == "__main__":
    main()
