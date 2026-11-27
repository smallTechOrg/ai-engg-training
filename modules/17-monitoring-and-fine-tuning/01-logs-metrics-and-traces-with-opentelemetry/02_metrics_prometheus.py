"""17.1/2  Metrics for an LLM app with prometheus_client

Counters, a Histogram and a Gauge for requests, latency, tokens and cost. We make a few real model
calls, then print what Prometheus would scrape from /metrics (the text exposition format).
No server is started: generate_latest() gives the same text your /metrics endpoint would return.

Run it:   ./run 17.1/2          (Windows: run 17.1/2)
     or:  python modules/17-monitoring-and-fine-tuning/01-logs-metrics-and-traces-with-opentelemetry/02_metrics_prometheus.py
"""

import time

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

from labkit import lesson

# Invented prices (per 1 million tokens, in dollars). Use your provider's real price list.
PRICE_IN_PER_M = 0.50
PRICE_OUT_PER_M = 1.50
MONTHLY_BUDGET_USD = 25.0

TICKETS = [
    ("network", "The office wifi drops every ten minutes."),
    ("account", "I am locked out of my Larkspur Labs account."),
    ("hardware", "My docking station does not charge my laptop."),
    ("software", "The VPN client crashes when I open it."),
]


@lesson("17.1/2", "Metrics for an LLM app with prometheus_client")
def main(ctx):
    ctx.step("Define the metrics")
    ctx.note("A private registry keeps this lesson tidy; in a real service you would use the default one.")
    reg = CollectorRegistry()
    requests = Counter("helpdesk_requests_total", "Model calls made", ["category", "status"], registry=reg)
    latency = Histogram("helpdesk_llm_latency_seconds", "Model call latency", buckets=(0.25, 0.5, 1, 2, 5, 10), registry=reg)
    tokens = Counter("helpdesk_llm_tokens_total", "Tokens used", ["direction"], registry=reg)
    cost = Counter("helpdesk_llm_cost_dollars_total", "Estimated spend", registry=reg)
    budget_left = Gauge("helpdesk_budget_remaining_dollars", "Monthly budget minus spend so far", registry=reg)
    budget_left.set(MONTHLY_BUDGET_USD)
    ctx.note("Counter: only goes up (requests, tokens, cost). Histogram: latency buckets. Gauge: a value that moves both ways.")
    ctx.note("Keep label values few and fixed (category, status). Never label by user id or ticket text: every distinct value is a new time series.")

    ctx.step("Make a few real calls and record each one")
    for category, text in TICKETS:
        messages = [
            {"role": "system", "content": "You are the Larkspur Labs IT helpdesk. Reply in one short sentence."},
            {"role": "user", "content": text},
        ]
        start = time.perf_counter()
        status = "ok"
        try:
            r = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
        except Exception as exc:  # an error is also a data point
            status = "error"
            ctx.note(f"call failed: {type(exc).__name__}")
            r = None
        latency.observe(time.perf_counter() - start)
        requests.labels(category=category, status=status).inc()
        if r is not None:
            ctx.record_usage(r.usage, quiet=True)
            t_in = getattr(r.usage, "prompt_tokens", None) or 0
            t_out = getattr(r.usage, "completion_tokens", None) or 0
            usd = t_in / 1e6 * PRICE_IN_PER_M + t_out / 1e6 * PRICE_OUT_PER_M
            tokens.labels(direction="in").inc(t_in)
            tokens.labels(direction="out").inc(t_out)
            cost.inc(usd)
            budget_left.dec(usd)
            ctx.note(f"{category}: {t_in} in, {t_out} out, ${usd:.6f}")

    ctx.step("What Prometheus would scrape from /metrics")
    ctx.note("This is the exposition format: one line per time series. Histograms expand to _bucket, _sum and _count lines.")
    text = generate_latest(reg).decode()
    for line in text.splitlines():
        if line.startswith("#") or "_created" in line:
            continue  # hide comments and creation timestamps to keep the output short
        ctx.console.print(line, markup=False, highlight=False)
    ctx.note("Prometheus stores these every scrape interval; PromQL (see the README) turns them into rates and percentiles.")


if __name__ == "__main__":
    main()
