"""10.2/3  Scenario: an evaluation report you can keep and compare

Script 2 printed results and forgot them. A useful eval run is a record: which prompt, which
model, when, every output and every score. This script runs the whole golden set in ONE
batched model call, scores it with an `Evaluator` list, builds a report and saves it as JSON
in a temp folder, so the next lesson can compare two runs.

Run it:   ./run 10.2/3          (Windows: run 10.2/3)
"""

import json
import tempfile
import time
from pathlib import Path

from labkit import lesson

GOLDEN = Path(__file__).with_name("golden.json")
CATEGORIES = ["network", "hardware", "software", "access", "other"]

PROMPT_NAME = "helpdesk-v1"
SYSTEM_PROMPT = """You are the Larkspur Labs IT helpdesk assistant. You receive several tickets at once.
Reply with only a JSON object: {"results": [{"id": "G-00", "category": "<network|hardware|software|access|other>", "reply": "<reply to the employee, at most 40 words>"}]}
One entry per ticket, same order, id copied exactly. network = Wi-Fi, VPN. hardware = physical devices. software = apps. access = accounts, passwords, permissions. other = not an IT problem."""


def lower(value):
    return str(value or "").strip().lower()


# An evaluator is (name, function(output_dict, case) -> bool). A list of them is the suite.
EVALUATORS = [
    ("category_allowed", lambda out, case: lower(out.get("category")) in CATEGORIES),
    ("exact_match", lambda out, case: lower(out.get("category")) == case["expected_category"]),
    ("max_length", lambda out, case: len(str(out.get("reply", "")).split()) <= case["max_words"]),
    ("keywords", lambda out, case: all(k.lower() in lower(out.get("reply")) for k in case["must_mention"])),
]


def parse(raw):
    """Return ({id: output}, problem or None). A malformed reply is a result, not a crash."""
    try:
        items = json.loads(raw).get("results")
        return {item["id"]: item for item in items}, None
    except (ValueError, AttributeError, KeyError, TypeError) as error:
        return {}, f"could not parse the reply ({type(error).__name__})"


@lesson("10.2/3", "Helpdesk evaluation report, saved as a run record")
def main(ctx):
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))

    ctx.step("1. One batched call for the whole golden set")
    tickets = "\n\n".join(f'<ticket id="{c["id"]}">\n{c["ticket"]}\n</ticket>' for c in cases)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": tickets}]
    started = time.perf_counter()
    response = ctx.client.chat.completions.create(
        model=ctx.model, messages=messages, response_format={"type": "json_object"}, temperature=0
    )
    seconds = time.perf_counter() - started
    raw = ctx.show_response(response)
    outputs, problem = parse(raw)
    if problem:
        ctx.note(f"Format problem: {problem}. Every row will count as failing: that is how a broken format shows up in a report.")

    ctx.step("2. Score every row with every evaluator")
    rows = []
    for case in cases:
        out = outputs.get(case["id"], {})
        scores = {name: bool(out) and fn(out, case) for name, fn in EVALUATORS}
        rows.append({"id": case["id"], "output": out, "scores": scores})

    ctx.step("3. The report")
    ctx.note(f"{'evaluator':18} {'passed':>8} {'rate':>7}")
    summary = {}
    for name, _ in EVALUATORS:
        passed = sum(r["scores"][name] for r in rows)
        summary[name] = round(passed / len(rows), 3)
        ctx.note(f"{name:18} {passed:>5}/{len(rows)} {summary[name]:>7.0%}")
    overall = sum(summary.values()) / len(summary)
    ctx.note(f"{'overall (mean)':18} {'':>8} {overall:>7.0%}")

    failing = [(r["id"], n) for r in rows for n, ok in r["scores"].items() if not ok]
    ctx.note("Failing checks: " + (", ".join(f"{i}:{n}" for i, n in failing) if failing else "none"))

    ctx.step("4. Save the run as a record")
    record = {"prompt": PROMPT_NAME, "model": ctx.model, "seconds": round(seconds, 2), "summary": summary, "rows": rows}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"run-{PROMPT_NAME}.json"
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        ctx.note(f"Saved {path.stat().st_size} bytes (to a temp folder that is deleted at the end of this script).")
    ctx.note("In a real project you would commit the record or upload it to an eval tool, so a later run has something to compare with.")

    ctx.step("What to notice")
    ctx.note("The report is a dict of numbers: that is what makes it comparable, thresholdable and chartable.")
    ctx.note("Batching all eight tickets in one call is cheaper but lets one malformed reply fail every row; script 2 isolates rows at eight times the calls.")


if __name__ == "__main__":
    main()
