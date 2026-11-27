"""01.7/1  Triage one ticket, end to end

Everything from module 01 in one place, applied to one ticket from tickets.json:

  - a system prompt in layers: role, rules, the JSON shape, few-shot examples (01.5);
  - JSON mode and a pydantic model that validates the reply (01.6);
  - temperature=0, so the same ticket gets the same answer as far as the provider allows (01.3);
  - token accounting for every call (01.4).

If the reply does not validate, the script sends the errors back to the model and asks
once more. At most two attempts; after that the ticket goes to a person.

Run it:   ./run 01.7/1          (Windows: run 01.7/1)
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from labkit import lesson

TICKETS_FILE = Path(__file__).with_name("tickets.json")
TICKET_ID = "LL-1003"  # try another id from tickets.json
MAX_ATTEMPTS = 2


class Triage(BaseModel):
    """What the rest of the helpdesk system needs from one ticket."""

    model_config = ConfigDict(extra="forbid")

    category: Literal["network", "hardware", "software", "access", "other"]
    urgency: int = Field(ge=1, le=4)
    summary: str = Field(min_length=1)
    needs_human: bool


SYSTEM_PROMPT = """You triage IT helpdesk tickets for Larkspur Labs.

Reply with only a JSON object in exactly this shape:
{"category": "software", "urgency": 2, "summary": "One short sentence describing the problem.", "needs_human": false}

Rules:
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

Examples:
Ticket: My mouse stopped working, even with new batteries.
{"category": "hardware", "urgency": 2, "summary": "Mouse not working after a battery change.", "needs_human": true}
Ticket: Teams says my password is wrong but I only changed it this morning.
{"category": "access", "urgency": 3, "summary": "Password rejected after a change; likely account sync or lockout.", "needs_human": true}
Ticket: Who do I ask about a parking permit?
{"category": "other", "urgency": 1, "summary": "Question about parking permits, not an IT issue.", "needs_human": false}"""


def load_ticket(ticket_id):
    tickets = json.loads(TICKETS_FILE.read_text(encoding="utf-8"))
    for ticket in tickets:
        if ticket["id"] == ticket_id:
            return ticket
    return tickets[0]


def problems(error):
    """One plain line per validation problem."""
    lines = []
    for problem in error.errors():
        where = ".".join(str(part) for part in problem["loc"]) or "(whole reply)"
        lines.append(f"{where}: {problem['msg']}")
    return lines


@lesson("01.7/1", "Triage one ticket, end to end")
def main(ctx):
    ctx.step("Load the ticket")
    ticket = load_ticket(TICKET_ID)
    ctx.note(f"From {TICKETS_FILE.name}: {ticket['id']}. Expected category (kept for lesson 01.7/3): {ticket['expected_category']}.")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        # Delimiters keep the employee's text clearly separate from our instructions (01.5).
        {"role": "user", "content": f"<ticket id=\"{ticket['id']}\" from=\"{ticket['from']}\">\n{ticket['text']}\n</ticket>"},
    ]
    ctx.show_messages(messages)

    triage = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        ctx.step(f"Attempt {attempt} of {MAX_ATTEMPTS}: ask in JSON mode, temperature 0")
        response = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,  # same input, same output, as far as the provider allows
        )
        reply = ctx.show_response(response)

        try:
            triage = Triage.model_validate_json(reply)
        except ValidationError as error:
            found = problems(error)
            ctx.note(f"REJECTED, {len(found)} problem(s):")
            for line in found:
                ctx.note(f"  - {line}")
            if attempt < MAX_ATTEMPTS:
                ctx.note("Feeding the errors back so the model can correct its own reply.")
                messages.append({"role": "assistant", "content": reply})
                messages.append({
                    "role": "user",
                    "content": "Your reply did not pass validation:\n" + "\n".join(f"- {line}" for line in found)
                    + "\nReply again with only the corrected JSON object.",
                })
                ctx.show_messages(messages[-1:], label="Correction sent back")
            continue
        ctx.note("Valid on attempt " + str(attempt) + ".")
        break

    ctx.step("Act on the result")
    if triage is None:
        ctx.note(f"No valid reply after {MAX_ATTEMPTS} attempts. The ticket goes to the human queue untouched.")
        ctx.note("That is a normal outcome, not a crash: the system still knows exactly what to do with the ticket.")
        return
    ctx.show_data("Validated triage", triage)
    queue = "human queue" if triage.needs_human else "self-service reply"
    priority = {1: "P4", 2: "P3", 3: "P2", 4: "P1"}[triage.urgency]
    ctx.note(f"Routing by ordinary code: {triage.category} / {priority} -> {queue}")
    verdict = "matches" if triage.category == ticket["expected_category"] else "does NOT match"
    ctx.note(f"The predicted category {verdict} the expected one ({ticket['expected_category']}).")


if __name__ == "__main__":
    main()
