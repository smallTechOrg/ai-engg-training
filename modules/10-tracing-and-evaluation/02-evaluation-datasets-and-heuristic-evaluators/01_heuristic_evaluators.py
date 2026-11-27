"""10.2/1  Heuristic evaluators: small pure functions that score one output

An evaluator takes an output (and sometimes the expected answer) and returns a score.
Heuristic evaluators are plain Python: no model, no cost, same answer every time. They check
what can be checked mechanically: is it valid JSON, is the category allowed, is it the right
category, is it short enough, does it mention what it must.

This script makes no model call. It runs the five evaluators on hand-written outputs, some
good and some deliberately bad, so you can see exactly what each one catches and misses.

Run it:   ./run 10.2/1          (Windows: run 10.2/1)
"""

import json

from labkit import lesson

CATEGORIES = ["network", "hardware", "software", "access", "other"]

CASE = {
    "ticket": "My laptop battery looks swollen and the trackpad is lifting off the case.",
    "expected_category": "hardware",
    "must_mention": ["battery", "stop"],
    "max_words": 30,
}


# Each evaluator returns {"name": ..., "passed": bool, "detail": str}. Keep them this boring.
def is_valid_json(raw):
    try:
        data = json.loads(raw)
    except ValueError as error:
        return {"name": "valid_json", "passed": False, "detail": f"not JSON: {error}"}, None
    if not isinstance(data, dict):
        return {"name": "valid_json", "passed": False, "detail": "JSON but not an object"}, None
    return {"name": "valid_json", "passed": True, "detail": "parsed"}, data


def category_allowed(data):
    value = data.get("category")
    return {"name": "category_allowed", "passed": value in CATEGORIES, "detail": f"category={value!r}"}


def exact_match(data, expected):
    # Exact match: normalise case and whitespace, then compare. No partial credit.
    got = str(data.get("category", "")).strip().lower()
    return {"name": "exact_match", "passed": got == expected, "detail": f"got {got!r}, expected {expected!r}"}


def max_length(data, limit):
    words = len(str(data.get("reply", "")).split())
    return {"name": "max_length", "passed": words <= limit, "detail": f"{words} words, limit {limit}"}


def keywords_present(data, keywords):
    text = str(data.get("reply", "")).lower()
    missing = [k for k in keywords if k.lower() not in text]
    return {"name": "keywords", "passed": not missing, "detail": "all present" if not missing else f"missing {missing}"}


def run_all(raw, case):
    results = []
    first, data = is_valid_json(raw)
    results.append(first)
    if data is not None:  # later evaluators need parsed data; skip them when the format is broken
        results += [
            category_allowed(data),
            exact_match(data, case["expected_category"]),
            max_length(data, case["max_words"]),
            keywords_present(data, case["must_mention"]),
        ]
    return results


OUTPUTS = {
    "good": json.dumps({"category": "hardware", "reply": "A swollen battery can be dangerous. Please stop using the laptop, unplug it and bring it to the IT desk today."}),
    "wrong category": json.dumps({"category": "software", "reply": "Please stop using the laptop and unplug the battery."}),
    "label not allowed": json.dumps({"category": "Hardware issue", "reply": "Stop using it; the battery needs replacing."}),
    "too long": json.dumps({"category": "hardware", "reply": "stop the battery " + "and please also consider the following " * 8}),
    "forgot the safety advice": json.dumps({"category": "hardware", "reply": "Thanks for reporting this. We will look at the trackpad soon."}),
    "not JSON": "Category: hardware. Please stop using it.",
}


@lesson("10.2/1", "Heuristic evaluators on hand-written outputs")
def main(ctx):
    ctx.step("1. The case: an input plus everything we know about a good answer")
    ctx.show_data("Case", CASE)

    ctx.step("2. Six candidate outputs, scored by five evaluators")
    ctx.note("An evaluator is a function: output in, pass/fail and a reason out. No model is called.")
    table = {}
    for label, raw in OUTPUTS.items():
        results = run_all(raw, CASE)
        table[label] = results
        marks = "  ".join(f"{r['name']}={'PASS' if r['passed'] else 'FAIL'}" for r in results)
        ctx.note(f"{label:26} {marks}")

    ctx.step("3. Why each one failed")
    for label, results in table.items():
        for r in results:
            if not r["passed"]:
                ctx.note(f"{label:26} {r['name']:17} {r['detail']}")

    ctx.step("What to notice")
    ctx.note("'wrong category' fails only exact_match, 'too long' only max_length: each check is narrow, so a failure names its cause.")
    ctx.note("'good' passes everything, but passing says only that the mechanical checks hold, not that the advice is kind or clear.")
    ctx.note("Judging tone and helpfulness needs a model as judge: that is 10.3.")


if __name__ == "__main__":
    main()
