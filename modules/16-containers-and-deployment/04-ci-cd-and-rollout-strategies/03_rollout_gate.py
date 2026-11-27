"""16.4/3  The decision at each canary step: promote, hold or roll back

A rollout needs a rule, not a feeling. This script implements a small gate that compares the canary
(v2) against the baseline (v1) on three signals and returns promote / hold / rollback with the reason:
error rate, p95 latency, and a quality score (for an LLM app this could be the share of replies that
pass an offline check, or user thumbs-down rate; here it is a number we feed in). It then replays
four invented releases through the gate. Pure logic, no model call, no network.

Two ideas: compare with the baseline (not an absolute number, because a provider outage hurts both),
and require a minimum sample before trusting a rate (3 errors in 10 requests is noise).

Run it:   ./run 16.4/3          (Windows: run 16.4/3)
"""

from dataclasses import dataclass

from labkit import lesson


@dataclass
class Window:
    requests: int
    errors: int
    p95_ms: float
    quality: float  # share of replies judged good, 0..1


MIN_REQUESTS = 200
MAX_ERROR_INCREASE = 0.02  # absolute: 1% -> 3% is the limit
MAX_LATENCY_RATIO = 1.5
MAX_QUALITY_DROP = 0.05


def gate(baseline: Window, canary: Window) -> tuple[str, str]:
    if canary.requests < MIN_REQUESTS:
        return "hold", f"only {canary.requests} canary requests (need {MIN_REQUESTS}); keep the share and wait"
    base_err, can_err = baseline.errors / baseline.requests, canary.errors / canary.requests
    if can_err - base_err > MAX_ERROR_INCREASE:
        return "rollback", f"error rate {can_err:.1%} vs baseline {base_err:.1%}"
    if canary.p95_ms > baseline.p95_ms * MAX_LATENCY_RATIO:
        return "rollback", f"p95 {canary.p95_ms:.0f} ms vs baseline {baseline.p95_ms:.0f} ms"
    if baseline.quality - canary.quality > MAX_QUALITY_DROP:
        return "rollback", f"quality {canary.quality:.0%} vs baseline {baseline.quality:.0%}"
    return "promote", "all three signals within limits"


RELEASES = {
    "A. Prompt tweak, no change in behaviour": Window(600, 6, 1800, 0.90),
    "B. New model: faster but answers worse": Window(600, 6, 1200, 0.78),
    "C. New tool: a slow lookup added": Window(600, 7, 3400, 0.91),
    "D. Config bug: bad requests": Window(600, 90, 1700, 0.89),
    "E. Looks fine but too little traffic yet": Window(40, 0, 1700, 0.90),
}
BASELINE = Window(5400, 54, 1850, 0.91)


@lesson("16.4/3", "A promote / hold / roll back gate")
def main(ctx):
    ctx.step("Baseline (v1, current production)")
    print(f"  {BASELINE.requests} requests, error rate {BASELINE.errors / BASELINE.requests:.1%}, p95 {BASELINE.p95_ms:.0f} ms, quality {BASELINE.quality:.0%}")

    ctx.step("Five releases through the gate")
    for name, window in RELEASES.items():
        decision, reason = gate(BASELINE, window)
        print(f"  {name}")
        print(f"      canary: {window.requests} req, errors {window.errors / window.requests:.1%}, p95 {window.p95_ms:.0f} ms, quality {window.quality:.0%}")
        print(f"      -> {decision.upper()}: {reason}")

    ctx.step("Why compare with the baseline?")
    outage_base = Window(1000, 300, 9000, 0.40)
    outage_canary = Window(300, 90, 9100, 0.41)
    print("  A provider outage hurts v1 and v2 equally:")
    print(f"    absolute rule (rollback if errors > 5%) would say: ROLLBACK, wrongly blaming v2")
    print(f"    baseline-relative gate says: {gate(outage_base, outage_canary)[0].upper()} ({gate(outage_base, outage_canary)[1]})")
    ctx.note("Rolling back would not have helped, since v1 is failing too. The gate separates 'my release broke' from 'the world broke'.")

    ctx.step("Wiring it to a platform")
    print("  A CI job (ci-workflow.yml, deploy-canary) runs this gate after each step and calls the platform:")
    print("  promote -> raise the share; hold -> wait; rollback -> set traffic to 0% on v2 and fail the job.")
    print("  The three signals come from your metrics system (module 17: Prometheus), never from the app's own claims.")


if __name__ == "__main__":
    main()
