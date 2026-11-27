"""07.4/1  A structured final answer from an agent

By default an agent ends with free text. Pass `response_format=<pydantic model>` to
`create_agent` and the final result also carries `result["structured_response"]`, a validated
object your code can use. Under the hood LangChain either asks the provider for JSON that
matches the schema (ProviderStrategy) or adds the schema as one more "tool" the model must call
to finish (ToolStrategy). Here we pick ToolStrategy, which works with any tool-calling model.

Run it:   ./run 07.4/1          (Windows: run 07.4/1)
"""

from typing import Literal

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from labkit import lesson

TICKETS = {
    "LL-2041": {"status": "open", "owner": "Priya", "summary": "VPN token reset", "priority": "high"},
    "LL-2043": {"status": "open", "owner": "Priya", "summary": "Printer on floor 3 offline", "priority": "medium"},
}


@tool
def lookup_ticket(ticket_id: str) -> str:
    """Return status, owner, priority and summary of one ticket id such as LL-2041."""
    return str(TICKETS.get(ticket_id, f"no ticket named {ticket_id}"))


class TicketReport(BaseModel):
    """The final answer about one ticket."""

    ticket_id: str = Field(description="The ticket id the answer is about.")
    status: Literal["open", "resolved", "unknown"]
    owner: str | None = Field(default=None, description="Owner's first name, or null if unknown.")
    next_action: str = Field(description="One short sentence: what should happen next.")


@lesson("07.4/1", "A structured final answer")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)

    ctx.step("Without response_format: free text")
    plain = create_agent(model, tools=[lookup_ticket], system_prompt="You are the Larkspur Labs helpdesk assistant. Be brief.")
    question = "What is going on with ticket LL-2041?"
    result = plain.invoke({"messages": [("user", question)]}, {"recursion_limit": 7})
    for m in result["messages"]:
        if m.type == "ai":
            ctx.record_usage(m.usage_metadata, quiet=True)
    ctx.note(f"Result keys: {sorted(result)}")
    ctx.note(f"Final message (text to parse yourself): {result['messages'][-1].content!r}")

    ctx.step("With response_format=ToolStrategy(TicketReport)")
    ctx.note("The schema is offered to the model as a final 'tool'. Calling it ends the run.")
    typed = create_agent(
        model,
        tools=[lookup_ticket],
        system_prompt="You are the Larkspur Labs helpdesk assistant. Look the ticket up, then give the final report.",
        response_format=ToolStrategy(TicketReport),
    )
    try:
        result = typed.invoke({"messages": [("user", question)]}, {"recursion_limit": 9})
    except Exception as exc:
        ctx.note(f"Stopped: {type(exc).__name__}: {str(exc)[:140]}")
        return
    for m in result["messages"]:
        if m.type == "ai":
            ctx.record_usage(m.usage_metadata, quiet=True)
    ctx.note(f"Result keys: {sorted(result)}")
    report = result.get("structured_response")

    ctx.step("Use the object")
    if isinstance(report, TicketReport):
        ctx.show_data("structured_response", report.model_dump())
        ctx.note(f"A typed object: report.status == {report.status!r}, so `if report.status == 'open':` is safe code.")
    else:
        ctx.note(f"No structured_response of the right type (got {type(report).__name__}). The model never called the schema.")
        ctx.note("Always check for this: a provider or model that cannot follow the schema ends the run without one.")
    ctx.note(f"Last message text: {str(result['messages'][-1].content)[:150]!r}")


if __name__ == "__main__":
    main()
