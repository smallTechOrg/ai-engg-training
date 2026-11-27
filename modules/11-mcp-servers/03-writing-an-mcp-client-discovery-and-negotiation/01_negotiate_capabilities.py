"""11.3/1  Discovery and negotiation: ask first, then call

A client should not assume what a server offers. After `initialize` it knows the protocol
version, the server's identity, its instructions and its CAPABILITIES. This script connects
to two servers (a full one and a tools-only one) and builds a catalogue that only asks for
what each server announced. It also shows what happens when a client asks anyway.

No model is involved.

Run it:   ./run 11.3/1          (Windows: run 11.3/1)
"""

import os
import sys
from pathlib import Path

import mcp_types as types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError

from labkit import lesson

HERE = Path(__file__).parent
SERVERS = {"tickets": HERE / "ticket_server.py", "status": HERE / "status_server.py"}


async def discover(session: ClientSession) -> dict:
    """Build a catalogue, calling only the list methods the server announced."""
    caps = session.server_capabilities
    catalogue = {"tools": [], "resources": [], "templates": [], "prompts": []}
    if caps.tools:
        catalogue["tools"] = [t.name for t in (await session.list_tools()).tools]
    if caps.resources:
        catalogue["resources"] = [r.uri for r in (await session.list_resources()).resources]
        catalogue["templates"] = [t.uri_template for t in (await session.list_resource_templates()).resource_templates]
    if caps.prompts:
        catalogue["prompts"] = [p.name for p in (await session.list_prompts()).prompts]
    return catalogue


@lesson("11.3/1", "Discovery and capability negotiation")
async def main(ctx):
    quiet = open(os.devnull, "w")
    try:
        for label, path in SERVERS.items():
            ctx.step(f"Connect to the {label} server")
            params = StdioServerParameters(command=sys.executable, args=[str(path)])
            async with stdio_client(params, errlog=quiet) as (read, write):
                # client_info is OUR half of the handshake: who is calling. read_timeout_seconds
                # makes every request fail instead of hanging forever if the server stalls.
                client_info = types.Implementation(name="larkspur-helpdesk-host", version="0.1.0")
                async with ClientSession(read, write, client_info=client_info, read_timeout_seconds=15) as session:
                    init = await session.initialize()
                    ctx.show_data(
                        "Result of initialize",
                        {
                            "protocol_version": init.protocol_version,
                            "server": f"{init.server_info.name} {init.server_info.version}".strip(),
                            "instructions": init.instructions,
                            "announced": sorted(init.capabilities.model_dump(exclude_none=True)),
                        },
                    )
                    ctx.note("Discover only what was announced:")
                    ctx.show_data(f"catalogue of {label}", await discover(session))

                    if not session.server_capabilities.resources:
                        ctx.step(f"What if we ask the {label} server for resources anyway?")
                        try:
                            await session.list_resources()
                        except MCPError as exc:
                            ctx.note(f"MCPError (code {exc.error.code}): {exc}")
                        ctx.note("A server may answer 'Method not found'. Checking capabilities first avoids the error.")
    finally:
        quiet.close()

    ctx.step("What negotiation settled")
    ctx.note("Protocol version: client and server agree on one version, the server answers with the one it will use.")
    ctx.note("Capabilities: each side declares what it supports; the other must not use more than that.")
    ctx.note("`list_changed` in a capability means the server will notify when its list changes, so cache with care.")


if __name__ == "__main__":
    main()
