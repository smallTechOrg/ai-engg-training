"""04.4/3  Capstone, part 3: the evaluation report

Runs the grounded answerer from script 2 over a labelled question set (`eval_set.json`: six answerable
questions, two not in the KB, two of the six with a stale conflicting source) and prints a report:
retrieval hit@3 and MRR, key-fact rate, refusal behaviour, citation verification, and PASS/FAIL against
acceptance bars. The script exits 0 even on FAIL: a failing report is a result, not a crash.
(8 model calls; no LLM judge here, adding one is a stretch goal.)

Run it:   ./run 04.4/3          (Windows: run 04.4/3)
     or:  python modules/04-rag-by-hand/04-capstone-helpdesk-answers-grounded-in-the-knowle/03_evaluation_report.py
Needs a chat model and the `rag` extra (local embedding model).
"""

import json
from pathlib import Path

import numpy as np

from labkit import lesson

HERE = Path(__file__).parent
KB_DIR = HERE / "kb"
TOP_K = 4
GATE = 0.62  # rough: below the lowest answerable best-score seen in 04.3 (0.66); tune on a dev set
REFUSAL = "I don't know based on the IT knowledge base."
BARS = {"hit@3": 0.9, "key fact": 0.8, "refusals": 1.0, "citations verified": 1.0}
SYSTEM = (
    "You are the IT helpdesk assistant at Larkspur Labs. Answer ONLY from the context, in one or two sentences. "
    "Each chunk shows a label and its last-updated date. If chunks disagree, trust the NEWEST date and add one "
    "sentence noting that an older source disagreed. "
    'Reply as JSON: {"answer": "<text>", "citations": [{"source": "<label>", "quote": "<exact words from that chunk>"}]}. '
    f'If the context does not answer the question, use "{REFUSAL}" as the answer and an empty citations list.'
)


def load_chunks():
    chunks = []
    for path in sorted(KB_DIR.glob("*.md")):
        updated, number = "unknown", 0
        for paragraph in (p.strip() for p in path.read_text(encoding="utf-8").split("\n\n")):
            if not paragraph or paragraph.startswith("#"):
                continue
            if paragraph.startswith("Updated:"):
                updated = paragraph.split(":", 1)[1].strip()
                continue
            number += 1
            chunks.append({"source": f"{path.stem}#{number}", "text": paragraph, "updated": updated})
    return chunks


def norm(text):
    return " ".join(text.split()).lower()


def answer(ctx, question, chunks, matrix):
    """Return {"status", "answer", "citations", "retrieved", "best", "problems"}."""
    qvec = np.array(ctx.embed([question])[0])
    qvec = qvec / np.linalg.norm(qvec)
    scores = matrix @ qvec
    top = [int(i) for i in np.argsort(-scores)[:TOP_K]]
    result = {"status": "", "answer": "", "citations": [], "problems": [],
              "retrieved": [chunks[i]["source"] for i in top], "best": float(scores[top[0]])}
    if result["best"] < GATE:
        result.update(status="refused_gate", answer=REFUSAL)
        return result
    by_label = {chunks[i]["source"]: chunks[i]["text"] for i in top}
    context = "\n\n".join(f"[{chunks[i]['source']}] (updated {chunks[i]['updated']})\n{chunks[i]['text']}" for i in top)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Context:\n\n{context}\n\nQuestion: {question}"},
    ]
    response = ctx.client.chat.completions.create(
        model=ctx.model, messages=messages, temperature=0, response_format={"type": "json_object"}
    )
    ctx.record_usage(response.usage, quiet=True)  # quiet: 8 replies would flood the report
    raw = response.choices[0].message.content or ""
    try:
        data = json.loads(raw)
        text, cites = str(data["answer"]), list(data["citations"])
    except (ValueError, KeyError, TypeError):
        result.update(status="bad_reply", answer=REFUSAL, problems=["reply was not the JSON shape requested"])
        return result
    if "don't know" in text.lower() or "do not know" in text.lower():
        result.update(status="refused_model", answer=text)
        return result
    problems = []
    if not cites:
        problems.append("answer has no citations")
    for c in cites:
        label, quote = (c.get("source", "?"), c.get("quote", "")) if isinstance(c, dict) else ("?", "")
        if label not in by_label:
            problems.append(f"{label}: not a supplied chunk")
        elif norm(quote) not in norm(by_label[label]):
            problems.append(f"{label}: quote not found in chunk")
    result.update(answer=text, citations=[c.get("source") for c in cites if isinstance(c, dict)], problems=problems)
    result["status"] = "citations_failed" if problems else "answered"
    if problems:
        result["answer"] = REFUSAL  # never show an answer whose citations do not check out
    return result


