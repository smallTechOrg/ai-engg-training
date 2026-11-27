"""16.4/2  Blue/green and canary: a traffic-split simulation

Two ways to put a new version (v2) in front of users while v1 serves them.
  Blue/green: run v2 ("green") beside v1 ("blue"), check it, switch ALL traffic at once, keep blue
              for instant rollback. Simple, but everyone gets v2 at the same moment.
  Canary:     send a small share (5%) to v2, watch error rate, widen in steps, roll back on a bad
              signal. A bad v2 only ever hurts the share it was given.

Both run on a seeded simulation of 1000 requests per minute (no network, no model). v2 has a bug
that fails 20% of requests. The numbers are a model of the idea, not a measurement.

Run it:   ./run 16.4/2          (Windows: run 16.4/2)
"""

import contextlib
import io
import random

from labkit import lesson

REQUESTS_PER_MINUTE = 1000
V1_ERROR, V2_ERROR = 0.01, 0.20  # v2 is a bad release


def minute(rng: random.Random, share_v2: float, v2_error: float) -> tuple[int, int, int]:
    """Serve one minute of traffic; return (v2 requests, v2 errors, total errors)."""
    v2_requests = v2_errors = errors = 0
    for _ in range(REQUESTS_PER_MINUTE):
        to_v2 = rng.random() < share_v2
        failed = rng.random() < (v2_error if to_v2 else V1_ERROR)
        v2_requests += to_v2
        v2_errors += to_v2 and failed
        errors += failed
    return v2_requests, v2_errors, errors


def blue_green(rng: random.Random, v2_error: float) -> dict:
    """Pre-switch smoke test hits v2 with 20 synthetic requests; then 100% switch; a bad signal switches back."""
    smoke_failures = sum(rng.random() < v2_error for _ in range(20))
    if smoke_failures > 2:
        return {"switched": False, "bad_requests": 0, "minutes_bad": 0, "note": f"smoke test caught it ({smoke_failures}/20 failed), nobody saw v2"}
    bad, minutes = 0, 0
    for _ in range(3):  # watch for 3 minutes after the switch
        _, v2_errs, _ = minute(rng, 1.0, v2_error)
        minutes += 1
        bad += v2_errs
        if v2_errs / REQUESTS_PER_MINUTE > 0.05:
            return {"switched": True, "bad_requests": bad, "minutes_bad": minutes, "note": "error rate alarm, switched back to blue"}
    return {"switched": True, "bad_requests": bad, "minutes_bad": 0, "note": "stayed on green"}


def canary(rng: random.Random, v2_error: float, steps=(0.05, 0.25, 0.5, 1.0)) -> dict:
    bad, minutes = 0, 0
    for share in steps:  # hard cap: len(steps) stages
        v2_reqs, v2_errs, _ = minute(rng, share, v2_error)
        minutes += 1
        bad += v2_errs
        rate = v2_errs / max(1, v2_reqs)
        print(f"    canary {share:>4.0%}: {v2_reqs} requests to v2, error rate {rate:.1%}")
        if rate > 0.05:
            return {"bad_requests": bad, "minutes_bad": minutes, "note": f"rolled back at {share:.0%}"}
    return {"bad_requests": bad, "minutes_bad": 0, "note": "promoted to 100%"}


@lesson("16.4/2", "Blue/green and canary traffic-split simulation")
def main(ctx):
    ctx.step("A bad release (v2 fails 20% of requests) with a smoke test that only checks 20 requests")
    # The seed is chosen so the smoke test passes by luck, which is the realistic danger.
    for seed in range(200):
        if blue_green(random.Random(seed), V2_ERROR)["switched"]:
            break
    result = blue_green(random.Random(seed), V2_ERROR)
    print(f"  blue/green: {result['note']}; bad requests before rollback: {result['bad_requests']}")
    ctx.note("Blue/green is as safe as its pre-switch checks. Once switched, 100% of users get v2 until the alarm fires.")

    ctx.step("The same bad release as a canary")
    result = canary(random.Random(seed), V2_ERROR)
    print(f"  canary: {result['note']}; bad requests before rollback: {result['bad_requests']}")
    ctx.note("The canary stopped at the first step, so only about 5% of one minute of traffic ever saw v2.")

    ctx.step("A good release (v2 fails 1%, like v1)")
    result = canary(random.Random(7), V1_ERROR)
    print(f"  canary: {result['note']}")

    ctx.step("Many runs: how many users get hurt by a bad release? (200 seeded runs each)")
    bg = [blue_green(random.Random(s), V2_ERROR)["bad_requests"] for s in range(200)]
    with contextlib.redirect_stdout(io.StringIO()):
        cn = [canary(random.Random(s), V2_ERROR)["bad_requests"] for s in range(200)]
    print(f"  blue/green: average {sum(bg) / len(bg):.0f} failed requests per bad release, worst {max(bg)}")
    print(f"  canary:     average {sum(cn) / len(cn):.0f} failed requests per bad release, worst {max(cn)}")

    ctx.step("Choosing")
    print("  blue/green: database migrations or protocol changes that cannot serve two versions; instant full rollback.")
    print("  canary:     most LLM changes (prompt, model, tool set): quality problems only show on real traffic.")
    print("  both:       need a rollback that is one command, and a health signal that is not 'the pod started'.")


if __name__ == "__main__":
    main()
