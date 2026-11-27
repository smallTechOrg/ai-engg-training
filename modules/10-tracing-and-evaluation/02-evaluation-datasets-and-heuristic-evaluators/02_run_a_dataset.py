"""10.2/2  Run a golden set through the assistant and score every row

A golden set (a "dataset" in LangSmith and most eval tools) is a list of inputs with what a
good answer looks like. The recipe is always the same: for each row, call the system, apply
the evaluators, keep one result record per row. This script does that for the helpdesk
classify-and-reply prompt, one model call per row (8 rows, 8 calls).

Run it:   ./run 10.2/2          (Windows: run 10.2/2)
"""

import json
from pathlib import Path

from labkit import lesson

GOLDEN = Path(__file__).with_name("golden.json")
CATEGORIES = ["network", "hardware", "software", "access", "other"]

SYSTEM_PROMPT = """You are the Larkspur Labs IT helpdesk assistant.
Read the ticket and reply with only a JSON object: {"category": "<one of network, hardware, software, access, other>", "reply": "<a reply to the employee in at most 40 words>"}.
network = Wi-Fi, VPN. hardware = physical devices. software = apps. access = accounts, passwords, permissions. other = not an IT problem."""


def evaluate(raw, case):
    """Five heuristic evaluators (same ideas as 10.2/1) returning {name: bool}."""
    try:
        data = json.loads(raw)
        assert isinstance(data, dict)
    except (ValueError, AssertionError):
        return {"valid_json": False}
    category = str(data.get("category", "")).strip().lower()
    reply = str(data.get("reply", ""))
    return {
        "valid_json": True,
        "category_allowed": category in CATEGORIES,
        "exact_match": category == case["expected_category"],
        "max_length": len(reply.split()) <= case["max_words"],
        "keywords": all(k.lower() in reply.lower() for k in case["must_mention"]),
    }


@lesson("10.2/2", "Run a golden set and score every row")
def main(ctx):
    ctx.step("1. Load the golden set")
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))
    ctx.note(f"{len(cases)} cases. Each has a ticket, the category a person decided is right, words the reply must contain, and a length limit.")
    ctx.show_data("First case", cases[0])

    ctx.step("2. For each case: call the model, keep the raw output, score it")
    records = []
    for case in cases:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": case["ticket"]}]
        response = ctx.client.chat.completions.create(
            model=ctx.model, messages=messages, response_format={"type": "json_object"}, temperature=0
        )
        raw = response.choices[0].message.content or ""
        ctx.record_usage(response.usage, quiet=True)
        records.append({"id": case["id"], "raw": raw, "scores": evaluate(raw, case)})

    ctx.step("3. One row per case, one column per evaluator")
    names = ["valid_json", "category_allowed", "exact_match", "max_length", "keywords"]
    ctx.note(f"{'case':6}" + "".join(f"{n:>18}" for n in names))
    for r in records:
        ctx.note(f"{r['id']:6}" + "".join(f"{('pass' if r['scores'].get(n) else 'FAIL'):>18}" for n in names))

    ctx.step("4. Pass rate per evaluator")
    for n in names:
        passed = sum(1 for r in records if r["scores"].get(n))
        ctx.note(f"{n:18} {passed}/{len(records)}  ({passed / len(records):.0%})")

    ctx.step("What to notice")
    ctx.note("Each column answers a different question; one overall percentage would hide which part broke.")
    ctx.note("A failing keyword check is not always a bad answer (a synonym?). Read the failing rows before trusting the number.")
    first_bad = next((r for r in records if not all(r["scores"].values())), None)
    if first_bad:
        ctx.show_data(f"A failing row: {first_bad['id']}", first_bad["raw"])


if __name__ == "__main__":
    main()
