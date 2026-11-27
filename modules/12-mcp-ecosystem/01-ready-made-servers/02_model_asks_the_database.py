"""12.1/2  The model answers questions with a ready-made server's tools

The host lists the SQLite server's tools, offers the read-only ones to the model, and
forwards the model's tool calls to the server. Least privilege: `write_query`,
`create_table` and `append_insight` are NOT offered, even though the server has them.

Run it:   ./run 12.1/2          (Windows: run 12.1/2)
"""

import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp import StdioServerParameters

from labkit import lesson
from labkit.errors import ServiceUnavailable


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
    """An invented helpdesk database in a temp folder."""
    path = Path(folder) / "helpdesk.db"
    rows = [
        (1, "network", "open", "VPN drops every ten minutes", "high"),
        (2, "hardware", "open", "Laptop battery swells", "high"),
        (3, "access", "closed", "Cannot open shared finance sheet", "low"),
        (4, "network", "open", "Wi-Fi slow in meeting room B", "medium"),
        (5, "software", "open", "Editor crashes on startup", "medium"),
        (6, "network", "closed", "Printer offline on floor 2", "low"),
    ]
    with closing(sqlite3.connect(path)) as db:
        db.execute("CREATE TABLE tickets (id INTEGER PRIMARY KEY, category TEXT, status TEXT, subject TEXT, priority TEXT)")
        db.executemany("INSERT INTO tickets VALUES (?, ?, ?, ?, ?)", rows)
        db.commit()
    return path


def sqlite_server_params(db_path):
    # The published server was written for mcp 1.x, so we ask uvx to run it with `mcp<2`.
    # (Tip: a server's own pinned dependencies are the server's business, not ours.)
    return StdioServerParameters(command=find_uvx(), args=["--with", "mcp<2", "mcp-server-sqlite", "--db-path", str(db_path)])


def text_of(result):
    return "".join(part.text for part in result.content if part.type == "text")


READ_ONLY_TOOLS = {"list_tables", "describe_table", "read_query"}
MAX_ITERATIONS = 4
QUESTION = "How many tickets are open in each category? Look at the database with your tools, then answer briefly."


@lesson("12.1/2", "The model asks the database")
async def main(ctx):
    with tempfile.TemporaryDirectory(prefix="labkit-mcp-") as folder:
        db_path = make_tickets_db(folder)
        params = sqlite_server_params(db_path)
        ctx.step("Connect and choose which tools the model may use")
        ctx.note("First run downloads the server through uvx, so it needs network.")
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    offered = [t for t in (await session.list_tools()).tools if t.name in READ_ONLY_TOOLS]
                    ctx.note("Offered to the model: " + ", ".join(t.name for t in offered))
                    tools = [
                        {"type": "function", "function": {"name": t.name, "description": t.description or "", "parameters": t.input_schema}}
                        for t in offered
                    ]

                    messages = [
                        {"role": "system", "content": "You are the Larkspur Labs helpdesk analyst. Use the database tools; do not guess. The table is `tickets` (id, category, status, subject, priority); status values are lowercase: open, closed."},
                        {"role": "user", "content": QUESTION},
                    ]
                    ctx.step("Run the tool loop")
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
                                if name not in READ_ONLY_TOOLS:
                                    output = f"Tool {name} is not available."
                                else:
                                    output = text_of(await session.call_tool(name, args))
                            except Exception as exc:  # bad arguments are an outcome, not a crash
                                args, output = call.function.arguments, f"Tool failed: {exc}"
                            ctx.show_tool_call(name, args, output)
                            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
                    else:
                        ctx.note(f"Stopped after {MAX_ITERATIONS} iterations without a final answer.")
        except ServiceUnavailable:
            raise
        except Exception as exc:
            if isinstance(exc, BaseExceptionGroup) or type(exc).__module__.startswith(("mcp", "anyio")):
                raise ServiceUnavailable(
                    f"Could not start or talk to the SQLite MCP server ({type(exc).__name__}).",
                    ["The first run needs network to download the server.", "Test it by hand: uvx mcp-server-sqlite --help"],
                ) from exc
            raise


if __name__ == "__main__":
    main()
