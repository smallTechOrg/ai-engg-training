"""10.4/3  The gate: fail the build when scores drop

A gate turns metrics into a verdict and the verdict into an EXIT CODE, because exit codes are
the only thing every CI system understands (0 = green, anything else = red). Two rules:
  floors:   every metric must be at least its absolute floor (thresholds.json)
  baseline: no metric may fall more than max_drop_from_baseline below baseline.json

Default run (a demonstration, always exits 0): gates BOTH the current prompt and a degraded
one (4 model calls) and prints the exit code CI would have seen for each.
CI run (the real thing):                       ./run 10.4/3 --ci            exits 1 on failure
CI run with a sabotaged prompt, to see red:    ./run 10.4/3 --ci --degrade  (2 model calls)

Run it:   ./run 10.4/3          (Windows: run 10.4/3)
"""

import json
import sys
from pathlib import Path

from labkit import lesson

HERE = Path(__file__).parent
GOLDEN = HERE / "golden.json"
CATEGORIES = ["network", "hardware", "software", "access", "other"]

FORMAT = """Reply with only a JSON object: {"results": [{"id": "G-00", "category": "<network|hardware|software|access|other>", "reply": "<reply to the employee>"}]}
One entry per ticket, same order, id copied exactly."""

CURRENT_PROMPT = (
    "You are the Larkspur Labs IT helpdesk assistant. You receive several tickets at once.\n" + FORMAT + "\n"
    "Rules for every reply: at most 40 words; name the product or device the employee mentioned; give one concrete next step the employee can take now; "
    "if there is a safety risk, say so first; never claim you have already done something (you cannot reset, order or dispatch anything: say what the IT team will do instead)."
)

DEGRADED_PROMPT = (
    "You are the Larkspur Labs IT helpdesk assistant. You receive several tickets at once.\n" + FORMAT + "\n"
    "Be extremely brief: every reply is at most 6 words, with no explanations and no advice."
)

JUDGE_PROMPT = """You are a strict reviewer of IT helpdesk replies at Larkspur Labs. You receive several tickets, each with a candidate reply.
Score every reply on three criteria, each an integer from 1 (very poor) to 5 (excellent):
- no_invented_actions: 5 = promises or claims only things a chat assistant could really do; 1 = claims it already did something (ordered, reset, dispatched, processed).
- actionable: 5 = the employee knows exactly what to do next; 1 = no next step.
- tone: 5 = polite and calm; 1 = rude or dismissive.
Reply with only JSON: {"scores": [{"id": "G-00", "no_invented_actions": 1, "actionable": 1, "tone": 1}]}
One entry per reply, ids copied exactly."""
JUDGE_CRITERIA = ["no_invented_actions", "actionable", "tone"]


def lower(value):
    return str(value or "").strip().lower()


