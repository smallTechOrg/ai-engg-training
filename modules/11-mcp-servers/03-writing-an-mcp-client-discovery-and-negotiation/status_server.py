"""A tools-only MCP server written with the low-level API, for lesson 11.3.

Not a lesson: the scripts launch it over stdio. The high-level `MCPServer` announces tools,
resources and prompts whether or not you registered any. The low-level `Server` announces
only the handlers you pass in, so this server really does offer less, and a client that
negotiates properly can see that.
"""

import anyio
import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

KNOWN = {"vpn": "degraded (one gateway restarting)", "mail": "ok", "wiki": "ok"}


async def on_list_tools(ctx, params):
    return types.ListToolsResult(
        tools=[
            types.Tool(
                name="service_status",
                description="Report whether a Larkspur Labs internal service is up (vpn, mail, wiki).",
                input_schema={
                    "type": "object",
                    "properties": {"service": {"type": "string", "enum": sorted(KNOWN)}},
                    "required": ["service"],
                },
            )
        ]
    )


async def on_call_tool(ctx, params):
    service = (params.arguments or {}).get("service", "")
    text = f"{service}: {KNOWN.get(service, 'unknown service')}"
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=service not in KNOWN)


server = Server("larkspur-status", version="0.3.0", on_list_tools=on_list_tools, on_call_tool=on_call_tool)


async def run() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(run)
