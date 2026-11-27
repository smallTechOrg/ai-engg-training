"""10.4/1  Build the suite: dataset + evaluators + judge, one report

The capstone assembles the module. A suite is: a golden set (10.2), heuristic evaluators
(10.2), an LLM judge (10.3), and a function that turns one prompt into one dictionary of
metrics (0..1, higher is better). Everything later (baselines, thresholds, CI) works on that
dictionary.

This script defines the suite and scores the current helpdesk prompt: 2 model calls (replies,
then one batched judge call). It ends by printing the metrics as JSON, the format of baseline.json.

Run it:   ./run 10.4/1          (Windows: run 10.4/1)
"""

import json
from pathlib import Path

from labkit import lesson

GOLDEN = Path(__file__).with_name("golden.json")
CATEGORIES = ["network", "hardware", "software", "access", "other"]

FORMAT = """Reply with only a JSON object: {"results": [{"id": "G-00", "category": "<network|hardware|software|access|other>", "reply": "<reply to the employee>"}]}
One entry per ticket, same order, id copied exactly."""

CURRENT_PROMPT = (
    "You are the Larkspur Labs IT helpdesk assistant. You receive several tickets at once.\n" + FORMAT + "\n"
    "Rules for every reply: at most 40 words; name the product or device the employee mentioned; give one concrete next step the employee can take now; "
    "if there is a safety risk, say so first; never claim you have already done something (you cannot reset, order or dispatch anything: say what the IT team will do instead)."
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


@lesson("10.4/1", "Build the suite and score the current prompt")
def main(ctx):
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))

    ctx.step("1. The suite's parts")
    ctx.note(f"dataset: {len(cases)} golden tickets   heuristics: exact_match, max_length, keywords   judge criteria: {', '.join(JUDGE_CRITERIA)}")

    ctx.step("2. Score the current helpdesk prompt (2 model calls)")
    metrics, outputs = run_suite(ctx, CURRENT_PROMPT, cases)

    ctx.step("3. The report")
    for name, value in metrics.items():
        bar = "#" * round(value * 20)
        ctx.note(f"{name:28}{value:>6.2f}  {bar}")

    ctx.step("4. One output, to remind you the numbers are about words")
    first = cases[1]["id"]
    ctx.note(f"{first}: {outputs.get(first, {}).get('reply', '(missing)')}")

    ctx.step("5. As JSON: this is the shape of baseline.json")
    ctx.show_data("metrics", metrics)

    ctx.step("What to notice")
    ctx.note("One function, prompt in and dict out, is the whole interface. Baselines, thresholds and the CI gate only need that dict.")
    ctx.note("Missing judge scores count as 0: a broken judge must make the suite fail, not pass.")


if __name__ == "__main__":
    main()
