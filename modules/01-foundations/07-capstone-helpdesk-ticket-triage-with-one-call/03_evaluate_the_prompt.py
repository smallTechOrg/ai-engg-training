"""01.7/3  Evaluate the prompt: prompts are tested like code

A prompt is code that happens to be written in English. It has inputs, expected outputs
and regressions, so it gets tests. tickets.json is the test set: every ticket carries the
category a person decided was right (expected_category).

This script runs the batch triage from 01.7/2 (one call), compares each predicted category
with the expected one, and prints the accuracy and every miss. Change the prompt, run this
again, and you know whether you made it better or worse.

Run it:   ./run 01.7/3          (Windows: run 01.7/3)
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from labkit import lesson

TICKETS_FILE = Path(__file__).with_name("tickets.json")
ACCEPTANCE_ACCURACY = 0.875  # the bar from the capstone brief: at least 7 of 8 correct


class TicketTriage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category: Literal["network", "hardware", "software", "access", "other"]
    urgency: int = Field(ge=1, le=4)
    summary: str = Field(min_length=1)
    needs_human: bool


# The prompt under test. It is the same text as in 01.7/2; edit it here and re-run to compare.
SYSTEM_PROMPT = """You triage IT helpdesk tickets for Larkspur Labs. You will receive several tickets at once.

Reply with only a JSON object in exactly this shape, with one entry in "results" per ticket, in the same order:
{"results": [{"id": "LL-0000", "category": "software", "urgency": 2, "summary": "One short sentence describing the problem.", "needs_human": false}]}

Rules:
- id is copied exactly from the ticket.
- category is one of: network, hardware, software, access, other.
  network = Wi-Fi, VPN, connectivity. hardware = physical devices: laptops, screens, printers, peripherals.
  software = applications crashing, installs, updates. access = accounts, passwords, MFA, permissions.
  other = anything that is not an IT problem.
- A password or locked-account problem is access, even when the employee names the app it appeared in.
- urgency is an integer: 1 = can wait days, 2 = normal, 3 = blocks someone's work today,
  4 = many people affected or a security risk.
- summary is one sentence of at most 20 words.
- needs_human is true when a person must act: a visit, a repair, a replacement, an approval
  or an account unlock. It is false when the employee can fix it with instructions.

Examples of single results:
Ticket: My mouse stopped working, even with new batteries.
{"id": "EX-1", "category": "hardware", "urgency": 2, "summary": "Mouse not working after a battery change.", "needs_human": true}
Ticket: Teams says my password is wrong but I only changed it this morning.
{"id": "EX-2", "category": "access", "urgency": 3, "summary": "Password rejected after a change; likely account sync or lockout.", "needs_human": true}
Ticket: Who do I ask about a parking permit?
{"id": "EX-3", "category": "other", "urgency": 1, "summary": "Question about parking permits, not an IT issue.", "needs_human": false}"""


def as_prompt(tickets):
    # Only id, sender and text go to the model. expected_category stays in our code: the answer key.
    return "\n\n".join(f"<ticket id=\"{t['id']}\" from=\"{t['from']}\">\n{t['text']}\n</ticket>" for t in tickets)


def parse_results(reply):
    """Return ({id: TicketTriage}, [problems]). Never raises: bad output is a test result, not a crash."""
    try:
        data = json.loads(reply)
    except ValueError as error:
        return {}, [f"reply is not JSON ({error})"]
    items = data.get("results") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return {}, ['reply has no "results" list']
    results, issues = {}, []
    for index, item in enumerate(items):
        try:
            result = TicketTriage.model_validate(item)
        except ValidationError as error:
            issues.append(f"results[{index}] failed validation ({error.error_count()} problem(s))")
            continue
        results.setdefault(result.id, result)
    return results, issues


@lesson("01.7/3", "Evaluate the prompt")
def main(ctx):
    ctx.step("Load the test set")
    tickets = json.loads(TICKETS_FILE.read_text(encoding="utf-8"))
    ctx.note(f"{len(tickets)} tickets, each with an expected_category decided by a person. The model never sees it.")
    for t in tickets:
        ctx.console.print(f"  {t['id']}  expected: {t['expected_category']}", markup=False)

    ctx.step("Run the prompt under test (one call, temperature 0)")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": as_prompt(tickets)},
    ]
    ctx.note("Same request as 01.7/2. temperature=0 keeps re-runs comparable.")
    response = ctx.client.chat.completions.create(
        model=ctx.model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0,
    )
    ctx.record_usage(response.usage)
    reply = response.choices[0].message.content or ""
    results, issues = parse_results(reply)
    known = {t["id"] for t in tickets}
    for unknown in sorted(set(results) - known):
        issues.append(f"result for {unknown!r}, which is not a ticket in the test set (ignored)")
        del results[unknown]
    ctx.note(f"Parsed {len(results)} valid result(s) for tickets in the test set.")
    for issue in issues:
        ctx.note(f"  - {issue}")

    ctx.step("Compare predicted with expected")
    header = f"{'id':<8} {'expected':<9} {'predicted':<10} result"
    ctx.console.print(header, markup=False)
    ctx.console.print("-" * 40, markup=False)
    misses = []
    for t in tickets:
        result = results.get(t["id"])
        predicted = result.category if result else "(none)"
        ok = predicted == t["expected_category"]
        if not ok:
            misses.append((t, predicted))
        ctx.console.print(f"{t['id']:<8} {t['expected_category']:<9} {predicted:<10} {'ok' if ok else 'MISS'}", markup=False)

    ctx.step("Score")
    correct = len(tickets) - len(misses)
    accuracy = correct / len(tickets) if tickets else 0.0
    ctx.note(f"Accuracy: {correct} / {len(tickets)} = {accuracy:.0%}")
    if misses:
        ctx.note("Every miss, with the ticket text, so you can decide whether the prompt or the label is wrong:")
        for t, predicted in misses:
            why = "no valid result for this ticket" if predicted == "(none)" else f"predicted {predicted}, expected {t['expected_category']}"
            ctx.note(f"  {t['id']} ({why})")
            ctx.note(f"    \"{t['text']}\"")
    else:
        ctx.note("No misses on this run.")
    verdict = "PASS" if accuracy >= ACCEPTANCE_ACCURACY else "FAIL"
    ctx.note(f"Acceptance bar: {ACCEPTANCE_ACCURACY:.1%} -> {verdict}.")
    ctx.note("In a real project this check runs in CI, and a prompt change that drops below the bar is not merged.")

    ctx.step("Prompts are tested like code")
    ctx.note("1. A fixed test set with expected answers (tickets.json).")
    ctx.note("2. A repeatable run (temperature 0, one batch call).")
    ctx.note("3. A score and a list of failures to read, not just a number.")
    ctx.note("4. Re-run after every prompt or model change. Eight tickets is a smoke test; real suites have hundreds.")


if __name__ == "__main__":
    main()
