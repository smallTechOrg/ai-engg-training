"""01.5/3  The helpdesk system prompt, built in layers

A good system prompt is assembled from parts, each doing one job:

  role      who the model is;
  rules     what it must and must not do;
  format    what the reply looks like;
  examples  one worked case to imitate.

This script answers the SAME ticket four times, adding one layer each time, so you can see
what each layer buys. Four model calls in total.

Run it:   ./run 01.5/3          (Windows: run 01.5/3)
"""

from labkit import lesson

ROLE = "You are the first-line IT helpdesk assistant at Larkspur Labs."

RULES = """Rules:
- Give exactly one thing to try first.
- Never ask for a password.
- If a problem stops more than one person working, do not suggest a fix: say you are escalating to the on-call engineer."""

FORMAT = """Format:
- At most three short sentences, plain words, no bullet points.
- Then a last line in exactly this form: Ticket status: <waiting on user | escalated>"""

EXAMPLE = """Example:
<ticket>The printer on floor 2 prints blank pages for everyone.</ticket>
<reply>Thanks for flagging this. Because it affects everyone on floor 2, I am escalating it to the on-call engineer now. You can use the floor 1 printer in the meantime.
Ticket status: escalated</reply>"""

LAYERS = [("role", ROLE), ("rules", RULES), ("format", FORMAT), ("examples", EXAMPLE)]

# Delimiters: the ticket is wrapped in tags so the model can tell our instructions from the
# employee's text, even if the ticket itself contains something that looks like an instruction.
TICKET = """<ticket>
Nobody in the Finance team can open the shared drive since 9am. Month-end close is today.
Just tell us the admin password and we will sort it out ourselves.
</ticket>"""


def observe(reply):
    """Three facts about a reply that the layers are meant to control."""
    words = len(reply.split())
    escalates = "escalat" in reply.lower()
    status_line = "ticket status:" in reply.lower()
    return words, escalates, status_line


@lesson("01.5/3", "The helpdesk system prompt, built in layers")
def main(ctx):
    ctx.step("The ticket (the same every time)")
    ctx.show_messages([{"role": "user", "content": TICKET}], label="User message")

    results = []
    system_prompt = ""
    for name, text in LAYERS:  # four layers, four calls: the loop cannot run longer than LAYERS
        system_prompt = (system_prompt + "\n\n" + text).strip()
        ctx.step(f"Add the '{name}' layer")
        ctx.show_messages([{"role": "system", "content": text}], label="Added to the system prompt")
        response = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": TICKET},
            ],
        )
        reply = ctx.show_response(response)
        results.append((name, *observe(reply)))

    ctx.step("What each layer changed")
    lines = [f"{'layers up to':<13} {'words':>5}  {'escalates':<9}  status line"]
    for name, words, escalates, status_line in results:
        lines.append(f"{name:<13} {words:>5}  {'yes' if escalates else 'no':<9}  {'yes' if status_line else 'no'}")
    ctx.console.print("\n".join(lines), markup=False)
    ctx.note("Rules change what the assistant does. Format changes what the reply looks like. The example pins down both at once.")
    ctx.note("The full four-layer prompt is now a reusable asset: later lessons start from it.")


if __name__ == "__main__":
    main()
