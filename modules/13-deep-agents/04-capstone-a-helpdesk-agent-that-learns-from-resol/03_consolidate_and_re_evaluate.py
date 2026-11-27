"""13.4/3  Consolidate the history, then answer from the consolidated memory

The history in tickets.json has eight episodes. As in 13.3/3, one model call turns repeated episodes
into semantic facts and procedures (with sources) and archives the sources. Then the script answers
the four incoming tickets from the CONSOLIDATED memory (recall over active memories, with a relevance
floor) and scores them with the same rule as 13.4/2.

This shows what consolidation can cost. A general procedure ("check secondary devices") may not
contain the specific word a ticket is checked for ("phone"). Compare with 13.4/2.

Five model calls (1 consolidation + 4 answers). Run it:   ./run 13.4/3   (Windows: run 13.4/3)
"""

import json
import math
import re
import sqlite3
import tempfile
from pathlib import Path

from labkit import lesson

DATA = json.loads((Path(__file__).parent / "tickets.json").read_text(encoding="utf-8"))
FLOOR = 0.6
SYSTEM = (
    "You are the Larkspur Labs IT helpdesk agent. Reply to the ticket in at most three sentences with the most likely fix. "
    "Use the memories below only if they clearly match; cite a ticket id only if the memory is an episode. "
    "If nothing matches, do not cite any ticket id; say you have no past experience and suggest escalating."
)
CONSOLIDATE_SYSTEM = (
    "You consolidate helpdesk episodes into long-term knowledge. Reply with JSON only, shaped like this example: "
    '{"facts": [{"text": "one general true statement", "sources": ["LL-0000"]}], '
    '"procedures": [{"text": "1) first step 2) second step", "sources": ["LL-0000"]}]}\n'
    "Write only generalisations supported by SEVERAL episodes and keep concrete details (devices, servers, protocols) that make the fix findable. "
    "List the ticket ids each one comes from. Ignore episodes that do not repeat."
)


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def passes(answer, expected_keyword):
    if expected_keyword is None:
        return re.search(r"LL-\d{4}", answer) is None
    return expected_keyword.lower() in answer.lower()


@lesson("13.4/3", "Consolidate, then re-evaluate")
def main(ctx):
    with tempfile.TemporaryDirectory() as tmp:
        db = sqlite3.connect(Path(tmp) / "memory.sqlite")
        db.execute("CREATE TABLE memories (id TEXT PRIMARY KEY, kind TEXT, text TEXT, embedding TEXT, archived INTEGER DEFAULT 0)")

        def add(mid, kind, text):
            db.execute("INSERT INTO memories (id, kind, text, embedding) VALUES (?, ?, ?, ?)", (mid, kind, text, json.dumps(ctx.embed([text])[0])))

        ctx.step("Seed the episodes")
        for h in DATA["history"]:
            add(h["id"], "episodic", f"{h['problem']} Fix: {h['fix']}")
        ctx.note(f"{len(DATA['history'])} episodes stored.")

        ctx.step("Consolidate")
        listing = "\n".join(f"{h['id']}: {h['problem']} Fix: {h['fix']}" for h in DATA["history"])
        response = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[{"role": "system", "content": CONSOLIDATE_SYSTEM}, {"role": "user", "content": listing}],
            response_format={"type": "json_object"},
        )
        ctx.record_usage(response.usage, quiet=True)
        known = {h["id"] for h in DATA["history"]}
        archived = set()
        try:
            data = json.loads(response.choices[0].message.content or "")
            entries = [("semantic", e) for e in data.get("facts", [])] + [("procedural", e) for e in data.get("procedures", [])]
        except (ValueError, AttributeError):
            entries = []
            ctx.note("The consolidation reply was not usable JSON, so the episodes stay as they are.")
        for n, (kind, entry) in enumerate(entries, 1):
            try:
                text, sources = str(entry["text"]), [s for s in entry["sources"] if s in known]
            except (KeyError, TypeError):
                continue
            if not sources:
                ctx.note(f"Dropped an entry with no real source: {entry!r}")
                continue
            add(f"K-{n}", kind, text)
            archived.update(sources)
            ctx.note(f"{kind} from {sources}: {text}")
        for tid in archived:
            db.execute("UPDATE memories SET archived = 1 WHERE id = ?", (tid,))
        db.commit()
        active = db.execute("SELECT COUNT(*) FROM memories WHERE archived = 0").fetchone()[0]
        ctx.show_data("Memory size", {"episodes_before": len(DATA["history"]), "archived": len(archived), "active_now": active})

        ctx.step("Answer the incoming tickets from the consolidated memory")
        rows = db.execute("SELECT id, kind, text, embedding FROM memories WHERE archived = 0").fetchall()
        results = []
        for ticket in DATA["incoming"]:
            qvec = ctx.embed([ticket["text"]])[0]
            ranked = sorted(((cosine(qvec, json.loads(e)), i, k, t) for i, k, t, e in rows), reverse=True)[:2]
            hits = [r for r in ranked if r[0] >= FLOOR]
            memory_text = "\n".join(f"- [{k}] {i}: {t}" for _, i, k, t in hits) or "(none)"
            reply = ctx.client.chat.completions.create(
                model=ctx.model,
                messages=[{"role": "system", "content": SYSTEM + "\n\nMemories:\n" + memory_text}, {"role": "user", "content": ticket["text"]}],
            )
            ctx.record_usage(reply.usage, quiet=True)
            text = reply.choices[0].message.content or ""
            ok = passes(text, ticket["expected_keyword"])
            ctx.note(f"{ticket['id']} recalled {[(i, round(s, 2)) for s, i, _, _ in hits] or 'nothing above the floor'}")
            ctx.note(f"   answer: {text}")
            results.append({"ticket": ticket["id"], "expect": ticket["expected_keyword"] or "no citation", "result": "pass" if ok else "miss"})

        ctx.step("Results")
        ctx.show_data("Per ticket", results)
        score = sum(r["result"] == "pass" for r in results)
        ctx.note(f"{score} of 4 pass. Acceptance bar: 3 of 4 -> {'PASS' if score >= 3 else 'FAIL'}.")
        ctx.note("Compare with 13.4/2 (raw episodes). If a ticket now fails, check what the consolidated entry kept and what it generalised away.")
        db.close()


if __name__ == "__main__":
    main()
