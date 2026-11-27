"""16.5/3  Capstone, part 3: gate a prompt change before it reaches everyone

A new prompt is a release. This script plays the canary step for real: the SAME four tickets go to
the current prompt (v1, baseline) and a candidate (v2), each ticket one model call (8 calls). It
measures what the gate needs (errors, slowest latency, and a quality score = share of tickets
whose category matches the expected one), then applies the gate from lesson 16.4 and prints
PROMOTE, HOLD or ROLLBACK. With four tickets the sample is tiny; the script says so. A real canary
uses live traffic and hundreds of requests.

Run it:   ./run 16.5/3          (Windows: run 16.5/3)
"""

import json
import time
from pathlib import Path

from labkit import lesson

TICKETS = json.loads((Path(__file__).parent / "tickets.json").read_text(encoding="utf-8"))
CATEGORIES = "network, hardware, software, access, other"
PROMPTS = {
    "v1 (current)": f"Classify the IT ticket. Answer with one word from: {CATEGORIES}.",
    "v2 (candidate)": f"Classify the IT ticket into one of: {CATEGORIES}. A password or account problem is access even if an app is named. Answer with the single word only.",
}
MIN_REQUESTS = 4  # real canaries need hundreds; four is all this lesson can afford
MAX_ERROR_INCREASE, MAX_LATENCY_RATIO, MAX_QUALITY_DROP = 0.02, 1.5, 0.05


def measure(ctx, prompt: str) -> dict:
    errors, slowest, correct = 0, 0.0, 0
    for ticket in TICKETS:  # one call per ticket, hard cap = len(TICKETS)
        started = time.perf_counter()
        try:
            done = ctx.client.chat.completions.create(
                model=ctx.model,
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": ticket["text"]}],
            )
            ctx.record_usage(done.usage, quiet=True)
            reply = (done.choices[0].message.content or "").strip().lower()
            correct += ticket["expected_category"] in reply
        except Exception:
            errors += 1
        slowest = max(slowest, time.perf_counter() - started)
    return {"requests": len(TICKETS), "errors": errors, "slowest_s": slowest, "quality": correct / len(TICKETS)}


def gate(base: dict, cand: dict) -> tuple[str, str]:
    if cand["requests"] < MIN_REQUESTS:
        return "HOLD", "not enough requests"
    if cand["errors"] / cand["requests"] - base["errors"] / base["requests"] > MAX_ERROR_INCREASE:
        return "ROLLBACK", "more errors than the baseline"
    if cand["slowest_s"] > base["slowest_s"] * MAX_LATENCY_RATIO + 1.0:  # +1 s: single calls are noisy
        return "ROLLBACK", f"slowest call {cand['slowest_s']:.1f}s vs baseline {base['slowest_s']:.1f}s"
    if base["quality"] - cand["quality"] > MAX_QUALITY_DROP:
        return "ROLLBACK", f"quality {cand['quality']:.0%} vs baseline {base['quality']:.0%}"
    return "PROMOTE", "signals within limits"


@lesson("16.5/3", "Capstone: gate a prompt change")
def main(ctx):
    results = {}
    for name, prompt in PROMPTS.items():
        ctx.step(f"Measure {name}")
        ctx.show_messages([{"role": "system", "content": prompt}])
        results[name] = measure(ctx, prompt)
        r = results[name]
        print(f"  {r['requests']} tickets, errors {r['errors']}, slowest call {r['slowest_s']:.1f}s, quality {r['quality']:.0%}")

    ctx.step("The gate")
    decision, reason = gate(results["v1 (current)"], results["v2 (candidate)"])
    print(f"  {decision}: {reason}")
    ctx.note("Four tickets is a toy sample: one different answer moves quality by 25 points. Treat this as the shape of the check, not as evidence.")
    ctx.note("In the pipeline (16.4) this decision gates the deploy-canary job; PROMOTE widens the share, ROLLBACK fails the job.")


if __name__ == "__main__":
    main()
