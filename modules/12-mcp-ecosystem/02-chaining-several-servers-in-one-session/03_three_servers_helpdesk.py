"""12.2/3  Scenario: a published server plus two of your own, in one session

New since 12.2/2: one of the three servers is NOT yours. The published SQLite server (started
with uvx, as in 12.1) holds the ticket data; your ticket desk and knowledge base add owners
and fixes. The host applies a per-server allow-list (only the read-only SQLite tools) and
one registry routes everything. The model is asked a question that needs all three.

Needs network on the first run (uvx downloads the SQLite server) and `uvx` on your machine;
without them the script stops with exit code 3 and tells you what to install.

Run it:   ./run 12.2/3          (Windows: run 12.2/3)
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import AsyncExitStack, closing
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from labkit import lesson
from labkit.errors import ServiceUnavailable

HERE = Path(__file__).parent
MAX_ITERATIONS = 8
ALLOW = {"sql": {"list_tables", "describe_table", "read_query"}}  # per-server allow-list; others offered whole
QUESTION = (
    "Using the database, find which category has the most open tickets. "
    "Then look up that category's owner with the ticket desk and find the knowledge-base advice for it. "
    "Answer in three short lines: category and count, owner, first thing to try."
)


def find_uvx():
    """uvx may not be on PATH inside a launcher, so also look in the usual install folders."""
    found = shutil.which("uvx")
    if found:
        return found
    names = ["uvx.exe", "uvx"] if os.name == "nt" else ["uvx"]
    for folder in (Path.home() / ".local" / "bin", Path.home() / ".cargo" / "bin"):
        for name in names:
            if (folder / name).exists():
                return str(folder / name)
    raise ServiceUnavailable(
        "`uvx` (part of uv) was not found, and this lesson launches a published MCP server with it.",
        [
            "Install uv: https://docs.astral.sh/uv/getting-started/installation/",
            "Open a new terminal so PATH is refreshed, then run the lesson again.",
        ],
    )


def make_tickets_db(folder):
    """An invented helpdesk database in a temp folder (ids match the ticket desk server)."""
    path = Path(folder) / "helpdesk.db"
    rows = [
        ("T-1001", "network", "open", "VPN drops every ten minutes"),
        ("T-1002", "hardware", "open", "Laptop battery swells"),
        ("T-1003", "access", "closed", "Cannot open shared finance sheet"),
        ("T-1004", "network", "open", "Wi-Fi slow in meeting room B"),
        ("T-1005", "network", "open", "Printer offline on floor 2"),
        ("T-1006", "software", "open", "Editor crashes on startup"),
    ]
    with closing(sqlite3.connect(path)) as db:
        db.execute("CREATE TABLE tickets (ticket_id TEXT PRIMARY KEY, category TEXT, status TEXT, subject TEXT)")
        db.executemany("INSERT INTO tickets VALUES (?, ?, ?, ?)", rows)
        db.commit()
    return path


def text_of(result):
    return "".join(part.text for part in result.content if part.type == "text")


@lesson("12.2/3", "A published server plus two of your own")
async def main(ctx):
    uvx = find_uvx()
    with tempfile.TemporaryDirectory(prefix="labkit-mcp-") as folder:
        db_path = make_tickets_db(folder)
        servers = {
            # The published SQLite server breaks on mcp 2.x, so uvx runs it with `mcp<2`.
            "sql": StdioServerParameters(command=uvx, args=["--with", "mcp<2", "mcp-server-sqlite", "--db-path", str(db_path)]),
            "tickets": StdioServerParameters(command=sys.executable, args=[str(HERE / "ticket_server.py")]),
            "kb": StdioServerParameters(command=sys.executable, args=[str(HERE / "kb_server.py")]),
        }
        ctx.step("Start three servers: one published, two yours")
        ctx.note("First run downloads the SQLite server through uvx, so it needs network.")
        try:
            async with AsyncExitStack() as stack:
                routes, tools = {}, []
                for alias, params in servers.items():
                    read, write = await stack.enter_async_context(stdio_client(params))
                    session = await stack.enter_async_context(ClientSession(read, write))
                    await session.initialize()
                    listed = (await session.list_tools()).tools
                    offered = [t for t in listed if t.name in ALLOW.get(alias, {t.name})]
                    ctx.note(f"{alias:<8} offers {len(listed)} tools, host exposes {len(offered)}: " + ", ".join(t.name for t in offered))
                    for tool in offered:
                        name = f"{alias}__{tool.name}"
                        routes[name] = (session, tool.name)
                        tools.append({"type": "function", "function": {"name": name, "description": f"[{alias}] {tool.description or ''}", "parameters": tool.input_schema}})

                messages = [
                    {"role": "system", "content": "You are the Larkspur Labs helpdesk analyst. Use tools; do not guess. The database table is `tickets` (ticket_id, category, status, subject); status values are lowercase: open, closed. Ticket desk lookups take a ticket id such as T-1001."},
                    {"role": "user", "content": QUESTION},
                ]
                ctx.step("Run the tool loop across three servers")
                servers_used = []
                for iteration in range(1, MAX_ITERATIONS + 1):
                    response = await ctx.async_client.chat.completions.create(model=ctx.model, messages=messages, tools=tools)
                    message = response.choices[0].message
                    if not message.tool_calls:
                        ctx.show_response(response)
                        break
                    ctx.record_usage(response.usage, quiet=True)  # a tool-call turn; the final reply is counted by show_response
                    messages.append(message.model_dump(exclude_none=True))
                    for call in message.tool_calls:
                        name = call.function.name
                        try:
                            args = json.loads(call.function.arguments or "{}")
                            if name not in routes:
                                output = f"Tool {name} is not available."
                            else:
                                session, original = routes[name]
                                output = text_of(await session.call_tool(original, args))
                                servers_used.append(name.split("__")[0])
                        except Exception as exc:  # bad arguments are an outcome, not a crash
                            args, output = call.function.arguments, f"Tool failed: {exc}"
                        ctx.show_tool_call(name, args, output)
                        messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
                else:
                    ctx.note(f"Stopped after {MAX_ITERATIONS} iterations without a final answer.")

                ctx.step("Which servers did the model use?")
                ctx.note("Calls per server: " + ", ".join(f"{a}={servers_used.count(a)}" for a in servers))
        except ServiceUnavailable:
            raise
        except Exception as exc:
            if isinstance(exc, BaseExceptionGroup) or type(exc).__module__.startswith(("mcp", "anyio")):
                raise ServiceUnavailable(
                    f"Could not start or talk to one of the MCP servers ({type(exc).__name__}).",
                    ["The first run needs network to download the SQLite server.", "Test it by hand: uvx mcp-server-sqlite --help"],
                ) from exc
            raise


if __name__ == "__main__":
    main()
