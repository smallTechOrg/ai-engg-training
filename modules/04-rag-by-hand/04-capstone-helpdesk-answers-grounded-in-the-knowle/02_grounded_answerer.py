"""04.4/2  Capstone, part 2: the grounded answerer

One function, `answer(question)`, that combines the module:
  retrieve top-k with scores -> GATE (refuse if best score is low) -> dated chunks in the prompt
  -> JSON reply with a verbatim quote per claim -> verify every citation in code
  -> a typed result: answered | refused_gate | refused_model | citations_failed | bad_reply
Five demo questions show each outcome the pipeline can produce.

Run it:   ./run 04.4/2          (Windows: run 04.4/2)
     or:  python modules/04-rag-by-hand/04-capstone-helpdesk-answers-grounded-in-the-knowle/02_grounded_answerer.py
Needs a chat model and the `rag` extra (local embedding model).
"""

import json
from pathlib import Path

import numpy as np

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"
TOP_K = 4
GATE = 0.62  # rough: below the lowest answerable best-score seen in 04.3 (0.66); tune on a dev set
REFUSAL = "I don't know based on the IT knowledge base."
DEMO = [
    "How many years until my laptop is swapped for a new one?",
    "How many characters must a password have, and how often must I change it?",
    "Can I print in colour on floor 4?",
    "What is the company's parental leave policy?",
    "Can I install the Larkspur VPN client on my personal phone?",
]
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
    raw = ctx.show_response(response) or ""
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


@lesson("04.4/2", "The grounded answerer")
def main(ctx):
    ctx.step("1. Build the index (script 1 explained it)")
    chunks = load_chunks()
    matrix = np.array(ctx.embed([c["text"] for c in chunks]))
    matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    ctx.note(f"{len(chunks)} chunks (including two stale files) | gate threshold {GATE} | top-k {TOP_K}")

    outcomes = []
    for question in DEMO:
        ctx.step(f"Question: {question}")
        result = answer(ctx, question, chunks, matrix)
        outcomes.append(result["status"])
        ctx.note(f"best score {result['best']:.2f}; retrieved {', '.join(result['retrieved'])}")
        ctx.note(f"STATUS: {result['status']}  cited: {result['citations']}  problems: {result['problems']}")
        ctx.note(f"SHOWN TO THE EMPLOYEE: {result['answer']}")

    ctx.step("Summary: every outcome is explicit")
    for status in sorted(set(outcomes)):
        ctx.note(f"{status}: {outcomes.count(status)}")
    ctx.note("The caller never has to guess whether an answer is grounded: the status says so.")
    ctx.note("Answers whose citations fail verification are replaced by the refusal rather than shown.")


if __name__ == "__main__":
    main()