@lesson("04.4/3", "The evaluation report")
def main(ctx):
    ctx.step("1. Build the index and load the labelled set")
    chunks = load_chunks()
    matrix = np.array(ctx.embed([c["text"] for c in chunks]))
    matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    items = json.loads((HERE / "eval_set.json").read_text(encoding="utf-8"))
    ctx.note(f"{len(chunks)} chunks, {len(items)} questions. Bars: {BARS}")

    ctx.step("2. Run every question through answer()")
    rows = []
    for q in items:
        result = answer(ctx, q["question"], chunks, matrix)
        should_answer = bool(q["gold"])
        row = {"id": q["id"], "status": result["status"], "should_answer": should_answer}
        if should_answer:
            # hit@3 uses retrieval order from the answerer (top-4 list, first three)
            ranked = result["retrieved"]
            row["rank"] = min((ranked.index(g) + 1 for g in q["gold"] if g in ranked), default=None)
            row["fact"] = all(k in result["answer"].lower() for k in q["must_contain"])
            row["refusal_ok"] = result["status"] in ("answered", "citations_failed")
        else:
            row["refusal_ok"] = result["status"] in ("refused_gate", "refused_model", "bad_reply")
        row["verified"] = result["status"] == "answered" if result["status"] in ("answered", "citations_failed") else None
        rows.append(row)
        ctx.note(f"{q['id']} {result['status']:<16} best={result['best']:.2f} rank={row.get('rank')} fact={row.get('fact')} :: {q['question'][:45]}")

    ctx.step("3. The report")
    answerable = [r for r in rows if r["should_answer"]]
    hits = sum(1 for r in answerable if r["rank"] and r["rank"] <= 3)
    mrr = sum(1 / r["rank"] for r in answerable if r["rank"]) / len(answerable)
    facts = sum(1 for r in answerable if r["fact"])
    refusals = sum(1 for r in rows if r["refusal_ok"])
    answered = [r for r in rows if r["verified"] is not None]
    verified = sum(1 for r in answered if r["verified"])
    metrics = {
        "hit@3": hits / len(answerable),
        "key fact": facts / len(answerable),
        "refusals": refusals / len(rows),
        "citations verified": verified / len(answered) if answered else 0.0,
    }
    ctx.note(f"MRR (informational): {mrr:.2f}")
    ctx.note(f"{'metric':<20} {'value':>6} {'bar':>6}  result")
    failed = []
    for name, bar in BARS.items():
        ok = metrics[name] >= bar
        if not ok:
            failed.append(name)
        ctx.note(f"{name:<20} {metrics[name]:>6.2f} {bar:>6.2f}  {'PASS' if ok else 'FAIL'}")
    ctx.note("Refusals = right behaviour for every question: answered when answerable, declined when not.")
    ctx.note("OVERALL: " + ("PASS" if not failed else "FAIL on " + ", ".join(failed)))

    ctx.step("4. Read the failures by hand")
    for r in rows:
        if r["should_answer"] and (not r["fact"] or not r["refusal_ok"]):
            ctx.note(f"{r['id']}: status={r['status']} fact={r['fact']}: open the log and read the reply and the chunks.")
    ctx.note("A number tells you something is wrong; reading the failing cases tells you what.")
    ctx.note("Eight questions is a smoke test. Before trusting these bars, grow the set (stretch goal 1).")


if __name__ == "__main__":
    main()
