"""02.1/2  Complete the round trip by hand

The full tool-calling exchange takes TWO model calls:

  1. send the question and the tools; the model replies with tool_calls;
  2. your program runs each requested function, then sends the conversation back with
     - the assistant message that holds the tool_calls, unchanged, and
     - one `role: "tool"` message per call, carrying the result and the matching `tool_call_id`;
     the model now answers in text.

The question asks about two tickets, so many models request both lookups in one reply
(parallel tool calls). The loop below handles one call or several the same way.

Run it:   ./run 02.1/2          (Windows: run 02.1/2)
"""

import json

from labkit import lesson

# The data the model cannot see. Only our function can read it.
TICKETS = {
    "LL-2041": {"status": "in progress", "owner": "Tomas (Desktop support)", "last_update": "Replacement charger ordered, arrives Thursday."},
    "LL-2044": {"status": "waiting on employee", "owner": "Aisha (Network)", "last_update": "Asked for a photo of the VPN error message."},
}


def lookup_ticket(ticket_id: str) -> dict:
    """The real Python function behind the tool. The model never sees this code."""
    ticket = TICKETS.get(ticket_id.strip().upper())
    if ticket is None:
        return {"error": f"No ticket with id {ticket_id!r}."}
    return {"ticket_id": ticket_id.strip().upper(), **ticket}


LOOKUP_TICKET = {
    "type": "function",
    "function": {
        "name": "lookup_ticket",
        "description": "Look up a Larkspur Labs helpdesk ticket by its id and return its status, owner and last update.",
        "parameters": {
            "type": "object",
            "properties": {"ticket_id": {"type": "string", "description": "The ticket id, for example LL-2041."}},
            "required": ["ticket_id"],
            "additionalProperties": False,
        },
    },
}

# Name -> Python function. This table is how your program turns a request into a real call.
FUNCTIONS = {"lookup_ticket": lookup_ticket}


@lesson("02.1/2", "Complete the round trip by hand")
def main(ctx):
    ctx.step("Call 1: question plus tools")
    messages = [
        {"role": "system", "content": "You are the Larkspur Labs IT helpdesk assistant. Use the tools when they help. Answer in two or three sentences."},
        {"role": "user", "content": "Can you tell me where tickets LL-2041 and LL-2044 are up to?"},
    ]
    ctx.show_messages(messages)
    response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, tools=[LOOKUP_TICKET])
    ctx.show_response(response)
    message = response.choices[0].message
    if not message.tool_calls:
        ctx.note("No tool calls this time: the model answered directly, so there is no round trip to complete.")
        return
    ctx.note(f"The model asked for {len(message.tool_calls)} tool call(s) in one reply.")
    if len(message.tool_calls) > 1:
        ctx.note("Several calls in one reply are 'parallel tool calls'. Run them all, then answer them all.")

    ctx.step("Your program runs the functions")
    # Keep the assistant message exactly as it came, tool_calls included: the tool results must
    # follow the message that asked for them.
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
    for call in message.tool_calls:
        function = FUNCTIONS.get(call.function.name)
        try:
            arguments = json.loads(call.function.arguments or "{}")
            result = function(**arguments) if function else {"error": f"Unknown tool {call.function.name!r}."}
        except (ValueError, TypeError) as error:
            # Bad JSON or wrong argument names: tell the model instead of crashing.
            arguments, result = call.function.arguments, {"error": f"Could not call the tool: {error}"}
        ctx.show_tool_call(call.function.name, arguments, json.dumps(result))
        messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})

    ctx.step("Call 2: the same conversation plus the results")
    ctx.note("This is the whole list sent now. tool_call_id ties each result to the request it answers.")
    ctx.show_messages(messages)
    final = ctx.client.chat.completions.create(model=ctx.model, messages=messages, tools=[LOOKUP_TICKET])
    ctx.show_response(final)
    if final.choices[0].message.tool_calls:
        ctx.note("The model asked for yet another tool call. Handling that needs a loop: see script 3.")

    ctx.step("Two more controls worth knowing")
    ctx.note('tool_choice="auto" (the default) lets the model decide; "none" forbids tools; "required" forces some tool;')
    ctx.note('{"type": "function", "function": {"name": "lookup_ticket"}} forces that one tool.')
    ctx.note("parallel_tool_calls=False asks for at most one call per reply (where the provider supports it).")


if __name__ == "__main__":
    main()
