"""20.1/3  Estimate cost and latency before you build

An architecture is also a budget. From the numbers in budget.json (requests per day, model calls
per request, tokens per call, prices, seconds per call) this script computes cost per request,
per day and per month, the expected latency, and checks them against the targets. Then it asks
"what if" questions: more calls per request, a bigger prompt.

All the numbers are assumptions you replace. Prices here are invented; use your provider's.

No model call.

Run it:   ./run 20.1/3          (Windows: run 20.1/3)
"""

import json
from pathlib import Path

from labkit import lesson

FILE = Path(__file__).with_name("budget.json")


def estimate(b):
    tokens_in = b["model_calls_per_request"] * b["input_tokens_per_call"]
    tokens_out = b["model_calls_per_request"] * b["output_tokens_per_call"]
    cost = tokens_in * b["usd_per_million_input_tokens"] / 1e6 + tokens_out * b["usd_per_million_output_tokens"] / 1e6
    return {
        "tokens_per_request": tokens_in + tokens_out,
        "usd_per_request": cost,
        "tokens_per_day": (tokens_in + tokens_out) * b["requests_per_day"],
        "usd_per_month": cost * b["requests_per_day"] * 30,
        "latency": b["retrieval_seconds"] + b["model_calls_per_request"] * b["seconds_per_call"],
    }


def verdicts(b, e):
    return [
        ("daily tokens within cap", e["tokens_per_day"] <= b["daily_token_cap"], f"{e['tokens_per_day']} of {b['daily_token_cap']}"),
        ("monthly cost within ceiling", e["usd_per_month"] <= b["monthly_usd_ceiling"], f"{e['usd_per_month']:.2f} of {b['monthly_usd_ceiling']} USD"),
        ("latency within target", e["latency"] <= b["latency_target_seconds"], f"{e['latency']:.1f}s of {b['latency_target_seconds']}s"),
    ]


@lesson("20.1/3", "Estimate cost and latency before you build")
def main(ctx):
    base = json.loads(FILE.read_text(encoding="utf-8"))

    ctx.step("The baseline from budget.json")
    e = estimate(base)
    ctx.note(f"{e['tokens_per_request']} tokens and {e['usd_per_request'] * 100:.3f} cents per request, {e['latency']:.1f}s expected")
    for name, ok, detail in verdicts(base, e):
        ctx.note(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

    ctx.step("What if the agent loops: 5 model calls per request")
    loop = dict(base, model_calls_per_request=5)
    e2 = estimate(loop)
    for name, ok, detail in verdicts(loop, e2):
        ctx.note(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

    ctx.step("What if retrieval stuffs 6 passages into the prompt: 3000 input tokens per call")
    fat = dict(base, input_tokens_per_call=3000)
    e3 = estimate(fat)
    for name, ok, detail in verdicts(fat, e3):
        ctx.note(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

    ctx.step("Find the breaking point")
    calls = 1
    while estimate(dict(base, model_calls_per_request=calls))["latency"] <= base["latency_target_seconds"] and calls < 50:
        calls += 1
    ctx.note(f"Latency target breaks at {calls} model calls per request; this is why the graph in 20.2 caps calls at 2.")

    ctx.step("Your turn")
    ctx.note("Put your own numbers in budget.json. If a PASS depends on an assumption you have not measured, write it in Open questions.")


if __name__ == "__main__":
    main()
