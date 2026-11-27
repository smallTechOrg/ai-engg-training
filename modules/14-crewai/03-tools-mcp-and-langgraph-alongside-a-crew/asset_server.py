"""A tiny Larkspur Labs asset-inventory MCP server (not a lesson: 14.3/1 launches it as a subprocess)."""

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("larkspur-assets")

ASSETS = {
    "LT-204": "Laptop, 3 years old, battery health 61 percent, warranty expired",
    "LT-310": "Laptop, 8 months old, battery health 97 percent, warranty valid until next March",
    "MN-077": "27 inch monitor, dock firmware 2.1 (update 2.4 available)",
}


@mcp.tool()
def get_asset(tag: str) -> str:
    """Look up a company asset by tag (for example LT-204) and return its age, health and warranty."""
    return ASSETS.get(tag.strip().upper(), f"No asset {tag}. Known asset tags: {', '.join(ASSETS)}")


if __name__ == "__main__":
    mcp.run("stdio")
