"""01.5/1  Zero-shot vs few-shot

Two ways to ask for the same job: classify four helpdesk tickets.

  zero-shot: an instruction and nothing else;
  few-shot:  the same instruction plus three worked examples.

The examples carry two things the instruction does not: the exact reply format, and a
house rule (anything about passwords or permissions is "access", even when an app is named).

Run it:   ./run 01.5/1          (Windows: run 01.5/1)
"""

import re

from labkit import lesson

CATEGORIES = ["network", "hardware", "software", "access"]

INSTRUCTION = """Classify each helpdesk ticket as one of: network, hardware, software, access.
Reply with one line per ticket."""

# All four tickets go to the model in ONE request, numbered. Never one call per ticket.
TICKETS = [
    "Outlook keeps asking for my password and then says it is wrong.",
    "The meeting-room screen on floor 3 shows 'no signal' when I plug in my laptop.",
    "At home the VPN drops every ten minutes, although my internet is fine.",
    "I need the Q3 budget folder but it says I do not have permission to open it.",
]

# The worked examples: one earlier exchange, written by us, that the model will imitate.
EXAMPLE_TICKETS = """1. Teams rejects my password after the weekend, though it works on my phone.
2. My docking station no longer charges the laptop.
3. Excel crashes whenever I open the pivot report."""
EXAMPLE_LABELS = """1: access
2: hardware
3: software"""


def numbered(tickets):
    return "\n".join(f"{number}. {text}" for number, text in enumerate(tickets, 1))


def parse_labels(reply):
    """Read 'N: label' lines tolerantly. Returns {ticket number: label or '?'}."""
    labels = {}
    for line in reply.splitlines():
        match = re.match(r"^\W*(\d+)\W+(.*)$", line)
        if not match:
            continue
        rest = match.group(2).lower()
        found = [(rest.find(name), name) for name in CATEGORIES if name in rest]
        labels[int(match.group(1))] = min(found)[1] if found else "?"
    return labels


def tidy_lines(reply):
    """How many lines are exactly 'N: label' with nothing else? A measure of format discipline."""
    pattern = r"^\d+: (%s)$" % "|".join(CATEGORIES)
    return sum(1 for line in reply.splitlines() if re.match(pattern, line.strip()))


@lesson("01.5/1", "Zero-shot vs few-shot")
def main(ctx):
    batch = numbered(TICKETS)

    ctx.step("Zero-shot: an instruction only")
    zero_shot = [
        {"role": "system", "content": INSTRUCTION},
        {"role": "user", "content": batch},
    ]
    ctx.show_messages(zero_shot)
    response = ctx.client.chat.completions.create(model=ctx.model, messages=zero_shot)
    zero_reply = ctx.show_response(response)

    ctx.step("Few-shot: the same instruction plus three worked examples")
    ctx.note("The examples are an earlier user/assistant exchange that we wrote ourselves.")
    few_shot = [
        {"role": "system", "content": INSTRUCTION},
        {"role": "user", "content": EXAMPLE_TICKETS},
        {"role": "assistant", "content": EXAMPLE_LABELS},
        {"role": "user", "content": batch},
    ]
    ctx.show_messages(few_shot)
    response = ctx.client.chat.completions.create(model=ctx.model, messages=few_shot)
    few_reply = ctx.show_response(response)

    ctx.step("Compare the two")
    zero, few = parse_labels(zero_reply), parse_labels(few_reply)
    lines = [f"{'#':>2}  {'zero-shot':<10} {'few-shot':<10} ticket"]
    for number, text in enumerate(TICKETS, 1):
        lines.append(f"{number:>2}  {zero.get(number, '(none)'):<10} {few.get(number, '(none)'):<10} {text[:52]}")
    ctx.console.print("\n".join(lines), markup=False)
    ctx.note(f"Lines in exactly the form 'N: label': zero-shot {tidy_lines(zero_reply)}/{len(TICKETS)}, few-shot {tidy_lines(few_reply)}/{len(TICKETS)}.")
    if not zero and not few:
        ctx.note("Neither reply contained numbered labels, so there is nothing to compare. That is a result too: the parser must expect it.")
        return
    ctx.note("Look at tickets 1 and 4. The examples taught the house rule (passwords and permissions are 'access') without a rule ever being written down.")


if __name__ == "__main__":
    main()
