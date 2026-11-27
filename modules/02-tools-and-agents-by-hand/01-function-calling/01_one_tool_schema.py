"""02.1/1  Describe a tool and see the model ask for it

You describe a Python function to the model as a JSON schema and send it with `tools=[...]`.
When the model decides the function would help, it does not answer in text. It replies with
a `tool_calls` entry: the function's name and the arguments, as a JSON string.

The model never runs anything. It only asks. Running the function is your program's job
(script 2).

Run it:   ./run 02.1/1          (Windows: run 02.1/1)
"""

import json

from labkit import lesson

# One tool, described the way the Chat Completions API expects: a name, a description the model
# reads to decide WHEN to use it, and a JSON Schema for the arguments.
LOOKUP_TICKET = {
    "type": "function",
    "function": {
        "name": "lookup_ticket",
        "description": "Look up a Larkspur Labs helpdesk ticket by its id and return its status, owner and last update.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "The ticket id, for example LL-2041."},
            },
            "required": ["ticket_id"],
            "additionalProperties": False,
        },
    },
}


@lesson("02.1/1", "Describe a tool and see the model ask for it")
def main(ctx):
    ctx.step("Describe the tool as a JSON schema")
    ctx.note("This is all the model will ever know about the function: its name, its description, its arguments.")
    ctx.show_data("The tool definition", LOOKUP_TICKET)

    ctx.step("Ask a question the tool can answer")
    messages = [
        {"role": "system", "content": "You are the Larkspur Labs IT helpdesk assistant. Use the tools when they help."},
        {"role": "user", "content": "What is the status of ticket LL-2041?"},
    ]
    ctx.show_messages(messages)
    response = ctx.client.chat.completions.create(
        model=ctx.model,
        messages=messages,
        tools=[LOOKUP_TICKET],
    )
    ctx.show_response(response)

    ctx.step("Read the tool call")
    message = response.choices[0].message
    if not message.tool_calls:
        ctx.note("The model answered in text instead of asking for the tool. That is allowed: the model decides.")
        ctx.note("It is also what you see when a model or provider does not support tools. Run ./run doctor to check.")
        return
    ctx.note(f"finish_reason is '{response.choices[0].finish_reason}' and content is {message.content!r}: no answer yet, a request.")
    for call in message.tool_calls:
        ctx.show_data(
            "One entry of message.tool_calls",
            {"id": call.id, "type": call.type, "function.name": call.function.name, "function.arguments": call.function.arguments},
        )
        ctx.note("function.arguments is a STRING of JSON, written by the model. Parse it before you trust it:")
        try:
            arguments = json.loads(call.function.arguments)
            ctx.show_data("json.loads(function.arguments)", arguments)
        except ValueError as error:
            ctx.note(f"It is not valid JSON ({error}). Your program would tell the model, or give up on this call.")

    ctx.step("What happened, and what did not")
    ctx.note("The model chose a tool and wrote its arguments. No function ran: there is no Python function yet.")
    ctx.note("Script 2 runs it and sends the result back, so the model can write the real answer.")


if __name__ == "__main__":
    main()
