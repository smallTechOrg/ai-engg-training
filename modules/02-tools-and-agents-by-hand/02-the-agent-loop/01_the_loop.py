"""02.2/1  The agent loop in about twenty lines

An agent is not a new kind of model. It is the round trip from 02.1 inside a `while` loop:

  reason   the model reads the transcript and decides: answer, or ask for a tool
  act      your program runs the tool the model asked for
  observe  the result is appended to the transcript, and the loop goes round again

The loop ends when the model answers in text (no tool calls) or when the iteration cap is hit.
The cap is not optional: a model that keeps asking for tools would otherwise loop forever.

Run it:   ./run 02.2/1          (Windows: run 02.2/1)
"""

import json

from labkit import lesson

MAX_STEPS = 6

TICKETS = {
    "LL-2060": {"from": "kbrown", "subject": "Printer on floor 2 prints blank pages", "status": "open"},
    "LL-2061": {"from": "ofarrell", "subject": "Cannot join the VPN from home", "status": "in progress"},
}
KB = {
    "printer": "Blank pages: replace the toner cartridge, then print a test page from the device menu.",
    "vpn": "VPN fails to connect: check the date and time on the laptop, then reinstall the VPN profile from the self-service portal.",
}


def lookup_ticket(ticket_id: str) -> dict:
    ticket = TICKETS.get(ticket_id.strip().upper())
    return {"ticket_id": ticket_id, **ticket} if ticket else {"error": f"No ticket {ticket_id!r}."}


def search_kb(query: str) -> dict:
    hits = [text for key, text in KB.items() if key in query.lower()]
    return {"articles": hits} if hits else {"articles": [], "note": "No article matched."}


FUNCTIONS = {"lookup_ticket": lookup_ticket, "search_kb": search_kb}
TOOLS = [
    {"type": "function", "function": {
        "name": "lookup_ticket", "description": "Read a helpdesk ticket by id (subject, who raised it, status).",
        "parameters": {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]}}},
    {"type": "function", "function": {
        "name": "search_kb", "description": "Search the knowledge base for a fix. The query is a short phrase such as 'vpn'.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
]


@lesson("02.2/1", "The agent loop in about twenty lines")
def main(ctx):
    ctx.step("The task and the loop's rules")
    ctx.note(f"Tools: lookup_ticket, search_kb. Hard cap: {MAX_STEPS} model calls. The model must read the ticket BEFORE it can search well.")
    messages = [
        {"role": "system", "content": "You are the Larkspur Labs helpdesk agent. Read the ticket first, then search the knowledge base for a fix, then reply with the ticket subject and the fix in two sentences."},
        {"role": "user", "content": "What should I tell the person who raised ticket LL-2061?"},
    ]
    ctx.show_messages(messages)

    for step in range(1, MAX_STEPS + 1):
        ctx.step(f"Loop turn {step}: reason")
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, tools=TOOLS)
        message = response.choices[0].message
        if not message.tool_calls:
            ctx.show_response(response)  # the final reply: records usage and prints it
            ctx.note(f"Stop reason: the model answered in text after {step} model call(s).")
            break
        ctx.record_usage(response.usage, quiet=True)
        ctx.note("Decision: act. The model asked for " + ", ".join(c.function.name for c in message.tool_calls) + ".")
        messages.append({
            "role": "assistant", "content": message.content,
            "tool_calls": [{"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in message.tool_calls],
        })
        ctx.step(f"Loop turn {step}: act and observe")
        for call in message.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
                result = FUNCTIONS[call.function.name](**args)
            except (ValueError, TypeError, KeyError) as error:
                args, result = call.function.arguments, {"error": f"Could not run the tool: {error!r}"}
            ctx.show_tool_call(call.function.name, args, json.dumps(result))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
    else:
        ctx.note(f"Stop reason: hit the cap of {MAX_STEPS} model calls with no final answer. A real agent hands over to a person here.")

    ctx.step("The transcript is the agent's whole state")
    ctx.note(f"The loop kept no other memory: {len(messages)} messages. Each turn re-sends all of them, so the cost grows every turn.")
    ctx.show_messages(messages, label="Final transcript")


if __name__ == "__main__":
    main()
