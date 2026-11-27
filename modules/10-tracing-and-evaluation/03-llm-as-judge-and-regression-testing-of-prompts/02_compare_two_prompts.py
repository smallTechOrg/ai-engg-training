"""10.3/2  Compare two prompt versions on the same dataset

The question you actually ask in practice is "is my new prompt better than the old one?".
Answer it by running both prompts over the SAME golden set and scoring both with the SAME
evaluators (heuristics from 10.2 plus an LLM judge), then putting the numbers side by side.

Four model calls: v1 replies, v2 replies, judge for v1, judge for v2 (each batched).

Run it:   ./run 10.3/2          (Windows: run 10.3/2)
"""

import json
from pathlib import Path

from labkit import lesson

GOLDEN = Path(__file__).with_name("golden.json")
CATEGORIES = ["network", "hardware", "software", "access", "other"]

FORMAT = """Reply with only a JSON object: {"results": [{"id": "G-00", "category": "<network|hardware|software|access|other>", "reply": "<reply to the employee>"}]}
One entry per ticket, same order, id copied exactly."""

PROMPTS = {
    "v1": "You are the Larkspur Labs IT helpdesk assistant. You receive several tickets at once.\n" + FORMAT,
    "v2": (
        "You are the Larkspur Labs IT helpdesk assistant. You receive several tickets at once.\n" + FORMAT + "\n"
        "Rules for every reply: at most 40 words; name the product or device the employee mentioned; give one concrete next step the employee can take now; "
        "if there is a safety risk, say so first; never claim you have already done something (you cannot reset, order or dispatch anything: say what the IT team will do instead)."
    ),
}

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


def evaluate_prompt(ctx, name, cases):
    """Generate replies with one prompt, then score them. Returns a dict of metric -> 0..1."""
    tickets = "\n\n".join(f'<ticket id="{c["id"]}">\n{c["ticket"]}\n</ticket>' for c in cases)
    outputs = parse_list(call_json(ctx, PROMPTS[name], tickets), "results")

    metrics = {"exact_match": 0, "max_length(40)": 0, "keywords": 0}
    for c in cases:
        out = outputs.get(c["id"], {})
        reply = lower(out.get("reply"))
        metrics["exact_match"] += lower(out.get("category")) == c["expected_category"]
        metrics["max_length(40)"] += bool(out) and len(reply.split()) <= 40
        metrics["keywords"] += bool(out) and all(k.lower() in reply for k in c["must_mention"])
    metrics = {k: v / len(cases) for k, v in metrics.items()}

    pairs = "\n\n".join(
        f'<ticket id="{c["id"]}">\n{c["ticket"]}\n</ticket>\n<reply id="{c["id"]}">\n{outputs.get(c["id"], {}).get("reply", "")}\n</reply>' for c in cases
    )
    judged = parse_list(call_json(ctx, JUDGE_PROMPT, pairs), "scores")
    for criterion in JUDGE_CRITERIA:
        values = [judged[c["id"]][criterion] for c in cases if isinstance(judged.get(c["id"], {}).get(criterion), (int, float))]
        metrics[f"judge:{criterion}"] = (sum(values) / len(values) / 5) if values else float("nan")  # scaled 0..1
    return metrics, outputs


@lesson("10.3/2", "Two prompt versions, same dataset, same evaluators")
def main(ctx):
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))

    ctx.step("1. The two prompts under test")
    ctx.note("v1 asks only for the JSON shape. v2 adds five rules: length, name the device, one next step, safety first, never claim an action.")

    ctx.step("2. Run and score both (4 model calls)")
    results, outputs = {}, {}
    for name in PROMPTS:
        results[name], outputs[name] = evaluate_prompt(ctx, name, cases)
        ctx.note(f"{name} done.")

    ctx.step("3. Side by side (all metrics scaled 0..1, higher is better)")
    ctx.note(f"{'metric':28}{'v1':>8}{'v2':>8}{'change':>9}")
    for metric in results["v1"]:
        a, b = results["v1"][metric], results["v2"][metric]
        change = f"{b - a:+.2f}" if a == a and b == b else "n/a"
        ctx.note(f"{metric:28}{a:>8.2f}{b:>8.2f}{change:>9}")

    ctx.step("4. Look at one pair of replies: numbers are a pointer, not the verdict")
    sample = cases[2]["id"]
    for name in PROMPTS:
        ctx.note(f"{name} {sample}: {outputs[name].get(sample, {}).get('reply', '(missing)')}")

    ctx.step("What to notice")
    ctx.note("Both prompts saw the same eight tickets and the same judge, so the difference comes from the prompt (plus some noise).")
    ctx.note("With eight rows, a change of one row is 0.125. Do not celebrate or panic about differences smaller than that; grow the golden set.")


if __name__ == "__main__":
    main()
