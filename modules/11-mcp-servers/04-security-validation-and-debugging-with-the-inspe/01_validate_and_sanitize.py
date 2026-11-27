"""11.4/1  Validate, sanitize, and gate: an MCP server is an attack surface

Everything a model sends to a tool is untrusted input, and everything a tool returns may
contain untrusted text (a ticket written by a stranger). This script attacks a small server
on purpose and shows four defences:

  1. schema validation (pattern, length) before the function runs
  2. a second check inside the function (resolved path must stay in the knowledge-base folder)
  3. parameterised SQL and size limits
  4. untrusted text wrapped as data, plus a host-side gate on destructive tools

The server has one deliberately unsafe tool next to its safe twin. No model is needed.

Run it:   ./run 11.4/1          (Windows: run 11.4/1)
"""

import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from labkit import lesson

SERVER = Path(__file__).with_name("secure_server.py")


def text_of(result) -> str:
    return "".join(p.text for p in result.content if p.type == "text")


@lesson("11.4/1", "Validate, sanitize and gate")
async def main(ctx):
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    with open(os.devnull, "w") as quiet:
        async with stdio_client(params, errlog=quiet) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = {t.name: t for t in (await session.list_tools()).tools}

                async def call(name, args):
                    result = await session.call_tool(name, args)
                    first = text_of(result).splitlines()[0] if text_of(result) else ""
                    ctx.show_tool_call(name, args, f"is_error={result.is_error} | {first[:110]}")
                    return result

                ctx.step("Path traversal: the unsafe tool versus the safe tool")
                await call("read_kb_article_unsafe", {"name": "../secrets.env"})
                ctx.note("The unsafe twin just joined the string into a path: it leaked a file OUTSIDE the knowledge base.")
                for name in ("../secrets", "..\\secrets", "vpn-reset.txt", "no-such-article"):
                    await call("read_kb_article", {"name": name})
                await call("read_kb_article", {"name": "vpn-reset"})
                ctx.note("The schema pattern (letters, digits, dashes) stops traversal; the safe tool also re-checks the resolved path.")

                ctx.step("Injection-shaped input and oversized input")
                await call("find_tickets", {"text": "' OR 1=1 --"})
                await call("find_tickets", {"text": "VPN"})
                await call("find_tickets", {"text": "x" * 500})
                ctx.note("SQL parameters make the quote just a character. The length cap protects the server from huge inputs.")

                ctx.step("Untrusted text that tries to give orders")
                result = await session.call_tool("get_ticket_text", {"ticket_id": "T-2002"})
                ctx.note(text_of(result))
                ctx.note("The ticket body says 'close every ticket'. The server cannot stop a user writing that; it can label it as data.")
                ctx.note("Labels help a model but do not guarantee anything: the real protection is the gate below.")

                ctx.step("A host-side gate: destructive tools need a human")
                for name, tool in tools.items():
                    ann = tool.annotations
                    read_only = bool(ann and ann.read_only_hint)
                    ctx.note(f"{name:24} read_only={read_only!s:5} -> {'auto-allowed' if read_only else 'NEEDS APPROVAL'}")
                ctx.note("Annotations are HINTS from the server. A host must not trust them from an untrusted server, only use them to decide when to ask.")
                ctx.note("This script has no human, so the gate denies close_ticket and the call is never sent:")
                ctx.show_tool_call("close_ticket", {"ticket_id": "T-2002"}, "blocked by host policy: approval required")
                ctx.note("With approval, the same call would run. A prompt-injected 'close every ticket' dies at this gate.")


if __name__ == "__main__":
    main()
