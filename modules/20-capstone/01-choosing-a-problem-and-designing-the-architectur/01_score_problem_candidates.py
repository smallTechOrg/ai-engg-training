"""20.1/1  Choose the problem: score candidates against a rubric

A capstone fails more often from a bad problem than from bad code. This script scores
candidate projects (candidates.json) on six criteria and ranks them. The weights are an
opinion; the point is to make the opinion visible and to see what changes when you change it.

No model call: the work is the thinking. Edit candidates.json and put your own ideas in.

Run it:   ./run 20.1/1          (Windows: run 20.1/1)
"""

import json
import sys
from pathlib import Path

from labkit import lesson

FILE = Path(__file__).with_name("candidates.json")


def score(candidate, criteria):
    total = sum(criteria[name]["weight"] * value for name, value in candidate["scores"].items())
    best = sum(5 * item["weight"] for item in criteria.values())
    return round(100 * total / best)


def verdict(candidate, criteria):
    """Hard rules beat the weighted sum: a risky or untestable idea is not a first project."""
    reasons = []
    if candidate["scores"]["checkable"] <= 2:
        reasons.append("cannot be tested")
    if candidate["scores"]["low_blast_radius"] <= 2:
        reasons.append("harm if wrong is high")
    if candidate["scores"]["small_scope"] <= 2:
        reasons.append("too big for a first version")
    return reasons


@lesson("20.1/1", "Choose the problem: score candidates against a rubric")
def main(ctx):
    path = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else FILE
    ctx.step(f"Load the rubric and candidates from {path.name}")
    data = json.loads(path.read_text(encoding="utf-8"))
    criteria = data["criteria"]
    for name, item in criteria.items():
        ctx.note(f"{name} (weight {item['weight']}): {item['question']}")

    ctx.step("Score each candidate (0-100) and apply the hard rules")
    rows = []
    for candidate in data["candidates"]:
        reasons = verdict(candidate, criteria)
        rows.append((score(candidate, criteria), candidate["name"], reasons))
    rows.sort(reverse=True)
    for points, name, reasons in rows:
        flag = "REJECT: " + ", ".join(reasons) if reasons else "ok"
        ctx.note(f"{points:3d}  {name:34s} {flag}")

    ctx.step("What the ranking says")
    allowed = [row for row in rows if not row[2]]
    if allowed:
        ctx.note(f"Start with: {allowed[0][1]}")
    best_overall = rows[0]
    if best_overall[2]:
        ctx.note(f"Note: '{best_overall[1]}' scores high but fails a hard rule, so the rules overrode the sum.")
    ctx.note("Sensitivity: change a weight in candidates.json and rerun. If the winner changes, the choice was close.")

    ctx.step("Your turn")
    ctx.note("Add your own candidates, score them honestly, and keep only ideas you could test with 10 questions.")


if __name__ == "__main__":
    main()
