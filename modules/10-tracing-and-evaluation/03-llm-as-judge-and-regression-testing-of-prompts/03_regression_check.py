"""10.3/3  Scenario: regression testing a prompt change against a baseline

Prompts regress silently: someone shortens the prompt to save tokens and replies get worse.
A regression test keeps the scores of the current prompt as a BASELINE and compares every
candidate to it, metric by metric, allowing a small tolerance for noise.

Here the baseline is prompt v2 (good). The candidate is v3, an over-eager "be brief" edit that
many teams would make. The script evaluates both (4 batched model calls), compares and prints
a verdict. 10.4 turns the verdict into an exit code that fails a build.

Run it:   ./run 10.3/3          (Windows: run 10.3/3)
"""

import json
import tempfile
from pathlib import Path

from labkit import lesson

GOLDEN = Path(__file__).with_name("golden.json")
TOLERANCE = 0.13  # one row of eight is 0.125; smaller drops are treated as noise

FORMAT = """Reply with only a JSON object: {"results": [{"id": "G-00", "category": "<network|hardware|software|access|other>", "reply": "<reply to the employee>"}]}
One entry per ticket, same order, id copied exactly."""

PROMPTS = {
    "v2 (baseline)": (
        "You are the Larkspur Labs IT helpdesk assistant. You receive several tickets at once.\n" + FORMAT + "\n"
        "Rules for every reply: at most 40 words; name the product or device the employee mentioned; give one concrete next step the employee can take now; "
        "if there is a safety risk, say so first; never claim you have already done something (you cannot reset, order or dispatch anything: say what the IT team will do instead)."
    ),
    "v3 (candidate)": (
        "You are the Larkspur Labs IT helpdesk assistant. You receive several tickets at once.\n" + FORMAT + "\n"
        "Be extremely brief: every reply is at most 6 words, with no explanations and no advice."
    ),
}

JUDGE_PROMPT = """You are a strict reviewer of IT helpdesk replies at Larkspur Labs. You receive several tickets, each with a candidate reply.
Score every reply on two criteria, each an integer from 1 (very poor) to 5 (excellent):
- actionable: 5 = the employee knows exactly what to do next; 1 = no next step.
- safety_first: 5 = any safety risk or urgency in the ticket is acknowledged; 1 = a risk is ignored. Score 5 if the ticket has no risk.
Reply with only JSON: {"scores": [{"id": "G-00", "actionable": 1, "safety_first": 1}]}
One entry per reply, ids copied exactly."""


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


def score_prompt(ctx, system, cases):
    tickets = "\n\n".join(f'<ticket id="{c["id"]}">\n{c["ticket"]}\n</ticket>' for c in cases)
    outputs = parse_list(call_json(ctx, system, tickets), "results")
    m = {"exact_match": 0.0, "keywords": 0.0}
    for c in cases:
        out = outputs.get(c["id"], {})
        m["exact_match"] += lower(out.get("category")) == c["expected_category"]
        m["keywords"] += bool(out) and all(k.lower() in lower(out.get("reply")) for k in c["must_mention"])
    m = {k: v / len(cases) for k, v in m.items()}
    pairs = "\n\n".join(
        f'<ticket id="{c["id"]}">\n{c["ticket"]}\n</ticket>\n<reply id="{c["id"]}">\n{outputs.get(c["id"], {}).get("reply", "")}\n</reply>' for c in cases
    )
    judged = parse_list(call_json(ctx, JUDGE_PROMPT, pairs), "scores")
    for criterion in ["actionable", "safety_first"]:
        values = [judged[c["id"]][criterion] for c in cases if isinstance(judged.get(c["id"], {}).get(criterion), (int, float))]
        m[f"judge:{criterion}"] = sum(values) / len(values) / 5 if values else 0.0  # not judged counts as 0, never as a pass
    return {k: round(v, 3) for k, v in m.items()}


def compare(baseline, candidate, tolerance):
    """Return rows of (metric, baseline, candidate, delta, status). Status is OK, IMPROVED or REGRESSED."""
    rows = []
    for metric, base in baseline.items():
        delta = candidate[metric] - base
        status = "REGRESSED" if delta < -tolerance else "IMPROVED" if delta > tolerance else "ok"
        rows.append((metric, base, candidate[metric], delta, status))
    return rows


@lesson("10.3/3", "Regression check: candidate prompt vs stored baseline")
def main(ctx):
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))
    names = list(PROMPTS)

    ctx.step("1. Score the baseline and store it")
    baseline_scores = score_prompt(ctx, PROMPTS[names[0]], cases)
    with tempfile.TemporaryDirectory() as tmp:
        baseline_file = Path(tmp) / "baseline.json"
        baseline_file.write_text(json.dumps({"prompt": names[0], "scores": baseline_scores}, indent=2), encoding="utf-8")
        ctx.note("In a real repo baseline.json is committed; here it lives in a temp folder for the length of the script.")

        ctx.step("2. Score the candidate")
        candidate_scores = score_prompt(ctx, PROMPTS[names[1]], cases)

        ctx.step("3. Compare to the stored baseline, metric by metric")
        stored = json.loads(baseline_file.read_text(encoding="utf-8"))["scores"]
    rows = compare(stored, candidate_scores, TOLERANCE)
    ctx.note(f"tolerance {TOLERANCE} (one row of eight is 0.125)")
    ctx.note(f"{'metric':22}{'baseline':>10}{'candidate':>11}{'delta':>8}  status")
    for metric, base, cand, delta, status in rows:
        ctx.note(f"{metric:22}{base:>10.2f}{cand:>11.2f}{delta:>+8.2f}  {status}")

    ctx.step("4. Verdict")
    regressed = [r[0] for r in rows if r[4] == "REGRESSED"]
    if regressed:
        ctx.note(f"REGRESSION in {', '.join(regressed)}: do not ship the candidate. (10.4 turns this into a failing exit code.)")
    else:
        ctx.note("No metric dropped by more than the tolerance: the candidate may ship (read a sample of replies first).")

    ctx.step("What to notice")
    ctx.note("Shorter prompts and replies are cheaper, so the candidate has a real benefit. The regression test is what puts a price on it.")
    ctx.note("A tolerance matters: re-running the same prompt can move a score by a row. Without one, noise fails builds and people stop trusting the test.")
    ctx.note("An unparseable judge reply scores 0 here, so a broken judge fails loudly instead of silently approving.")


if __name__ == "__main__":
    main()
