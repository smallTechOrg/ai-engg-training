"""02.4/3  Allow-lists and budgets: limit what the loop may do

New since script 2: failures are not only bugs. A confused or manipulated model can ask for
things it should not. Three guards, all in your program:

  allow-list   only tools on the list for THIS session can run (a read-only session cannot reset passwords);
  budget       at most N tool calls in total, whatever the model wants;
  repeat check the same tool with the same arguments twice is a sign the model is stuck: stop.

Each guard returns a clear message to the model (it may adapt) and ends in a NAMED stop reason.

Run it:   ./run 02.4/3          (Windows: run 02.4/3)
"""

import json

from labkit import lesson

MAX_STEPS = 6
TOOL_BUDGET = 3
ALLOWED = {"lookup_ticket"}  # this session is read-only: reset_password is NOT on the list

TICKETS = {"LL-2095": {"from": "dmorgan", "subject": "Locked out after holiday", "status": "open"}}


def lookup_ticket(ticket_id: str) -> dict:
    ticket = TICKETS.get(ticket_id.strip().upper())
    return {"ticket_id": ticket_id, **ticket} if ticket else {"error": "not_found"}


def reset_password(username: str) -> dict:
    return {"username": username, "result": "reset link sent (simulated)"}


FUNCTIONS = {"lookup_ticket": lookup_ticket, "reset_password": reset_password}
TOOLS = [
    {"type": "function", "function": {"name": "lookup_ticket", "description": "Read a helpdesk ticket by id.",
        "parameters": {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]}}},
    {"type": "function", "function": {"name": "reset_password", "description": "Send a password reset link to a username.",
        "parameters": {"type": "object", "properties": {"username": {"type": "string"}}, "required": ["username"]}}},
]


@lesson("02.4/3", "Allow-lists and budgets: limit what the loop may do")
def main(ctx):
    ctx.step("The request tempts the model to use a tool this session may not")
    ctx.note(f"Both tools are DESCRIBED to the model. Only {sorted(ALLOWED)} may run. Budget: {TOOL_BUDGET} tool calls.")
    messages = [
        {"role": "system", "content": "You are the Larkspur Labs helpdesk agent. Read ticket LL-2095, and if the account is locked, reset the password. Then report in two sentences what you did."},
        {"role": "user", "content": "Please sort out ticket LL-2095."},
    ]
    ctx.show_messages(messages)
    ran, refused, seen, stop = [], [], set(), None
    for turn in range(1, MAX_STEPS + 1):
        ctx.step(f"Model call {turn} of at most {MAX_STEPS}")
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, tools=TOOLS)
        message = response.choices[0].message
        if not message.tool_calls:
            ctx.show_response(response)
            stop = "answered"
            break
        ctx.record_usage(response.usage, quiet=True)
        messages.append({"role": "assistant", "content": message.content, "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in message.tool_calls]})
        for call in message.tool_calls:
            name, raw = call.function.name, call.function.arguments
            key = (name, raw)
            if name not in ALLOWED:
                result = {"error": "not_permitted", "message": f"{name} is not available in this session. Tell the user a person must do it."}
                refused.append(name)
            elif len(ran) >= TOOL_BUDGET:
                result, stop = {"error": "budget_exhausted", "message": "No tool calls left."}, "tool_budget"
            elif key in seen:
                result, stop = {"error": "repeated_call", "message": "You already made this exact call. Use its result."}, "repeated_call"
            else:
                seen.add(key)
                try:
                    result = FUNCTIONS[name](**json.loads(raw or "{}"))
                    ran.append(name)
                except (ValueError, TypeError) as error:
                    result = {"error": "bad_arguments", "message": str(error)}
            ctx.show_tool_call(name, raw, json.dumps(result))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
        if stop in ("tool_budget", "repeated_call"):
            ctx.note(f"Stopping the loop: {stop}. The ticket goes to a person.")
            break
    else:
        stop = "step_cap"
        ctx.note(f"Stopped at the cap of {MAX_STEPS} model calls.")

    ctx.step("What the program records")
    ctx.show_data("Summary", {"stop_reason": stop, "tools_that_ran": ran, "tools_refused": refused})
    if "reset_password" in ran:
        ctx.note("UNEXPECTED: reset_password ran. The allow-list is broken.")
    else:
        ctx.note("reset_password never ran: whatever the model asked, the allow-list is enforced in code, not in the prompt.")
    ctx.note("A prompt that says 'do not reset passwords' is a request. The allow-list is a guarantee.")


if __name__ == "__main__":
    main()
