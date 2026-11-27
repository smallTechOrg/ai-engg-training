"""07.5/1  The capstone tools, tested without a model

An agent is only as reliable as its tools. Before any model is involved, this script builds
the four tools of the capstone (knowledge-base search, schema description, read-only SQL,
ticket creation) and checks each one, including how it refuses bad input. Nothing here calls
a model, so these checks are fast, free and repeatable: keep them as unit tests in your own project.

Run it:   ./run 07.5/1          (Windows: run 07.5/1)
"""

import json
import re
import sqlite3
import tempfile
from pathlib import Path
from typing import Literal

from langchain_core.tools import tool

from labkit import lesson

HERE = Path(__file__).parent
MAX_ROWS = 20
FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum)\b", re.I)
TOKEN = re.compile(r"[a-z0-9]+")


def check_select(sql: str) -> str | None:
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        return "only one statement is allowed"
    if not re.match(r"^(select|with)\b", stripped, re.I):
        return "only SELECT statements are allowed"
    if FORBIDDEN.search(stripped):
        return "the statement contains a word that is not allowed in a read-only query"
    return None


class Helpdesk:
    """The three tool groups over one temp database, one knowledge base and one in-memory ticket queue."""

    def __init__(self, directory: Path):
        self.path = directory / "helpdesk.db"
        setup = sqlite3.connect(self.path)
        setup.executescript((HERE / "seed.sql").read_text(encoding="utf-8"))
        setup.commit()
        setup.close()
        self.con = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
        self.kb = json.loads((HERE / "kb.json").read_text(encoding="utf-8"))
        self.created: list[dict] = []
        self.calls: list[str] = []  # names of tools the agent used, for the acceptance check

    def tools(self):
        hd = self

        @tool
        def search_kb(query: str) -> str:
            """Search the knowledge base. Returns the best 2 articles as 'id: title - text'. Use for how-to and fix questions."""
            hd.calls.append("search_kb")
            words = set(TOKEN.findall(query.lower()))
            scored = sorted(hd.kb, key=lambda a: -len(words & set(TOKEN.findall((a["title"] + " " + a["text"]).lower()))))
            hits = [a for a in scored[:2] if words & set(TOKEN.findall((a["title"] + " " + a["text"]).lower()))]
            return "\n".join(f"{a['id']}: {a['title']} - {a['text']}" for a in hits) or "no matching article"

        @tool
        def describe_database() -> str:
            """Describe the tickets database: its tables and columns. Call once before run_select."""
            hd.calls.append("describe_database")
            out = []
            for (name,) in hd.con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
                cols = ", ".join(f"{c[1]} {c[2]}" for c in hd.con.execute(f"PRAGMA table_info({name})"))
                out.append(f"{name}({cols})")
            return "\n".join(out)

        @tool
        def run_select(sql: str) -> str:
            """Run ONE read-only SQLite SELECT over the tickets database and return up to 20 rows. Errors come back as text."""
            hd.calls.append("run_select")
            reason = check_select(sql)
            if reason:
                return f"refused: {reason}"
            try:
                cur = hd.con.execute(sql)
                return f"columns: {[d[0] for d in cur.description]}\nrows: {cur.fetchmany(MAX_ROWS)}"
            except sqlite3.Error as exc:
                return f"sql error: {exc}"

        @tool
        def create_ticket(summary: str, priority: Literal["low", "medium", "high"]) -> str:
            """Create a NEW helpdesk ticket. Only call this when the user explicitly asks to open or file a ticket."""
            hd.calls.append("create_ticket")
            if len(summary.strip()) < 8:
                return "refused: the summary is too short to be useful"
            if any(t["summary"].lower() == summary.strip().lower() for t in hd.created):
                return "refused: an identical ticket was already created in this session"
            ticket = {"id": f"LL-{3001 + len(hd.created)}", "summary": summary.strip(), "priority": priority}
            hd.created.append(ticket)
            return f"created {ticket['id']}"

        return [search_kb, describe_database, run_select, create_ticket]


@lesson("07.5/1", "The capstone tools, tested without a model")
def main(ctx):
    with tempfile.TemporaryDirectory() as tmp:
        hd = Helpdesk(Path(tmp))
        search_kb, describe_database, run_select, create_ticket = hd.tools()
        results = []

        def check(label: str, condition: bool):
            results.append((label, condition))
            ctx.note(f"{'PASS' if condition else 'FAIL'}  {label}")

        ctx.step("Knowledge base search")
        out = search_kb.invoke({"query": "printer offline firmware"})
        ctx.show_tool_call("search_kb", {"query": "printer offline firmware"}, out)
        check("printer query finds KB-02 first", out.startswith("KB-02"))
        out = search_kb.invoke({"query": "xyzzy"})
        check("nonsense query returns 'no matching article'", out == "no matching article")

        ctx.step("Database tools")
        ctx.show_tool_call("describe_database", {}, describe_database.invoke({}))
        out = run_select.invoke({"sql": "SELECT COUNT(*) FROM tickets WHERE status = 'open'"})
        ctx.show_tool_call("run_select", {"sql": "SELECT COUNT(*) ..."}, out)
        check("open ticket count is 4", "(4,)" in out)
        check("DELETE is refused", run_select.invoke({"sql": "DELETE FROM tickets"}).startswith("refused"))
        check("two statements are refused", run_select.invoke({"sql": "SELECT 1; SELECT 2"}).startswith("refused"))
        check("bad SQL comes back as text, not an exception", run_select.invoke({"sql": "SELECT nope FROM tickets"}).startswith("sql error"))

        ctx.step("Ticket creation")
        out = create_ticket.invoke({"summary": "Docking station beeps constantly", "priority": "low"})
        ctx.show_tool_call("create_ticket", {"summary": "Docking station beeps constantly", "priority": "low"}, out)
        check("first ticket is LL-3001", out == "created LL-3001")
        check("an identical ticket is refused", create_ticket.invoke({"summary": "Docking station beeps constantly", "priority": "low"}).startswith("refused"))
        check("a too-short summary is refused", create_ticket.invoke({"summary": "hi", "priority": "low"}).startswith("refused"))
        try:
            create_ticket.invoke({"summary": "Something long enough", "priority": "urgent"})
            check("an invalid priority is rejected by the schema", False)
        except Exception as exc:
            check(f"an invalid priority is rejected by the schema ({type(exc).__name__})", True)
        check("exactly one ticket was created", len(hd.created) == 1)

        ctx.step("Summary")
        failed = [label for label, ok in results if not ok]
        ctx.note(f"{len(results) - len(failed)} of {len(results)} checks passed." + (f" Failed: {failed}" if failed else ""))
        hd.con.close()


if __name__ == "__main__":
    main()
