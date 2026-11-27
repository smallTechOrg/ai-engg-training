"""01.2/3  A helpdesk conversation that remembers

The running scenario: the helpdesk assistant handles a ticket over three turns. In turn 3
it must use a detail (the asset tag) that the employee mentioned only in turn 1. It can,
because the script resends the whole conversation each time.

Run it:   ./run 01.2/3          (Windows: run 01.2/3)
"""

from labkit import lesson

SYSTEM_PROMPT = """You are the first-line IT helpdesk assistant at Larkspur Labs.
Reply in at most three short sentences. Be friendly and plain; no jargon."""

ASSET_TAG = "LL-2291"

EMPLOYEE_TURNS = [
    f"Hi, this is Omar from Sales. My laptop (asset tag {ASSET_TAG}) shuts down by itself when I unplug the charger.",
    "The battery icon says 'plugged in, not charging' and it has been stuck at 3% for two days.",
    "OK, I can't fix that myself. Please write the two-line handover note for the on-site technician.",
]


@lesson("01.2/3", "A helpdesk conversation that remembers")
def main(ctx):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    reply = ""

    for number, text in enumerate(EMPLOYEE_TURNS, 1):
        ctx.step(f"Turn {number} of {len(EMPLOYEE_TURNS)}")
        messages.append({"role": "user", "content": text})
        ctx.show_messages(messages, label=f"Messages sent to the model ({len(messages)} messages)")
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
        reply = ctx.show_response(response)
        messages.append({"role": "assistant", "content": reply})

    ctx.step("Did the handover note use the detail from turn 1?")
    used = ASSET_TAG in reply
    ctx.note(f"Asset tag {ASSET_TAG} was mentioned only in turn 1. Present in the turn-3 reply: {'yes' if used else 'no'}")
    if used:
        ctx.note("The model 'remembered' because turn 1 was resent as part of the turn-3 request.")
    else:
        ctx.note("The model had turn 1 in front of it but did not use the tag. Having the context is necessary, not sufficient.")
    ctx.note("Remove the line that appends the assistant reply, or send only the last message, and this breaks.")


if __name__ == "__main__":
    main()
