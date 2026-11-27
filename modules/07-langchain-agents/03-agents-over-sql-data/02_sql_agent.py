"""07.3/2  An agent that explores a database and answers in plain language

The agent gets the three tools from script 1. The system prompt tells it the order of work:
list the tables, describe the ones it needs, then write one SELECT. Errors come back as text,
so the model can correct a bad query on its own. The run is capped.

Run it:   ./run 07.3/2          (Windows: run 07.3/2)
"""

import re
import sqlite3
import tempfile
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from labkit import lesson

SCHEMA = """
CREATE TABLE agents  (id INTEGER PRIMARY KEY, name TEXT NOT NULL, team TEXT NOT NULL);
CREATE TABLE tickets (id TEXT PRIMARY KEY, summary TEXT NOT NULL, status TEXT NOT NULL,
                      priority TEXT NOT NULL, agent_id INTEGER REFERENCES agents(id), opened TEXT NOT NULL);
INSERT INTO agents VALUES (1,'Priya','access'),(2,'Tom','hardware'),(3,'Mei','network');
INSERT INTO tickets VALUES
 ('LL-2041','VPN token reset','open','high',1,'2026-11-20'),
 ('LL-2042','Laptop battery replaced','resolved','low',2,'2026-11-18'),
 ('LL-2043','Printer on floor 3 offline','open','medium',3,'2026-11-21'),
 ('LL-2044','Monitor flickers','open','low',2,'2026-11-22'),
 ('LL-2045','Shared drive access request','open','medium',1,'2026-11-23'),
 ('LL-2046','Wi-Fi drops in meeting room B','resolved','high',3,'2026-11-19');
"""
MAX_ROWS = 20
FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum)\b", re.I)


def check_select(sql: str) -> str | None:
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        return "only one statement is allowed"
    if not re.match(r"^(select|with)\b", stripped, re.I):
        return "only SELECT statements are allowed"
    if FORBIDDEN.search(stripped):
        return "the statement contains a word that is not allowed in a read-only query"
    return None


def build_tools(path: Path):
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, check_same_thread=False)

    @tool
    def list_tables() -> str:
        """List the tables in the helpdesk database."""
        return ", ".join(r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))

    @tool
    def describe_table(table: str) -> str:
        """Show the columns of one table and its first 2 rows. Call this before writing a query."""
        if not re.fullmatch(r"[A-Za-z_]+", table):
            return "error: table names contain letters and underscores only"
        cols = con.execute(f"PRAGMA table_info({table})").fetchall()
        if not cols:
            return f"error: no table named {table}"
        return "columns: " + ", ".join(f"{c[1]} {c[2]}" for c in cols) + f"\nsample rows: {con.execute(f'SELECT * FROM {table} LIMIT 2').fetchall()}"

    @tool
    def run_select(sql: str) -> str:
        """Run ONE read-only SQL SELECT (SQLite dialect) and return up to 20 rows. Errors are returned as text."""
        reason = check_select(sql)
        if reason:
            return f"refused: {reason}"
        try:
            cur = con.execute(sql)
            rows = cur.fetchmany(MAX_ROWS)
            return f"columns: {[d[0] for d in cur.description]}\nrows: {rows}"
        except sqlite3.Error as exc:
            return f"sql error: {exc}"

    return con, [list_tables, describe_table, run_select]


SYSTEM = (
    "You answer questions about the Larkspur Labs helpdesk database using SQL. Work in this order: "
    "call list_tables, call describe_table for the tables you need, then write ONE SQLite SELECT with run_select. "
    "If a query returns an error, fix it and try again. Never guess column names. Answer in one or two plain sentences."
)


@lesson("07.3/2", "A SQL agent that explores the schema")
def main(ctx):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "helpdesk.db"
        setup = sqlite3.connect(path)
        setup.executescript(SCHEMA)
        setup.commit()
        setup.close()
        con, tools = build_tools(path)

        ctx.step("Build the agent")
        model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
        agent = create_agent(model, tools=tools, system_prompt=SYSTEM)

        ctx.step("Ask a question that needs a join")
        question = "Which helpdesk agent has the most open tickets, and what are their summaries?"
        ctx.note(f"Question: {question}")
        try:
            result = agent.invoke({"messages": [("user", question)]}, {"recursion_limit": 15})
        except Exception as exc:
            ctx.note(f"Stopped: {type(exc).__name__}: {str(exc)[:120]}")
            con.close()
            return

        ctx.step("What the agent did")
        asked = {}
        for m in result["messages"]:
            if m.type == "ai":
                ctx.record_usage(m.usage_metadata, quiet=True)
                asked.update({c["id"]: c["args"] for c in m.tool_calls})
            elif m.type == "tool":
                ctx.show_tool_call(m.name, asked.get(m.tool_call_id, {}), str(m.content)[:300])
        ctx.note(f"Final answer: {result['messages'][-1].content}")
        con.close()
        ctx.note("Schema inspection first, one query second: the tool descriptions and the system prompt steer that order.")


if __name__ == "__main__":
    main()
