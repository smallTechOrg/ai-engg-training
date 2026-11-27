"""12.2/1  Two servers, one tool registry (no model)

12.1 talked to one server. A real host talks to several, and then two problems appear:

  1. Two servers can offer a tool with the SAME name (both of ours have `search`).
  2. When the model calls a tool, the host must know WHICH server to send it to.

The fix is a registry: give every server an alias, expose tools as `alias__tool`, and keep a
routing table from that name back to (session, original name). This script builds the
registry from two small local servers and routes a few calls. No model is involved.

Run it:   ./run 12.2/1          (Windows: run 12.2/1)
"""

import sys
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from labkit import lesson

HERE = Path(__file__).parent
SERVERS = {"tickets": HERE / "ticket_server.py", "kb": HERE / "kb_server.py"}


def text_of(result):
    return "".join(part.text for part in result.content if part.type == "text")


@lesson("12.2/1", "Two servers, one tool registry")
async def main(ctx):
    async with AsyncExitStack() as stack:
        ctx.step("Start both servers and collect their tools")
        routes = {}  # "alias__tool" -> (session, original tool name)
        raw_names = []
        for alias, script in SERVERS.items():
            params = StdioServerParameters(command=sys.executable, args=[str(script)])
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            init = await session.initialize()
            tools = (await session.list_tools()).tools
            ctx.note(f"{alias:<8} -> server '{init.server_info.name}' offers: " + ", ".join(t.name for t in tools))
            for tool in tools:
                raw_names.append(tool.name)
                routes[f"{alias}__{tool.name}"] = (session, tool.name)

        ctx.step("The problem: the plain names collide")
        clashes = sorted({n for n in raw_names if raw_names.count(n) > 1})
        ctx.note("Plain tool names from both servers: " + ", ".join(raw_names))
        ctx.note("Names offered more than once: " + ", ".join(clashes) + ". A model that calls `search` would be ambiguous.")

        ctx.step("The fix: namespaced names and a routing table")
        ctx.note("Registry: " + ", ".join(routes))
        ctx.note("Prefixes also help the model: `tickets__search` says what is being searched.")

        ctx.step("Route three calls by name")
        for name, args in [
            ("tickets__search", {"text": "VPN"}),
            ("kb__search", {"text": "VPN"}),
            ("kb__read_article", {"article_id": "KB-10"}),
        ]:
            session, original = routes[name]
            result = await session.call_tool(original, args)
            ctx.show_tool_call(name, args, text_of(result))

        ctx.step("An unknown name is an error you handle, not a crash")
        wanted = "search"
        if wanted not in routes:
            ctx.note(f"`{wanted}` is not in the registry, so the host answers 'Tool {wanted} is not available.' instead of guessing a server.")


if __name__ == "__main__":
    main()
