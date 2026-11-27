"""01.7/2  Triage the whole batch in one call

All eight tickets from tickets.json go to the model in ONE request, and one JSON object
comes back with a list of results. The instructions and few-shot examples are sent once
instead of eight times, so the batch is cheaper and faster than one call per ticket.

The reply is validated twice: the shape of each result (pydantic), and the batch as a
whole (every ticket answered exactly once, no invented ids). Problems are reported and the
rest of the batch is still used.

Run it:   ./run 01.7/2          (Windows: run 01.7/2)
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from labkit import lesson

TICKETS_FILE = Path(__file__).with_name("tickets.json")


class TicketTriage(BaseModel):
    """One result in the batch: the triage fields plus the id of the ticket it belongs to."""

    model_config = ConfigDict(extra="forbid")

    id: str
    category: Literal["network", "hardware", "software", "access", "other"]
    urgency: int = Field(ge=1, le=4)
    summary: str = Field(min_length=1)
    needs_human: bool


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
    """All tickets in one user message, each inside its own delimiters."""
    return "\n\n".join(f"<ticket id=\"{t['id']}\" from=\"{t['from']}\">\n{t['text']}\n</ticket>" for t in tickets)


def problems(error):
    lines = []
    for problem in error.errors():
        where = ".".join(str(part) for part in problem["loc"]) or "(whole item)"
        lines.append(f"{where}: {problem['msg']}")
    return lines


def validate_batch(ctx, reply, expected_ids):
    """Validate item by item, so one bad entry does not throw away the other seven."""
    try:
        data = json.loads(reply)
    except ValueError as error:
        ctx.note(f"The reply is not JSON at all ({error}). Nothing to use; the whole batch goes to a person.")
        return {}
    items = data.get("results") if isinstance(data, dict) else None
    if not isinstance(items, list):
        ctx.note('The reply has no "results" list. Nothing to use; the whole batch goes to a person.')
        return {}
    results = {}
    for index, item in enumerate(items):
        try:
            result = TicketTriage.model_validate(item)
        except ValidationError as error:
            ctx.note(f"results[{index}] REJECTED: " + "; ".join(problems(error)))
            continue
        if result.id not in expected_ids:
            ctx.note(f"results[{index}] has id {result.id!r}, which is not one of the tickets we sent. Ignored.")
        elif result.id in results:
            ctx.note(f"results[{index}] answers {result.id} a second time. Keeping the first answer.")
        else:
            results[result.id] = result
    return results


@lesson("01.7/2", "Triage the whole batch in one call")
def main(ctx):
    ctx.step("Load the tickets and put them all in one message")
    tickets = json.loads(TICKETS_FILE.read_text(encoding="utf-8"))
    ctx.note(f"{len(tickets)} tickets from {TICKETS_FILE.name}. One request, not {len(tickets)}.")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": as_prompt(tickets)},
    ]
    ctx.show_messages(messages[1:], label="User message (the system prompt is the same as in 01.7/1, adapted for a list)")

    ctx.step("One call, JSON mode, temperature 0")
    response = ctx.client.chat.completions.create(
        model=ctx.model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0,
    )
    reply = ctx.show_response(response)

    ctx.step("Validate every result, then the batch as a whole")
    expected_ids = [t["id"] for t in tickets]
    results = validate_batch(ctx, reply, set(expected_ids))
    missing = [ticket_id for ticket_id in expected_ids if ticket_id not in results]
    ctx.note(f"Valid results: {len(results)} of {len(tickets)}.")
    if missing:
        ctx.note(f"No valid answer for: {', '.join(missing)}. Those tickets go to the human queue.")

    ctx.step("The triaged batch")
    header = f"{'id':<8} {'category':<9} {'urg':>3}  {'human':<5}  summary"
    ctx.console.print(header, markup=False)
    ctx.console.print("-" * 78, markup=False)
    for ticket_id in expected_ids:
        r = results.get(ticket_id)
        if r is None:
            ctx.console.print(f"{ticket_id:<8} {'-':<9} {'-':>3}  {'-':<5}  (no valid result: human queue)", markup=False)
        else:
            ctx.console.print(f"{r.id:<8} {r.category:<9} {r.urgency:>3}  {'yes' if r.needs_human else 'no':<5}  {r.summary}", markup=False)

    ctx.step("What the batch cost")
    usage = response.usage
    if usage is not None and usage.prompt_tokens is not None and usage.completion_tokens is not None:
        tokens_in, tokens_out, how = usage.prompt_tokens, usage.completion_tokens, "reported"
    else:
        tokens_in, tokens_out, how = len(SYSTEM_PROMPT + messages[1]["content"]) // 4, len(reply) // 4, "estimated, characters / 4"
        ctx.note("This endpoint reported no usage, so these are estimates.")
    ctx.note(f"Batch: {tokens_in} in + {tokens_out} out ({how}), about {(tokens_in + tokens_out) / len(tickets):.0f} tokens per ticket.")
    # How much of the prompt is the shared part (instructions + examples)? Measure its share by characters.
    shared = round(tokens_in * len(SYSTEM_PROMPT) / (len(SYSTEM_PROMPT) + len(messages[1]["content"])))
    ctx.note(f"About {shared} of those input tokens are the instructions and examples, sent once here.")
    ctx.note(f"One call per ticket would send them {len(tickets)} times: roughly {shared * (len(tickets) - 1)} extra input tokens,")
    ctx.note(f"and {len(tickets)} round trips instead of one. The trade-off: one bad reply can affect the whole batch.")


if __name__ == "__main__":
    main()
