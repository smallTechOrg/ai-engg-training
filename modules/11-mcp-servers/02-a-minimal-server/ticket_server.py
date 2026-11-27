"""A Larkspur Labs ticket MCP server for lesson 11.2 (not a lesson: scripts launch it over stdio).

Shows tools with typed/validated arguments, static and templated resources, and prompts.
Run by hand to see it wait for JSON-RPC on stdin:  python ticket_server.py
"""

from typing import Annotated, Literal

from pydantic import Field

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError, ToolError

mcp = MCPServer("larkspur-tickets", instructions="Read and search Larkspur Labs helpdesk tickets.")

TICKETS = {
    "T-1001": {"subject": "VPN drops every ten minutes", "status": "open", "category": "network", "priority": 2},
    "T-1002": {"subject": "Laptop battery swells", "status": "open", "category": "hardware", "priority": 1},
    "T-1003": {"subject": "Cannot open shared finance sheet", "status": "closed", "category": "access", "priority": 3},
    "T-1004": {"subject": "Wi-Fi unavailable in meeting room 4", "status": "open", "category": "network", "priority": 3},
}

Status = Literal["open", "closed"]


@mcp.tool()
def search_tickets(
    category: Annotated[str, Field(description="network, hardware, software, access or other")],
    status: Annotated[Status, Field(description="Which tickets to return")] = "open",
    limit: Annotated[int, Field(description="Maximum rows", ge=1, le=10)] = 5,
) -> str:
    """Search tickets by category and status. Returns one line per ticket, newest id first."""
    rows = [
        f"{tid}: {t['subject']} (priority {t['priority']})"
        for tid, t in sorted(TICKETS.items(), reverse=True)
        if t["category"] == category.lower() and t["status"] == status
    ]
    return "\n".join(rows[:limit]) or f"No {status} tickets in category {category}."


@mcp.tool()
def set_priority(
    ticket_id: Annotated[str, Field(pattern=r"^T-\d{4}$", description="Ticket id such as T-1001")],
    priority: Annotated[int, Field(ge=1, le=4, description="1 = urgent ... 4 = low")],
) -> str:
    """Change a ticket's priority (1 urgent to 4 low). Fails for unknown tickets."""
    if ticket_id not in TICKETS:
        raise ToolError(f"No ticket {ticket_id}. Known ids: {', '.join(TICKETS)}")
    TICKETS[ticket_id]["priority"] = priority
    return f"{ticket_id} priority is now {priority}"


@mcp.resource("helpdesk://policies/password", mime_type="text/plain")
def password_policy() -> str:
    """Larkspur Labs password policy (a static resource)."""
    return "Passwords: at least 14 characters, rotated every 365 days, never reused."


@mcp.resource("helpdesk://tickets/{ticket_id}", mime_type="application/json")
def ticket_resource(ticket_id: str) -> dict:
    """One ticket as JSON (a resource template: the client fills in the id)."""
    ticket = TICKETS.get(ticket_id.upper())
    if ticket is None:
        raise ResourceNotFoundError(f"No ticket {ticket_id}")
    return {"id": ticket_id.upper(), **ticket}


@mcp.prompt()
def triage_prompt(ticket_text: str, audience: Literal["agent", "customer"] = "agent") -> str:
    """Triage a ticket; the audience changes the tone of the reason."""
    tone = "technical" if audience == "agent" else "plain and friendly"
    return (
        "Classify this IT helpdesk ticket as network, hardware, software, access or other. "
        f"Give a one-line reason in a {tone} tone.\n\nTicket: {ticket_text}"
    )


if __name__ == "__main__":
    mcp.run("stdio")
