"""07.1/2  bind_tools and the tool loop with LangChain types

The same loop as lesson 02.2, written with LangChain objects: `model.bind_tools(...)`, read
`AIMessage.tool_calls`, run each tool, send the results back as `ToolMessage`s.

Run it:   ./run 07.1/2          (Windows: run 07.1/2)
"""

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from labkit import lesson

TICKETS = {
    "LL-2041": "open, owner Priya, waiting on a VPN token reset",
    "LL-2042": "resolved, owner Tom, laptop battery replaced",
}


@tool
def lookup_ticket(ticket_id: str) -> str:
    """Look up a Larkspur Labs helpdesk ticket by its id and return its status."""
    return TICKETS.get(ticket_id, f"no ticket named {ticket_id}")


@tool
def add_numbers(a: int, b: int) -> int:
    """Add two whole numbers."""
    return a + b


MAX_ROUNDS = 4


@lesson("07.1/2", "bind_tools and the tool loop")
def main(ctx):
    ctx.step("Create the model and bind the tools")
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
    tools = {t.name: t for t in (lookup_ticket, add_numbers)}
    model_with_tools = model.bind_tools(list(tools.values()))
    ctx.note("bind_tools returns a new runnable that sends the tool schemas with every call.")
    ctx.note(f"Tools bound: {', '.join(tools)}")

    ctx.step("Ask a question and loop")
    messages = [
        SystemMessage("You are the Larkspur Labs IT helpdesk assistant. Use tools when they help."),
        HumanMessage("What is the status of ticket LL-2041?"),
    ]
    for round_no in range(1, MAX_ROUNDS + 1):
        ctx.note(f"Round {round_no} of at most {MAX_ROUNDS}")
        ai = model_with_tools.invoke(messages)
        ctx.record_usage(ai.usage_metadata)
        messages.append(ai)
        ctx.note(f"AIMessage.content = {ai.content!r}")
        ctx.note(f"AIMessage.tool_calls = {ai.tool_calls}")
        if not ai.tool_calls:
            ctx.note("No tool calls: this is the final answer.")
            break
        for call in ai.tool_calls:
            # call is {"name", "args", "id", "type"}. Run the matching tool and answer with the same id.
            result = tools[call["name"]].invoke(call["args"])
            ctx.show_tool_call(call["name"], call["args"], result)
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
    else:
        ctx.note(f"Stopped at the cap of {MAX_ROUNDS} rounds without a final answer.")

    ctx.step("The final conversation")
    for m in messages:
        ctx.note(f"{m.type:>6} | {str(m.content)[:100]}" + (f"  tool_calls={len(m.tool_calls)}" if getattr(m, "tool_calls", None) else ""))
    ctx.note("By hand (02.2) you built dicts and parsed JSON argument strings; here args arrive already parsed.")


if __name__ == "__main__":
    main()
