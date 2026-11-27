"""12.1/1  Connect to a ready-made MCP server (SQLite)

You do not have to write MCP servers. Many are published, and `uvx` runs a Python one
without installing it. This script starts the published `mcp-server-sqlite` on an
invented helpdesk database, lists its tools and runs one read-only query.
No model is involved. The first run downloads the server, so it needs network.

Run it:   ./run 12.1/1          (Windows: run 12.1/1)
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


@lesson("12.1/1", "Connect to the SQLite MCP server")
async def main(ctx):
    ctx.step("Create an invented helpdesk database in a temp folder")
    with tempfile.TemporaryDirectory(prefix="labkit-mcp-") as folder:
        db_path = make_tickets_db(folder)
        ctx.note("Table `tickets`: id, category, status, subject, priority (6 rows). Deleted when the script ends.")

        ctx.step("Launch the published server with uvx")
        params = sqlite_server_params(db_path)
        ctx.note("Command: uvx --with 'mcp<2' mcp-server-sqlite --db-path <temp>/helpdesk.db")
        ctx.note("First run downloads the server, so it needs network and can take a few seconds.")
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    ctx.note(f"Connected to server '{init.server_info.name}' (protocol {init.protocol_version}).")

                    ctx.step("List the tools it offers")
                    tools = (await session.list_tools()).tools
                    for tool in tools:
                        ctx.note(f"{tool.name:<15} {tool.description}")
                    ctx.note("Someone else wrote these tools, and you got them without writing a line of tool code.")
                    ctx.note("Note `write_query` and `create_table`: a server offers everything, the host decides what to expose.")

                    ctx.step("Run a read-only query through read_query")
                    args = {"query": "SELECT category, COUNT(*) AS open_tickets FROM tickets WHERE status = 'open' GROUP BY category"}
                    result = await session.call_tool("read_query", args)
                    ctx.show_tool_call("read_query", args, text_of(result))
        except ServiceUnavailable:
            raise
        except Exception as exc:
            raise ServiceUnavailable(
                f"Could not start or talk to the SQLite MCP server ({type(exc).__name__}).",
                [
                    "The first run needs network to download the server: check your connection or proxy.",
                    "Test it by hand: uvx mcp-server-sqlite --help",
                    "Run ./run doctor to check your setup.",
                ],
            ) from exc


if __name__ == "__main__":
    main()
