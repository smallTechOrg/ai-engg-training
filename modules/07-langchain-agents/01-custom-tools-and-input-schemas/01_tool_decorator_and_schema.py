"""07.1/1  `@tool` and the args schema

In lesson 02.1 you wrote a tool's JSON schema by hand. LangChain builds it for you from a
Python function: the function name becomes the tool name, the docstring becomes the
description, and the type hints (or a pydantic model) become the argument schema.

No model call here: this script only inspects what `@tool` generates.

Run it:   ./run 07.1/1          (Windows: run 07.1/1)
"""

from langchain_core.tools import tool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, Field

from labkit import lesson

# The hand-written schema from lesson 02.1, for comparison.
HAND_WRITTEN = {
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


@tool
def lookup_ticket(ticket_id: str) -> str:
    """Look up a Larkspur Labs helpdesk ticket by its id and return its status, owner and last update."""
    return f"{ticket_id}: open, owner Priya, last update yesterday"


class LookupArgs(BaseModel):
    """Arguments for lookup_ticket."""

    ticket_id: str = Field(description="The ticket id, for example LL-2041.", pattern=r"^LL-\d{4}$")


@tool("lookup_ticket", args_schema=LookupArgs)
def lookup_ticket_v2(ticket_id: str) -> str:
    """Look up a Larkspur Labs helpdesk ticket by its id and return its status, owner and last update."""
    return f"{ticket_id}: open, owner Priya, last update yesterday"


@lesson("07.1/1", "@tool and the args schema")
def main(ctx):
    ctx.step("What @tool made from a plain function")
    ctx.note("The decorator returns a tool object, not a function. Its parts are read from your code.")
    ctx.show_data(
        "lookup_ticket (type hints only)",
        {
            "type": type(lookup_ticket).__name__,
            "name": lookup_ticket.name,
            "description": lookup_ticket.description,
            "args": lookup_ticket.args,
        },
    )

    ctx.step("The full schema a model would receive")
    ctx.note("convert_to_openai_tool is what bind_tools uses. Compare with the dict written by hand in lesson 02.1.")
    generated = convert_to_openai_tool(lookup_ticket)
    ctx.show_data("Generated", generated)
    ctx.show_data("Hand-written (02.1/1)", HAND_WRITTEN)
    ctx.note(f"Same name: {generated['function']['name'] == HAND_WRITTEN['function']['name']}. "
             f"Same description: {generated['function']['description'] == HAND_WRITTEN['function']['description']}. "
             "The argument description is missing: type hints carry no prose.")

    ctx.step("Add a pydantic args schema")
    ctx.note("A pydantic model lets you add descriptions and constraints, and validates the arguments for you.")
    ctx.show_data("lookup_ticket_v2 schema", convert_to_openai_tool(lookup_ticket_v2))

    ctx.step("Call the tool yourself with .invoke")
    ctx.show_tool_call("lookup_ticket_v2", {"ticket_id": "LL-2041"}, lookup_ticket_v2.invoke({"ticket_id": "LL-2041"}))

    ctx.step("Bad arguments are rejected before your function runs")
    try:
        lookup_ticket_v2.invoke({"ticket_id": "banana"})
    except Exception as exc:  # pydantic ValidationError
        ctx.note(f"{type(exc).__name__}: " + str(exc).splitlines()[0])
        ctx.note("In an agent you would catch this and hand the message back to the model so it can retry.")
    ctx.note("By hand (02.1) you wrote the dict; with LangChain the function and its hints are the schema.")


if __name__ == "__main__":
    main()
