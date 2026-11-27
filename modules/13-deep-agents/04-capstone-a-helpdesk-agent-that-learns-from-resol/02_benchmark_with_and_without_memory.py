"""13.4/2  Does memory help? The same tickets with and without it

The acceptance test for the capstone. The same prompt answers each of four new tickets twice:

  baseline: no memory at all.
  memory:   the closest past tickets above the relevance floor are added to the prompt.

Three tickets repeat a problem from the history. One (a software request) has never come up before,
so the right behaviour there is to NOT cite a past ticket. Scoring is plain string matching, so it
gives the same result every time. A "repeat" ticket passes if the answer contains its keyword. The
"novel" ticket passes if the answer cites no ticket id (LL-xxxx).

Eight model calls in total (4 tickets x 2). Run it:   ./run 13.4/2   (Windows: run 13.4/2)
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
SYSTEM = "You are the Larkspur Labs IT helpdesk agent. Reply to the ticket in at most three sentences with the most likely fix."
MEMORY_SYSTEM = (
    SYSTEM + " Past resolved tickets are listed below. Use one only if it clearly matches, and cite its id. "
    "If none matches, do not cite any ticket id; say you have no past experience and suggest escalating."
)


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def passes(answer: str, expected_keyword):
    if expected_keyword is None:
        return re.search(r"LL-\d{4}", answer) is None  # novel ticket: citing a past ticket is a miss
    return expected_keyword.lower() in answer.lower()


@lesson("13.4/2", "Benchmark: with and without memory")
def main(ctx):
    with tempfile.TemporaryDirectory() as tmp:
        db = sqlite3.connect(Path(tmp) / "memory.sqlite")
        db.execute("CREATE TABLE episodes (id TEXT, problem TEXT, fix TEXT, embedding TEXT)")
        vectors = ctx.embed([h["problem"] for h in DATA["history"]])
        for h, v in zip(DATA["history"], vectors):
            db.execute("INSERT INTO episodes VALUES (?, ?, ?, ?)", (h["id"], h["problem"], h["fix"], json.dumps(v)))
        rows = db.execute("SELECT id, problem, fix, embedding FROM episodes").fetchall()
        ctx.step("The memory")
        ctx.note(f"{len(rows)} resolved tickets; relevance floor {FLOOR}; top 2 recalled per ticket.")

        results = []
        for ticket in DATA["incoming"]:
            ctx.step(f"Ticket {ticket['id']}")
            ctx.note(ticket["text"])
            qvec = ctx.embed([ticket["text"]])[0]
            ranked = sorted(((cosine(qvec, json.loads(e)), i, p, f) for i, p, f, e in rows), reverse=True)[:2]
            hits = [r for r in ranked if r[0] >= FLOOR]
            ctx.note("recalled: " + (", ".join(f"{i} ({s:.2f})" for s, i, _, _ in hits) or f"nothing above the floor (best {ranked[0][0]:.2f})"))

            base = ctx.client.chat.completions.create(
                model=ctx.model, messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": ticket["text"]}]
            )
            ctx.record_usage(base.usage, quiet=True)
            base_text = base.choices[0].message.content or ""

            memory_text = "\n".join(f"- {i}: {p} Fix: {f}" for _, i, p, f in hits) or "(none)"
            mem = ctx.client.chat.completions.create(
                model=ctx.model,
                messages=[
                    {"role": "system", "content": MEMORY_SYSTEM + "\n\nPast tickets:\n" + memory_text},
                    {"role": "user", "content": ticket["text"]},
                ],
            )
            ctx.record_usage(mem.usage, quiet=True)
            mem_text = mem.choices[0].message.content or ""

            ok_base, ok_mem = passes(base_text, ticket["expected_keyword"]), passes(mem_text, ticket["expected_keyword"])
            ctx.note(f"baseline: {base_text}")
            ctx.note(f"memory:   {mem_text}")
            results.append({"ticket": ticket["id"], "expect": ticket["expected_keyword"] or "no citation", "baseline": "pass" if ok_base else "miss", "memory": "pass" if ok_mem else "miss"})

        ctx.step("Results")
        ctx.show_data("Per ticket", results)
        b, m = sum(r["baseline"] == "pass" for r in results), sum(r["memory"] == "pass" for r in results)
        ctx.show_data("Passes out of 4", {"baseline": b, "memory": m})
        verdict = "PASS" if m >= 3 and m > b else "FAIL"
        ctx.note(f"Acceptance (memory passes at least 3 of 4 and beats the baseline): {verdict}.")
        ctx.note("The keyword check is crude on purpose: it is repeatable and free. A baseline can pass by luck, because generic advice sometimes names the right thing. Read the answers too.")
        db.close()


if __name__ == "__main__":
    main()
