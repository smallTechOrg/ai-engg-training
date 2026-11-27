"""02.4/1  Tool errors are data: classify them and send them back to the model

A tool call can go wrong in five different ways, and none of them should crash the agent:

  unknown_tool     the model named a function that does not exist
  bad_json         `arguments` is not valid JSON
  bad_arguments    valid JSON, but wrong or missing fields (checked with pydantic)
  tool_failed      the function itself raised an exception
  not_found        the function ran fine and reports "no such ticket" (a normal result)

`execute()` turns every one into a small JSON object with an `error` kind and a message the
model can act on. Part 1 feeds it hand-made bad calls (no model needed); part 2 lets the real
model meet a "not found" and shows how it explains it.

Run it:   ./run 02.4/1          (Windows: run 02.4/1)
"""

import json
from types import SimpleNamespace

from pydantic import BaseModel, ConfigDict, ValidationError

from labkit import lesson

MAX_STEPS = 4
TICKETS = {"LL-2080": {"from": "dmorgan", "subject": "Docking station not detected", "status": "open"}}


class LookupArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown fields are an error, not ignored
    ticket_id: str


def lookup_ticket(ticket_id: str) -> dict:
    ticket = TICKETS.get(ticket_id.strip().upper())
    return {"ticket_id": ticket_id, **ticket} if ticket else {"error": "not_found", "message": f"No ticket {ticket_id!r}. Ask the user to check the id."}


def explode(**_):
    raise RuntimeError("ticket database is down")


# name -> (argument model, function)
REGISTRY = {"lookup_ticket": (LookupArgs, lookup_ticket), "lookup_ticket_broken": (LookupArgs, explode)}
TOOLS = [{"type": "function", "function": {
    "name": "lookup_ticket", "description": "Read a helpdesk ticket by id such as LL-2080.",
    "parameters": {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]}}}]


def execute(name: str, raw_arguments: str) -> dict:
    """Never raises. Always returns a dict the model can read."""
    if name not in REGISTRY:
        return {"error": "unknown_tool", "message": f"No tool called {name!r}. Available: {sorted(REGISTRY)}."}
    model_class, function = REGISTRY[name]
    try:
        data = json.loads(raw_arguments or "{}")
    except ValueError as error:
        return {"error": "bad_json", "message": f"Arguments are not valid JSON: {error}"}
    try:
        args = model_class(**data) if isinstance(data, dict) else model_class.model_validate(data)
    except (ValidationError, TypeError) as error:
        first = error.errors()[0] if isinstance(error, ValidationError) else {"msg": str(error)}
        return {"error": "bad_arguments", "message": f"{first.get('loc', '')} {first['msg']}".strip()}
    try:
        return function(**args.model_dump())
    except Exception as error:  # a tool may fail in any way; the agent must survive it
        return {"error": "tool_failed", "message": f"{type(error).__name__}: {error}"}


@lesson("02.4/1", "Tool errors are data: classify them and send them back")
def main(ctx):
    ctx.step("Part 1: five bad calls, no model involved")
    cases = [
        ("lookup_ticket_v2", '{"ticket_id": "LL-2080"}'),
        ("lookup_ticket", '{"ticket_id": "LL-2080"'),
        ("lookup_ticket", '{"id": "LL-2080"}'),
        ("lookup_ticket_broken", '{"ticket_id": "LL-2080"}'),
        ("lookup_ticket", '{"ticket_id": "LL-9999"}'),
    ]
    for name, raw in cases:
        ctx.show_tool_call(name, raw, json.dumps(execute(name, raw)))
    ctx.note("Each result names the KIND of error and says what to do. 'error' alone is not enough for the model to recover.")

    ctx.step("Part 2: the real model meets a ticket that does not exist")
    messages = [
        {"role": "system", "content": "You are the Larkspur Labs helpdesk agent. Use lookup_ticket. If the ticket is not found, say so plainly and ask for the correct id."},
        {"role": "user", "content": "What is the status of ticket LL-9999?"},
    ]
    ctx.show_messages(messages)
    for turn in range(1, MAX_STEPS + 1):
        ctx.step(f"Model call {turn} of at most {MAX_STEPS}")
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, tools=TOOLS)
        message = response.choices[0].message
        if not message.tool_calls:
            ctx.show_response(response)
            break
        ctx.record_usage(response.usage, quiet=True)
        messages.append({"role": "assistant", "content": message.content, "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in message.tool_calls]})
        for call in message.tool_calls:
            result = execute(call.function.name, call.function.arguments)
            ctx.show_tool_call(call.function.name, call.function.arguments, json.dumps(result))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
    else:
        ctx.note(f"Stopped at the cap of {MAX_STEPS} calls. A model that keeps retrying a missing ticket is exactly what the cap is for.")
    ctx.note("The agent survived a 'failed' lookup because the failure was an ordinary tool message, not an exception.")


if __name__ == "__main__":
    main()
