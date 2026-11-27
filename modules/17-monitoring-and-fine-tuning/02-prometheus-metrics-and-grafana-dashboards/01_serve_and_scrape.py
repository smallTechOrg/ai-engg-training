"""17.2/1  Serve /metrics over HTTP, then scrape it yourself

In 17.1 you printed generate_latest(). Here a real HTTP endpoint serves the metrics
(prometheus_client.start_http_server on a free port), and the script reads them back with a
request to itself, exactly as Prometheus would scrape (collect) them. It parses the text into
samples and works out by hand what rate() and histogram_quantile() would give.

To let a real Prometheus scrape it, set LESSON_METRICS_PORT=8000 in the environment. The
script then serves on that port and waits 60 seconds after the calls.

Run it:   ./run 17.2/1          (Windows: run 17.2/1)
     or:  python modules/17-monitoring-and-fine-tuning/02-prometheus-metrics-and-grafana-dashboards/01_serve_and_scrape.py
"""

import os
import time
import urllib.request

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, start_http_server
from prometheus_client.parser import text_string_to_metric_families

from labkit import lesson

PRICE_IN_PER_M = 0.50  # invented prices, dollars per million tokens
PRICE_OUT_PER_M = 1.50
BUDGET = 25.0
BUCKETS = (0.25, 0.5, 1, 2, 5, 10)

TICKETS = [
    ("network", "The office wifi drops every ten minutes."),
    ("account", "I am locked out of my Larkspur Labs account."),
    ("hardware", "My docking station does not charge my laptop."),
    ("software", "The VPN client crashes when I open it."),
]


@lesson("17.2/1", "Serve /metrics over HTTP, then scrape it yourself")
def main(ctx):
    ctx.step("Define the metrics (same names the Grafana dashboard in this lesson uses)")
    reg = CollectorRegistry()
    requests = Counter("helpdesk_requests_total", "Model calls made", ["category", "status"], registry=reg)
    latency = Histogram("helpdesk_llm_latency_seconds", "Model call latency", buckets=BUCKETS, registry=reg)
    tokens = Counter("helpdesk_llm_tokens_total", "Tokens used", ["direction"], registry=reg)
    cost = Counter("helpdesk_llm_cost_dollars_total", "Estimated spend", registry=reg)
    budget_left = Gauge("helpdesk_budget_remaining_dollars", "Budget minus spend so far", registry=reg)
    budget_left.set(BUDGET)

    ctx.step("Start the metrics server on a free port")
    wanted = os.environ.get("LESSON_METRICS_PORT", "").strip()
    port = int(wanted) if wanted.isdigit() else 0  # 0 = let the OS pick a free port
    server, thread = start_http_server(port, addr="127.0.0.1", registry=reg)
    port = server.server_address[1]
    ctx.note(f"Serving http://127.0.0.1:{port}/metrics from a background thread. Prometheus calls this a 'target'.")

    ctx.step("Make a few real calls and record each one")
    for category, text in TICKETS:
        messages = [
            {"role": "system", "content": "You are the Larkspur Labs IT helpdesk. Reply in one short sentence."},
            {"role": "user", "content": text},
        ]
        start = time.perf_counter()
        status, r = "ok", None
        try:
            r = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
        except Exception as exc:  # an error is also a data point
            status = "error"
            ctx.note(f"call failed: {type(exc).__name__}")
        latency.observe(time.perf_counter() - start)
        requests.labels(category=category, status=status).inc()
        if r is not None:
            t_in = getattr(r.usage, "prompt_tokens", None) or 0
            t_out = getattr(r.usage, "completion_tokens", None) or 0
            tokens.labels(direction="in").inc(t_in)
            tokens.labels(direction="out").inc(t_out)
            dollars = t_in * PRICE_IN_PER_M / 1e6 + t_out * PRICE_OUT_PER_M / 1e6
            cost.inc(dollars)
            budget_left.dec(dollars)
            ctx.show_response(r)  # also records token usage once

    ctx.step("Scrape it like Prometheus does: an HTTP GET to /metrics")
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5) as resp:
        body = resp.read().decode("utf-8")
        ctype = resp.headers.get("Content-Type", "")
    ctx.note(f"HTTP 200, Content-Type: {ctype}, {len(body.splitlines())} lines. The first helpdesk lines:")
    shown = [ln for ln in body.splitlines() if ln.startswith("helpdesk_") and "_bucket" not in ln]
    for line in shown[:8]:
        ctx.console.print(line, markup=False, highlight=False)

    ctx.step("Parse the scraped text into samples")
    samples = {}
    for family in text_string_to_metric_families(body):
        for s in family.samples:
            samples[(s.name, tuple(sorted(s.labels.items())))] = s.value
    ok = samples.get(("helpdesk_requests_total", (("category", "network"), ("status", "ok"))), 0)
    ctx.note(f"{len(samples)} samples parsed. helpdesk_requests_total{{category=network,status=ok}} = {ok:g}")

    ctx.step("Compute by hand what PromQL would say")
    count = samples.get(("helpdesk_llm_latency_seconds_count", ()), 0)
    total = samples.get(("helpdesk_llm_latency_seconds_sum", ()), 0)
    ctx.note(f"average latency = sum / count = {total:.2f} s / {count:g} = {(total / count if count else 0):.2f} s")
    ctx.note("histogram_quantile(0.95, ...) estimates inside the bucket that holds the 95th percentile. Running bucket counts:")
    cumulative = {float(dict(k[1])["le"]): v for k, v in samples.items() if k[0] == "helpdesk_llm_latency_seconds_bucket" and dict(k[1])["le"] != "+Inf"}
    for le in sorted(cumulative):
        ctx.console.print(f"  le={le:g}s  {cumulative[le]:g} of {count:g} calls", markup=False)
    ctx.note("rate() needs two scrapes: (value now - value then) / seconds between. One scrape only gives totals, so dashboards use rate() and increase() on counters.")

    if wanted.isdigit():
        ctx.step("Keep serving so a real Prometheus can scrape")
        ctx.note("Waiting 60 seconds on the port you chose. Check http://localhost:9090/targets.")
        time.sleep(60)
    server.shutdown()


if __name__ == "__main__":
    main()
