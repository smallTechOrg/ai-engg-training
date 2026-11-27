"""02.1/3  The helpdesk assistant with two tools

The assistant gets two tools over an invented ticket table and user directory:

  lookup_ticket(ticket_id)   reads the ticket table
  reset_password(username)   PRETENDS to reset a password (it changes nothing, it only reports)

Because the model may need one tool, then another, then the answer, the round trip from
script 2 now sits in a loop: call the model, run what it asks for, repeat until it answers
in text. The loop has a hard cap of 4 model calls, printed when hit.

Run it:   ./run 02.1/3          (Windows: run 02.1/3)
"""

import json

from labkit import lesson

MAX_ITERATIONS = 4

TICKETS = {
    "LL-2051": {"from": "dmorgan", "subject": "Locked out after holiday", "status": "open", "notes": "Account locked after 5 failed sign-ins."},
    "LL-2052": {"from": "pnair", "subject": "Second monitor flickers", "status": "in progress", "notes": "New cable sent by internal mail."},
}
USERS = {"dmorgan": "Dana Morgan (Sales)", "pnair": "Priya Nair (Finance)"}


def lookup_ticket(ticket_id: str) -> dict:
    ticket = TICKETS.get(ticket_id.strip().upper())
    if ticket is None:
        return {"error": f"No ticket with id {ticket_id!r}."}
    return {"ticket_id": ticket_id.strip().upper(), **ticket}


def reset_password(username: str) -> dict:
    # A real version would call the identity provider. This one only pretends, on purpose.
    name = username.strip().lower()
    if name not in USERS:
        return {"error": f"No user called {username!r}."}
    return {"username": name, "result": "reset link sent to the registered phone (simulated, nothing changed)"}


FUNCTIONS = {"lookup_ticket": lookup_ticket, "reset_password": reset_password}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_ticket",
            "description": "Look up a helpdesk ticket by id. Returns who raised it (their username), the subject, status and notes.",
            "parameters": {
                "type": "object",
                "properties": {"ticket_id": {"type": "string", "description": "Ticket id such as LL-2051."}},
                "required": ["ticket_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reset_password",
            "description": "Send a password reset link to an employee. Use only when a ticket shows a locked account or forgotten password.",
            "parameters": {
                "type": "object",
                "properties": {"username": {"type": "string", "description": "The employee's username, such as dmorgan."}},
                "required": ["username"],
                "additionalProperties": False,
            },
        },
    },
]

SYSTEM_PROMPT = """You are the Larkspur Labs IT helpdesk assistant, working a ticket queue.
Use lookup_ticket to read a ticket before acting on it. If it is a locked account or forgotten
password, use reset_password for the username on the ticket. Finish with two sentences for the
on-call engineer: what you found and what you did."""


def run_tool(call):
    """Turn one tool request into a result string. Never raises: problems go back to the model."""
    function = FUNCTIONS.get(call.function.name)
    if function is None:
        return call.function.arguments, {"error": f"Unknown tool {call.function.name!r}."}
    try:
        arguments = json.loads(call.function.arguments or "{}")
        return arguments, function(**arguments)
    except (ValueError, TypeError) as error:
        return call.function.arguments, {"error": f"Bad arguments: {error}"}


@lesson("02.1/3", "The helpdesk assistant with two tools")
def main(ctx):
    ctx.step("The tools and the request")
    ctx.note("Tools offered: " + ", ".join(t["function"]["name"] for t in TOOLS) + f". Loop cap: {MAX_ITERATIONS} model calls.")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Please handle ticket LL-2051."},
    ]
    ctx.show_messages(messages)

    answer = None
    executed = []  # (tool name, arguments) for every function that really ran
    for iteration in range(1, MAX_ITERATIONS + 1):
        ctx.step(f"Model call {iteration} of at most {MAX_ITERATIONS}")
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, tools=TOOLS)
        ctx.show_response(response)
        message = response.choices[0].message
        if not message.tool_calls:
            answer = message.content or ""
            break
        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                    for c in message.tool_calls
                ],
            }
        )
        ctx.note("Your program, not the model, runs each requested function:")
        for call in message.tool_calls:
            arguments, result = run_tool(call)
            executed.append((call.function.name, arguments))
            ctx.show_tool_call(call.function.name, arguments, json.dumps(result))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
    else:
        ctx.note(f"Stopped: hit the cap of {MAX_ITERATIONS} model calls without a final answer. The ticket goes to a person.")

    ctx.step("Result")
    if answer is not None:
        ctx.note(f"Final answer after {iteration} model call(s):")
        ctx.console.print(answer, markup=False)

    ctx.step("Check the answer against what really ran")
    ctx.note("Only your program's record says what happened. The model's text is a claim.")
    ctx.show_data("Functions your program actually ran", [f"{name}({json.dumps(args)})" for name, args in executed] or ["(none)"])
    claimed_reset = answer is not None and "reset" in answer.lower()
    really_reset = any(name == "reset_password" for name, _ in executed)
    if claimed_reset and not really_reset:
        ctx.note("WARNING: the answer talks about a password reset, but reset_password never ran.")
        ctx.note("The model wrote about the action in text instead of requesting it as a tool call. Nothing was reset.")
        ctx.note("Never report an action to a user on the model's word: report what your program executed.")
    elif really_reset:
        ctx.note("reset_password really ran (in simulation), so the answer matches the record.")
    ctx.note("Every action happened in Python, where you can log it, check permissions or ask a human first.")
    ctx.note("This loop is the core of every agent; 02.2 looks at it properly.")


if __name__ == "__main__":
    main()
