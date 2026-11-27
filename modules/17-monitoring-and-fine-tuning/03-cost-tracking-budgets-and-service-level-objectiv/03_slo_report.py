"""17.3/3  Service level objectives from run logs

An SLO (service level objective) turns a metric into a promise: "99% of calls succeed" and "95%
of calls finish in under 5 seconds". The gap to 100% is the ERROR BUDGET, the amount of failure
you are allowed. The log file records each HTTP request and response with a timestamp `t`, so
you can work out latency and success offline. The script makes three real calls, reads all
logs, then computes:
  - the two SLIs (service level indicators, the measurements) and whether each SLO is met,
  - how much error budget is left,
  - the burn rate: how fast the budget is being used compared with the allowed pace,
  - a what-if with simulated failures, clearly labelled as simulated.

Run it:   ./run 17.3/3          (Windows: run 17.3/3)
     or:  python modules/17-monitoring-and-fine-tuning/03-cost-tracking-budgets-and-service-level-objectiv/03_slo_report.py
"""

import json
import math

from labkit import lesson
from labkit.config import state_dir

AVAILABILITY_SLO = 0.99  # share of calls that must succeed
LATENCY_SLO = 0.95  # share of calls that must finish within the threshold
LATENCY_THRESHOLD_S = 5.0


def read_calls(folder):
    """Pair each wire request with the next wire response in the same file: (latency_seconds, ok)."""
    calls = []
    for path in sorted(folder.glob("*.jsonl")):
        pending = None
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("event") != "wire":
                continue
            if e.get("direction") == "request":
                pending = e.get("t")
            elif e.get("direction") == "response" and pending is not None:
                ok = str(e.get("summary", "")).startswith("2")
                calls.append((max(e.get("t", pending) - pending, 0.0), ok))
                pending = None
    return calls


def percentile(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1)]


def report(ctx, calls, label):
    n = len(calls)
    good = sum(1 for _, ok in calls if ok)
    fast = sum(1 for lat, ok in calls if ok and lat <= LATENCY_THRESHOLD_S)
    avail, quick = good / n, fast / max(good, 1)
    ctx.console.print(f"[{label}] {n} calls | availability {avail:.2%} (SLO {AVAILABILITY_SLO:.0%}) | within {LATENCY_THRESHOLD_S:g}s {quick:.2%} (SLO {LATENCY_SLO:.0%})", markup=False)
    budget = (1 - AVAILABILITY_SLO) * n  # failures you may afford over this window
    used = n - good
    ctx.console.print(f"    error budget: {budget:.1f} failures allowed, {used} used, {budget - used:.1f} left", markup=False)
    burn = (used / n) / (1 - AVAILABILITY_SLO)
    verdict = "on track" if burn <= 1 else "BURNING TOO FAST"
    ctx.console.print(f"    burn rate {burn:.2f}x ({verdict}); 1.0x means the budget lasts exactly the whole window", markup=False)
    return avail >= AVAILABILITY_SLO and quick >= LATENCY_SLO


@lesson("17.3/3", "Service level objectives from run logs")
def main(ctx):
    ctx.step("Make three real calls so the logs are never empty")
    for text in ("The printer on floor 2 is offline.", "I need access to the shared drive.", "My laptop fan is very loud."):
        r = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[{"role": "system", "content": "You are the Larkspur Labs IT helpdesk. Reply in one short sentence."}, {"role": "user", "content": text}],
        )
        ctx.show_response(r)

    ctx.step("Read request/response pairs from every run log")
    calls = read_calls(state_dir("logs"))
    if not calls:
        ctx.note("No request/response pairs found in the logs, so there is nothing to report.")
        return
    lats = [lat for lat, ok in calls if ok]
    ctx.note(f"{len(calls)} calls found. Latency: median {percentile(lats, 0.5):.2f}s, p95 {percentile(lats, 0.95):.2f}s, max {max(lats):.2f}s.")
    ctx.note("Percentiles beat averages: one 30-second call can hide inside a good average.")

    ctx.step("Evaluate the SLOs on the real data")
    met = report(ctx, calls, "real")
    ctx.note("SLOs met." if met else "At least one SLO is missed on this sample.")

    ctx.step("What if? Simulate failures (NOT real data)")
    ctx.note("We copy the real calls and mark 3 as failed, to see what 3 errors do to the budget.")
    simulated = [(lat, ok and i >= 3) for i, (lat, ok) in enumerate(calls)]
    report(ctx, simulated, "simulated")
    ctx.note("Alert on burn rate (say, 'page when the 1-hour burn rate passes 14x'). It catches a fast outage early and ignores a slow trickle you can live with.")
    ctx.note("The same SLI in PromQL: sum(rate(helpdesk_requests_total{status='ok'}[30d])) / sum(rate(helpdesk_requests_total[30d]))")


if __name__ == "__main__":
    main()
