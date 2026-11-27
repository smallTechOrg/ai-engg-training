"""17.1/1  Logs, metrics and traces, in one process

Observability means being able to see what your app is doing from the outside. It rests on three
kinds of record, and this script shows two of them with no service running:
  logs    - what happened (one JSON line per event, using Python's standard logging)
  traces  - where the time went (OpenTelemetry spans, each with a parent and children)
  metrics - how much and how often (see script 2)
You wrap a two-step helpdesk call (classify, then reply) and print the spans as a tree.

Run it:   ./run 17.1/1          (Windows: run 17.1/1)
     or:  python modules/17-monitoring-and-fine-tuning/01-logs-metrics-and-traces-with-opentelemetry/01_logs_metrics_traces.py
"""

import io
import json
import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from labkit import lesson

TICKET = "My laptop cannot join the Larkspur-Staff wifi since this morning's update."


class JsonFormatter(logging.Formatter):
    """One JSON object per line: easy for a log platform to index and filter."""

    def format(self, record):
        data = {"level": record.levelname, "event": record.getMessage()}
        data.update(getattr(record, "fields", {}))
        return json.dumps(data, sort_keys=True)


def print_tree(spans, console):
    """Print finished spans as an indented tree using parent_id links."""
    children = {}
    for s in spans:
        parent = s.parent.span_id if s.parent else None
        children.setdefault(parent, []).append(s)

    def walk(parent, depth):
        for s in sorted(children.get(parent, []), key=lambda x: x.start_time):
            ms = (s.end_time - s.start_time) / 1e6
            console.print(f"{'  ' * depth}- {s.name}  ({ms:.0f} ms)")
            for k, v in s.attributes.items():
                console.print(f"{'  ' * depth}    {k} = {v}", markup=False)
            walk(s.context.span_id, depth + 1)

    walk(None, 0)


@lesson("17.1/1", "Logs, metrics and traces, in one process")
def main(ctx):
    ctx.step("Set up structured logging (pillar 1)")
    ctx.note("Standard Python logging, but each record is one JSON object. It stays in memory so we can print it neatly.")
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JsonFormatter())
    log = logging.getLogger("helpdesk")
    log.handlers = [handler]
    log.setLevel(logging.INFO)
    log.propagate = False

    ctx.step("Set up an OpenTelemetry tracer (pillar 2)")
    ctx.note("A TracerProvider makes spans. A SpanProcessor passes finished spans to an exporter, here an in-memory list.")
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("larkspur.helpdesk")  # not the global provider: this lesson stays self-contained

    ctx.step("Handle one ticket: classify, then reply")
    with tracer.start_as_current_span("handle_ticket") as root:
        root.set_attribute("ticket.chars", len(TICKET))

        with tracer.start_as_current_span("classify") as span:  # child of handle_ticket (context propagation)
            messages = [
                {"role": "system", "content": "Classify the IT ticket as one of: network, hardware, account, software, other. Answer with the single word."},
                {"role": "user", "content": TICKET},
            ]
            r = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
            ctx.record_usage(r.usage, quiet=True)
            category = (r.choices[0].message.content or "other").strip().lower().split()[0].strip(".,")
            span.set_attribute("llm.model", ctx.model)
            span.set_attribute("llm.tokens.in", getattr(r.usage, "prompt_tokens", None) or 0)
            span.set_attribute("llm.tokens.out", getattr(r.usage, "completion_tokens", None) or 0)
            span.set_attribute("ticket.category", category)
            log.info("classified", extra={"fields": {"step": "classify", "category": category, "trace_id": format(span.get_span_context().trace_id, "032x")}})

        with tracer.start_as_current_span("reply") as span:
            messages = [
                {"role": "system", "content": f"You are the Larkspur Labs IT helpdesk. The ticket category is {category}. Reply in two sentences."},
                {"role": "user", "content": TICKET},
            ]
            r = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
            ctx.record_usage(r.usage, quiet=True)
            text = r.choices[0].message.content or ""
            span.set_attribute("llm.model", ctx.model)
            span.set_attribute("llm.tokens.in", getattr(r.usage, "prompt_tokens", None) or 0)
            span.set_attribute("llm.tokens.out", getattr(r.usage, "completion_tokens", None) or 0)
            span.set_attribute("reply.chars", len(text))
            log.info("replied", extra={"fields": {"step": "reply", "chars": len(text), "trace_id": format(span.get_span_context().trace_id, "032x")}})
        root.set_attribute("ticket.category", category)

    ctx.step("Read the logs")
    ctx.note("Each line is easy for a program to read and carries the trace_id, so a log line leads you to its trace.")
    for line in buffer.getvalue().splitlines():
        ctx.console.print(line, markup=False, highlight=False)

    ctx.step("Read the trace")
    ctx.note("All spans share one trace id, and each child points at its parent. The durations show where the time went.")
    spans = exporter.get_finished_spans()
    print_tree(spans, ctx.console)
    ctx.note(f"{len(spans)} spans, {len({s.context.trace_id for s in spans})} trace. Metrics (pillar 3) come next in 17.1/2.")


if __name__ == "__main__":
    main()
