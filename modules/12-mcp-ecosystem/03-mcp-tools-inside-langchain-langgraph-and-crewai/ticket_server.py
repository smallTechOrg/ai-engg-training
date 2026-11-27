"""The helpdesk server for lesson 12.3 (not a lesson: the lessons launch it as a subprocess).

Larkspur Labs ticket desk: look up a ticket, search tickets, find who owns a category.
Run by hand to see it wait for JSON-RPC on stdin:  python ticket_server.py
"""

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("ticket-desk")

TICKETS = {
    "T-1001": {"subject": "VPN drops every ten minutes", "status": "open", "category": "network"},
    "T-1002": {"subject": "Laptop battery swells", "status": "open", "category": "hardware"},
    "T-1003": {"subject": "Cannot open shared finance sheet", "status": "closed", "category": "access"},
    "T-1004": {"subject": "Wi-Fi slow in meeting room B", "status": "open", "category": "network"},
}
OWNERS = {"network": "Priya (network team)", "hardware": "Tomas (hardware bench)", "access": "Jun (identity team)"}


@mcp.tool()
def lookup(ticket_id: str) -> str:
    """Look up one ticket by id (for example T-1001): subject, status, category and the owner of that category."""
    ticket = TICKETS.get(ticket_id.strip().upper())
    if ticket is None:
        return f"No ticket with id {ticket_id}. Known ids: {', '.join(TICKETS)}"
    owner = OWNERS.get(ticket["category"], "unassigned")
    return f"{ticket_id.strip().upper()}: {ticket['subject']} (status: {ticket['status']}, category: {ticket['category']}, owner: {owner})"


@mcp.tool()
def search(text: str) -> str:
    """Search ticket subjects for a word. Returns matching ticket ids and subjects."""
    hits = [f"{i}: {t['subject']}" for i, t in TICKETS.items() if text.lower() in t["subject"].lower()]
    return "\n".join(hits) or "No tickets match."


if __name__ == "__main__":
    mcp.run("stdio")