def call_json(ctx, system, user):
    response = ctx.client.chat.completions.create(
        model=ctx.model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    ctx.record_usage(response.usage, quiet=True)
    return response.choices[0].message.content or ""


def parse_list(raw, key):
    try:
        return {item["id"]: item for item in json.loads(raw)[key]}
    except (ValueError, KeyError, TypeError, AttributeError):
        return {}


def run_suite(ctx, system_prompt, cases):
    """The suite: prompt in, {metric: 0..1} out (plus the raw outputs for inspection)."""
    tickets = "\n\n".join(f'<ticket id="{c["id"]}">\n{c["ticket"]}\n</ticket>' for c in cases)
    outputs = parse_list(call_json(ctx, system_prompt, tickets), "results")

    totals = {"exact_match": 0, "max_length": 0, "keywords": 0}
    for c in cases:
        out = outputs.get(c["id"], {})
        reply = lower(out.get("reply"))
        totals["exact_match"] += lower(out.get("category")) == c["expected_category"]
        totals["max_length"] += bool(out) and len(reply.split()) <= 40
        totals["keywords"] += bool(out) and all(k.lower() in reply for k in c["must_mention"])
    metrics = {k: v / len(cases) for k, v in totals.items()}

    pairs = "\n\n".join(
        f'<ticket id="{c["id"]}">\n{c["ticket"]}\n</ticket>\n<reply id="{c["id"]}">\n{outputs.get(c["id"], {}).get("reply", "")}\n</reply>' for c in cases
    )
    judged = parse_list(call_json(ctx, JUDGE_PROMPT, pairs), "scores")
    for criterion in JUDGE_CRITERIA:
        values = [judged[c["id"]][criterion] for c in cases if isinstance(judged.get(c["id"], {}).get(criterion), (int, float))]
        metrics[f"judge_{criterion}"] = sum(values) / len(values) / 5 if values else 0.0  # not judged = 0, never a pass
    return {k: round(v, 3) for k, v in metrics.items()}, outputs




def gate(metrics, baseline, thresholds):
    """Return a list of human-readable failures. An empty list means the build is green."""
    failures = []
    for metric, floor in thresholds["floors"].items():
        value = metrics.get(metric, 0.0)
        if value < floor:
            failures.append(f"{metric} {value:.2f} is below the floor {floor:.2f}")
    for metric, base in baseline["metrics"].items():
        value = metrics.get(metric, 0.0)
        if base - value > thresholds["max_drop_from_baseline"]:
            failures.append(f"{metric} dropped {base - value:.2f} from the baseline {base:.2f}")
    return failures


def verdict(ctx, name, prompt, cases, baseline, thresholds):
    metrics, _ = run_suite(ctx, prompt, cases)
    failures = gate(metrics, baseline, thresholds)
    ctx.note(f"{name}: " + "  ".join(f"{k}={v:.2f}" for k, v in metrics.items()))
    for failure in failures:
        ctx.note(f"  FAIL  {failure}")
    ctx.note(f"{name}: exit code {1 if failures else 0} ({'RED' if failures else 'green'})")
    return failures


RESULT = {"failed": False}  # read by the entry point below, after the lesson runtime has printed its summary


@lesson("10.4/3", "The CI gate: scores below the bar fail the build")
def main(ctx):
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))
    baseline = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))
    thresholds = json.loads((HERE / "thresholds.json").read_text(encoding="utf-8"))
    args = sys.argv[1:]
    ci, degrade = "--ci" in args, "--degrade" in args

    ctx.step("1. The rules (thresholds.json)")
    ctx.show_data("thresholds", thresholds)

    if ci:
        ctx.step("2. CI mode: gate one prompt and exit with the result")
        failures = verdict(ctx, "degraded prompt" if degrade else "current prompt", DEGRADED_PROMPT if degrade else CURRENT_PROMPT, cases, baseline, thresholds)
        RESULT["failed"] = bool(failures)
    else:
        ctx.step("2. Demonstration: gate the current prompt, then a degraded one (4 model calls)")
        verdict(ctx, "current prompt ", CURRENT_PROMPT, cases, baseline, thresholds)
        verdict(ctx, "degraded prompt", DEGRADED_PROMPT, cases, baseline, thresholds)
        ctx.note("This demonstration exits 0 so the course can run it. With --ci the same verdict becomes the process exit code.")

    ctx.step("3. Put it in CI")
    ctx.note("A GitHub Actions step is one line:  run: uv run python modules/10-tracing-and-evaluation/04-capstone-an-evaluation-suite-for-the-helpdesk-as/03_ci_gate.py --ci")
    ctx.note("Run it on pull requests that touch prompts. It costs two model calls, so it is cheap enough to run every time.")

    ctx.step("What to notice")
    ctx.note("Two kinds of rule: floors say 'good enough', the baseline says 'not worse than what we ship'. You usually want both.")
    ctx.note("If the model endpoint is down the lesson runtime already exits non-zero: an unreachable judge must never turn the build green.")


def cli():
    main()
    if RESULT["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
