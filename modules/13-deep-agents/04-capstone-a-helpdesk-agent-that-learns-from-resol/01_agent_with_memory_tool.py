"""13.4/1  The agent: memory as a tool, and learning after the ticket is closed

Capstone. The helpdesk agent from module 02 gets one new capability: a `search_memory` tool over a
SQLite store of past resolved tickets (episodic memory, 13.3). The loop is the usual tool loop with a
hard cap. After a person resolves the ticket, the resolution is written back as a new episode, so the
next session can use it. Two sessions are simulated by opening the database file twice.

  session 1: the store holds the history in tickets.json; the agent handles LL-5001 using search_memory;
             the engineer's real resolution is stored as a new episode;
  session 2: a fresh connection; the new episode is there.

Run it:   ./run 13.4/1          (Windows: run 13.4/1)
"""

import json
import math
import sqlite3
import tempfile
from pathlib import Path

from labkit import lesson

DATA = json.loads((Path(__file__).parent / "tickets.json").read_text(encoding="utf-8"))
MAX_TURNS = 5
FLOOR = 0.6

SYSTEM = (
    "You are the Larkspur Labs IT helpdesk agent. Before proposing a fix, call search_memory once with a short description "
    "of the problem. Use a past ticket only if it clearly matches, and cite its id. If nothing matches, say you have no past "
    "experience and suggest escalating. Reply in at most three sentences."
)
SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_memory",
        "description": "Search past resolved helpdesk tickets for similar problems. Returns up to 3 with their fix.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Short description of the problem."}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def connect(path):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS episodes (id TEXT PRIMARY KEY, problem TEXT, fix TEXT, embedding TEXT)")
    return db


def remember(db, ctx, ticket_id, problem, fix):
    db.execute("INSERT OR REPLACE INTO episodes VALUES (?, ?, ?, ?)", (ticket_id, problem, fix, json.dumps(ctx.embed([problem])[0])))
    db.commit()


def recall(db, ctx, query, k=3):
    qvec = ctx.embed([query])[0]
    rows = db.execute("SELECT id, problem, fix, embedding FROM episodes").fetchall()
    scored = sorted(((cosine(qvec, json.loads(e)), i, p, f) for i, p, f, e in rows), reverse=True)[:k]
    return [{"ticket": i, "score": round(s, 2), "problem": p, "fix": f} for s, i, p, f in scored if s >= FLOOR]


@lesson("13.4/1", "The agent with a memory tool")
def main(ctx):
    ticket = DATA["incoming"][0]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "agent_memory.sqlite"

        ctx.step("Session 1: seed the memory from the ticket history")
        db = connect(path)
        for h in DATA["history"]:
            remember(db, ctx, h["id"], h["problem"], h["fix"])
        ctx.note(f"{len(DATA['history'])} resolved tickets stored.")

        ctx.step("Session 1: the agent handles a new ticket")
        ctx.note(f"{ticket['id']}: {ticket['text']}")
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": ticket["text"]}]
        answer = None
        for turn in range(1, MAX_TURNS + 1):
            response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, tools=[SEARCH_TOOL])
            message = response.choices[0].message
            if not message.tool_calls:
                answer = ctx.show_response(response)
                break
            ctx.record_usage(response.usage, quiet=True)
            messages.append(message.model_dump(exclude_none=True))
            for call in message.tool_calls:
                try:
                    query = str(json.loads(call.function.arguments or "{}").get("query", ticket["text"]))
                except ValueError:
                    query = ticket["text"]
                result = recall(db, ctx, query)
                ctx.show_tool_call("search_memory", {"query": query}, json.dumps(result))
                messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
        if answer is None:
            ctx.note(f"Hit the cap of {MAX_TURNS} model calls without a final answer: the ticket goes to a human.")

        ctx.step("Learn: store the engineer's real resolution")
        resolution = "Mail app on the phone retried the old password. Removed and re-added the account on the phone, unlocked."
        remember(db, ctx, ticket["id"], ticket["text"], resolution)
        ctx.note(f"Stored {ticket['id']} with the fix the engineer actually applied (not the agent's guess).")
        db.close()

        ctx.step("Session 2: a new connection sees the new episode")
        db = connect(path)
        total = db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        ctx.show_data("Episodes now", {"count": total, "includes_new": bool(db.execute("SELECT 1 FROM episodes WHERE id = ?", (ticket["id"],)).fetchone())})
        db.close()
        ctx.note("Write after the human resolves, not after the agent answers: otherwise the agent learns from its own mistakes.")


if __name__ == "__main__":
    main()
