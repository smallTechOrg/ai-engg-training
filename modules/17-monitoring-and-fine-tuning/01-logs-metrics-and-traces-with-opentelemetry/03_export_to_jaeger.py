"""17.1/3  Export the same trace to Jaeger over OTLP HTTP

The traced helpdesk call from script 1, but spans go to a real backend through the OTLP HTTP exporter.
Needs OTEL_EXPORTER_OTLP_ENDPOINT in .env pointing at Jaeger (or any OTLP collector), e.g. http://localhost:4318.
Start one with:  docker compose up -d   (from this lesson's folder). Exits with code 3 when it is not reachable.

Run it:   ./run 17.1/3          (Windows: run 17.1/3)
     or:  python modules/17-monitoring-and-fine-tuning/01-logs-metrics-and-traces-with-opentelemetry/03_export_to_jaeger.py
"""

import os

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from labkit import lesson
from labkit.services import require

TICKET = "My laptop cannot join the Larkspur-Staff wifi since this morning's update."
JAEGER_UI = "http://localhost:16686"


@lesson("17.1/3", "Export the same trace to Jaeger over OTLP HTTP")
def main(ctx):
    ctx.step("Check that a trace backend is reachable")
    endpoint = require(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        how_to_start="from this lesson's folder run: docker compose up -d   (Jaeger UI: http://localhost:16686)",
    )
    ctx.note(f"OTLP endpoint: {endpoint}")

    ctx.step("Create a tracer that exports over OTLP HTTP")
    ctx.note("The service.name resource attribute is how Jaeger names your app in its drop-down.")
    provider = TracerProvider(resource=Resource.create({"service.name": "larkspur-helpdesk"}))
    # The HTTP exporter posts to <endpoint>/v1/traces. The env var holds the base URL only.
    exporter = OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces", timeout=5)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    tracer = provider.get_tracer("larkspur.helpdesk")

    ctx.step("Handle one ticket: classify, then reply")
    with tracer.start_as_current_span("handle_ticket") as root:
        root.set_attribute("ticket.chars", len(TICKET))
        category = "other"
        for name, system in (
            ("classify", "Classify the IT ticket as one of: network, hardware, account, software, other. Answer with the single word."),
            ("reply", "You are the Larkspur Labs IT helpdesk. Reply in two sentences."),
        ):
            with tracer.start_as_current_span(name) as span:
                r = ctx.client.chat.completions.create(
                    model=ctx.model,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": TICKET}],
                )
                ctx.record_usage(r.usage, quiet=True)
                text = (r.choices[0].message.content or "").strip()
                span.set_attribute("llm.model", ctx.model)
                span.set_attribute("llm.tokens.in", getattr(r.usage, "prompt_tokens", None) or 0)
                span.set_attribute("llm.tokens.out", getattr(r.usage, "completion_tokens", None) or 0)
                if name == "classify":
                    category = (text.split() or ["other"])[0].strip(".,").lower()
                    span.set_attribute("ticket.category", category)
        root.set_attribute("ticket.category", category)
    ctx.note(f"trace id: {format(root.get_span_context().trace_id, '032x')}")

    ctx.step("Flush the spans to the backend")
    ok = provider.force_flush(timeout_millis=8000)
    provider.shutdown()
    if not ok:
        ctx.note("The exporter could not deliver the spans in time. Check the endpoint (is port 4318 the OTLP HTTP port?). Nothing was lost locally, but Jaeger has no trace.")
        raise SystemExit(1)

    ctx.step("Look at it in Jaeger")
    ctx.note(f"Open {JAEGER_UI} (or your cloud Jaeger), pick service 'larkspur-helpdesk', click Find Traces.")
    ctx.note("The waterfall shows handle_ticket as a wide bar with classify and reply nested under it, one after the other. The gap between them is your own code; the bar lengths are the model calls. Click a span to see llm.model, llm.tokens.in and ticket.category.")


if __name__ == "__main__":
    main()
