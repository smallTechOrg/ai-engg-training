"""02.2/3  The helpdesk agent works a small queue

New since script 2: the agent has to PLAN across several tools. The task is open-ended ("what
is open for dmorgan and how do I fix it?"), so the number of loop turns is not known in advance:
it depends on what each observation reveals. The script prints the cost of every turn, to show
why a loop that re-sends its whole transcript gets expensive.

Run it:   ./run 02.2/3          (Windows: run 02.2/3)
"""

import json

from labkit import lesson

MAX_STEPS = 8

TICKETS = {
    "LL-2070": {"from": "dmorgan", "subject": "VPN drops every ten minutes", "status": "open"},
    "LL-2071": {"from": "dmorgan", "subject": "Laptop fan is loud", "status": "closed"},
    "LL-2072": {"from": "pnair", "subject": "Cannot print to floor 3", "status": "open"},
}
KB = {
    "vpn": "VPN drops: switch the VPN protocol to TCP in the client settings and update to the latest client.",
    "fan": "Loud fan: clean the vents; if it persists, book a hardware check.",
    "print": "Printing: restart the print spooler from the self-service portal.",
}


def list_tickets(username: str) -> dict:
    found = [{"ticket_id": k, "subject": v["subject"], "status": v["status"]} for k, v in TICKETS.items() if v["from"] == username.strip().lower()]
    return {"tickets": found}


def search_kb(query: str) -> dict:
    hits = [text for key, text in KB.items() if key in query.lower()]
    return {"articles": hits or ["No article matched."]}


FUNCTIONS = {"list_tickets": list_tickets, "search_kb": search_kb}
TOOLS = [
    {"type": "function", "function": {
        "name": "list_tickets", "description": "List every ticket raised by a username, with status.",
        "parameters": {"type": "object", "properties": {"username": {"type": "string"}}, "required": ["username"]}}},
    {"type": "function", "function": {
        "name": "search_kb", "description": "Search the knowledge base with a short keyword such as 'vpn' or 'print'.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
]


@lesson("02.2/3", "The helpdesk agent works a small queue")
def main(ctx):
    ctx.step("An open-ended task")
    messages = [
        {"role": "system", "content": "You are the Larkspur Labs helpdesk agent. Only open tickets need a fix. Use list_tickets, then search_kb once per open ticket. Reply with one line per open ticket: subject and suggested fix."},
        {"role": "user", "content": "What is still open for dmorgan, and how do we fix it?"},
    ]
    ctx.show_messages(messages)
    per_turn = []  # prompt tokens per model call
    for turn in range(1, MAX_STEPS + 1):
        ctx.step(f"Turn {turn} of at most {MAX_STEPS}")
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, tools=TOOLS)
        message = response.choices[0].message
        per_turn.append(getattr(response.usage, "prompt_tokens", None))
        if not message.tool_calls:
            ctx.show_response(response)
            break
        ctx.record_usage(response.usage, quiet=True)
        messages.append({
            "role": "assistant", "content": message.content,
            "tool_calls": [{"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in message.tool_calls],
        })
        for call in message.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
                result = FUNCTIONS[call.function.name](**args)
            except (ValueError, TypeError, KeyError) as error:
                args, result = call.function.arguments, {"error": f"Could not run the tool: {error!r}"}
            ctx.show_tool_call(call.function.name, args, json.dumps(result))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
    else:
        ctx.note(f"Stopped at the cap of {MAX_STEPS} turns with no final answer.")

    ctx.step("What each turn cost")
    if all(p is not None for p in per_turn):
        ctx.show_data("Prompt tokens sent on each model call", per_turn)
        ctx.note("The numbers climb because every turn re-sends the whole transcript. 02.3 is about keeping that under control.")
    else:
        ctx.note("This endpoint did not report token usage, so there is no per-turn cost to show.")
    ctx.note(f"The agent decided its own path: {len(per_turn)} model call(s). You set the ceiling, the model chose the route.")


if __name__ == "__main__":
    main()
