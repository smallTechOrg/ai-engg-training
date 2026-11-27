"""A tiny Larkspur Labs helpdesk MCP server (not a lesson: the lessons launch it as a subprocess).

It exposes the three MCP primitives: one tool, one resource, one prompt.
Run by hand to see it wait for JSON-RPC on stdin:  python helpdesk_server.py
"""

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("larkspur-helpdesk")

TICKETS = {
    "T-1001": {"subject": "VPN drops every ten minutes", "status": "open", "category": "network"},
    "T-1002": {"subject": "Laptop battery swells", "status": "open", "category": "hardware"},
    "T-1003": {"subject": "Cannot open shared finance sheet", "status": "closed", "category": "access"},
}


@mcp.tool()
def lookup_ticket(ticket_id: str) -> str:
    """Look up a helpdesk ticket by its id (for example T-1001) and return its subject, status and category."""
    ticket = TICKETS.get(ticket_id.strip().upper())
    if ticket is None:
        return f"No ticket with id {ticket_id}. Known ids: {', '.join(TICKETS)}"
    return f"{ticket_id.strip().upper()}: {ticket['subject']} (status: {ticket['status']}, category: {ticket['category']})"


@mcp.resource("helpdesk://policies/password")
def password_policy() -> str:
    """Larkspur Labs password policy."""
    return "Passwords: at least 14 characters, rotated every 365 days, never reused. Resets go through the self-service portal."


@mcp.prompt()
def triage_prompt(ticket_text: str) -> str:
    """A reusable instruction for triaging a ticket."""
    return f"Classify this IT helpdesk ticket as network, hardware, software, access or other, and give a one-line reason.\n\nTicket: {ticket_text}"


if __name__ == "__main__":
    mcp.run("stdio")
