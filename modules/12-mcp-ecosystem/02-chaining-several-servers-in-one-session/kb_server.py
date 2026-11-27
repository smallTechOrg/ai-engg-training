"""Server 2 of 2 for lesson 12.2 (not a lesson: the lessons launch it as a subprocess).

Larkspur Labs knowledge base: search articles and read one. Note that it also has a tool
called `search`, the same name as the ticket server's. That clash is deliberate.
Run by hand to see it wait for JSON-RPC on stdin:  python kb_server.py
"""

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("knowledge-base")

ARTICLES = {
    "KB-10": ("VPN keeps disconnecting", "Switch the VPN client to the TCP profile, then update the client to 5.2 or later. If it still drops, collect the client log and escalate to the network team."),
    "KB-11": ("Swollen laptop battery", "Power the laptop off, do not charge it, move it away from desks and bring it to the hardware bench. Never press on the battery."),
    "KB-12": ("Wi-Fi is slow in a room", "Check the access point load in the dashboard; if more than 40 clients are attached, ask the network team to rebalance channels."),
}


@mcp.tool()
def search(text: str) -> str:
    """Search knowledge-base article titles and bodies for a word. Returns article ids and titles."""
    hits = [f"{i}: {title}" for i, (title, body) in ARTICLES.items() if text.lower() in (title + " " + body).lower()]
    return "\n".join(hits) or "No articles match."


@mcp.tool()
def read_article(article_id: str) -> str:
    """Read a knowledge-base article by id (for example KB-10)."""
    item = ARTICLES.get(article_id.strip().upper())
    if item is None:
        return f"No article {article_id}. Known ids: {', '.join(ARTICLES)}"
    return f"{article_id.strip().upper()} {item[0]}: {item[1]}"


if __name__ == "__main__":
    mcp.run("stdio")
