"""10.4/2  Prompt regression: compare a candidate prompt with the committed baseline

baseline.json is a file in the repository: the metrics of the prompt we currently ship. A
change to the prompt is accepted only if no metric falls more than a tolerance below it. The
tolerance (in thresholds.json) exists because one row of eight is worth 0.125.

Pick the candidate with an argument:  ./run 10.4/2            the current prompt (should pass)
                                      ./run 10.4/2 --degrade  an "extremely brief" edit (should regress)
(2 model calls either way.)

Run it:   ./run 10.4/2          (Windows: run 10.4/2)
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




def compare(baseline, candidate, max_drop):
    """Rows of (metric, baseline, candidate, delta, status)."""
    rows = []
    for metric, base in baseline.items():
        value = candidate.get(metric, 0.0)
        delta = value - base
        rows.append((metric, base, value, delta, "REGRESSED" if delta < -max_drop else "ok"))
    return rows


@lesson("10.4/2", "Prompt regression against the committed baseline")
def main(ctx):
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))
    baseline = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))
    max_drop = json.loads((HERE / "thresholds.json").read_text(encoding="utf-8"))["max_drop_from_baseline"]
    degrade = "--degrade" in sys.argv[1:]

    ctx.step("1. The baseline and the candidate")
    ctx.note(f"baseline: {baseline['prompt']} (from baseline.json)   allowed drop per metric: {max_drop}")
    ctx.note("candidate: " + ("DEGRADED prompt (6 words max, no advice)" if degrade else "the current prompt, unchanged"))

    ctx.step("2. Run the suite on the candidate (2 model calls)")
    metrics, outputs = run_suite(ctx, DEGRADED_PROMPT if degrade else CURRENT_PROMPT, cases)

    ctx.step("3. Compare")
    rows = compare(baseline["metrics"], metrics, max_drop)
    ctx.note(f"{'metric':28}{'baseline':>9}{'candidate':>11}{'delta':>8}  status")
    for metric, base, value, delta, status in rows:
        ctx.note(f"{metric:28}{base:>9.2f}{value:>11.2f}{delta:>+8.2f}  {status}")
    bad = [r[0] for r in rows if r[4] == "REGRESSED"]
    ctx.note(("REGRESSED: " + ", ".join(bad)) if bad else "No regression against the baseline.")

    ctx.step("4. A sample reply from the candidate")
    sample = cases[3]["id"]
    ctx.note(f"{sample}: {outputs.get(sample, {}).get('reply', '(missing)')}")

    ctx.step("What to notice")
    ctx.note("The baseline is data in version control: a prompt change and its score change appear in the same pull request.")
    ctx.note("The comparison is relative. It cannot tell you the baseline itself is good enough: that is what absolute floors do (script 3).")


if __name__ == "__main__":
    main()
