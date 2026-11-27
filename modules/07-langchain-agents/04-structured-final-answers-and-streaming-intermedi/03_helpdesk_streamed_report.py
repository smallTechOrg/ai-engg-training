"""07.4/3  Helpdesk: stream progress, then return a validated report

The two ideas together on the helpdesk scenario. The agent looks up the open tickets of one
owner, streams its progress (so a UI could show "looking up LL-2041..."), and ends with a
validated `OwnerReport` object. The script then applies ordinary code to the typed result.

Run it:   ./run 07.4/3          (Windows: run 07.4/3)
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
    "LL-2045": {"status": "open", "owner": "Priya", "summary": "Shared drive access request", "priority": "medium"},
    "LL-2044": {"status": "open", "owner": "Tom", "summary": "Monitor flickers", "priority": "low"},
}


@tool
def open_tickets_for(owner: str) -> str:
    """List open ticket ids for a helpdesk owner such as Priya."""
    return ", ".join(k for k, t in TICKETS.items() if t["owner"].lower() == owner.lower() and t["status"] == "open") or "none"


@tool
def lookup_ticket(ticket_id: str) -> str:
    """Return status, owner, priority and summary of one ticket id."""
    return str(TICKETS.get(ticket_id, f"no ticket named {ticket_id}"))


class TicketLine(BaseModel):
    ticket_id: str
    priority: Literal["high", "medium", "low"]
    summary: str


class OwnerReport(BaseModel):
    """Workload report for one helpdesk owner."""

    owner: str
    tickets: list[TicketLine] = Field(description="Every open ticket the owner has, highest priority first.")
    advice: str = Field(description="One sentence on what to do first.")


@lesson("07.4/3", "Helpdesk: streamed progress, typed report")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
    agent = create_agent(
        model,
        tools=[open_tickets_for, lookup_ticket],
        system_prompt="You are the Larkspur Labs helpdesk assistant. Find the owner's open tickets, look each one up, then report.",
        response_format=ToolStrategy(OwnerReport),
    )
    ctx.step("Stream the run")
    final_state = None
    try:
        # stream_mode="values" yields the whole state after each step; the last one is the result.
        for state in agent.stream({"messages": [("user", "Give me Priya's workload report.")]}, {"recursion_limit": 15}, stream_mode="values"):
            final_state = state
            last = state["messages"][-1]
            if last.type == "ai" and last.tool_calls:
                ctx.record_usage(last.usage_metadata, quiet=True)
                ctx.note("progress: calling " + ", ".join(f"{c['name']}({list(c['args'].values())})" for c in last.tool_calls))
            elif last.type == "tool":
                ctx.note(f"progress: got {str(last.content)[:60]}")
            elif last.type == "ai":
                ctx.record_usage(last.usage_metadata, quiet=True)
                ctx.note("progress: final turn")
    except Exception as exc:
        ctx.note(f"Stopped: {type(exc).__name__}: {str(exc)[:140]}")

    ctx.step("Use the typed result")
    report = (final_state or {}).get("structured_response")
    if not isinstance(report, OwnerReport):
        ctx.note("No OwnerReport came back; a real service would retry once or return the plain text. That is a handled outcome.")
        return
    ctx.show_data("OwnerReport", report.model_dump())
    known = {t.ticket_id for t in report.tickets if t.ticket_id in TICKETS}
    ctx.note(f"Ticket ids in the report that exist in the data: {sorted(known)} of {len(report.tickets)}")
    expected = {k for k, t in TICKETS.items() if t["owner"] == "Priya"}
    ctx.note(f"Complete? {known == expected} (expected {sorted(expected)}). Typed output is well-formed, not automatically correct: check it.")


if __name__ == "__main__":
    main()
