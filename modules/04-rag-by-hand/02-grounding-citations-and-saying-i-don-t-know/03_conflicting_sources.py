"""04.2/3  Scenario: two sources disagree

The KB now holds an archived laptop page (3 years, 2022) and an old password FAQ (12 chars, 90 days,
2023) next to the current pages. Retrieval happily returns both. A naive prompt picks one silently;
a conflict-aware prompt shows each chunk's date, asks the model to prefer the newest, and to say
when sources disagree. Same chunks, two prompts, side by side.

Run it:   ./run 04.2/3          (Windows: run 04.2/3)
     or:  python modules/04-rag-by-hand/02-grounding-citations-and-saying-i-don-t-know/03_conflicting_sources.py
Needs a chat model and the `rag` extra (local embedding model).
"""

from pathlib import Path

import numpy as np

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"
TOP_K = 4
QUESTIONS = [
    "How often does Larkspur Labs replace laptops?",
    "How long must my password be, and how often do I change it?",
]
NAIVE = "You are the IT helpdesk assistant at Larkspur Labs. Answer from the context. Cite sources in square brackets."
AWARE = (
    "You are the IT helpdesk assistant at Larkspur Labs. Answer ONLY from the context. Cite sources in square brackets. "
    "Each chunk shows its last-updated date. If two chunks disagree, trust the NEWEST date, answer with that, "
    "and add one sentence saying an older source disagreed, naming both labels. "
    "If you cannot tell which is right, say so instead of picking one."
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


@lesson("04.2/3", "Conflicting sources")
def main(ctx):
    ctx.step("1. Index, with the last-updated date kept as metadata")
    chunks = load_chunks()
    matrix = np.array(ctx.embed([c["text"] for c in chunks]))
    matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    qvecs = np.array(ctx.embed(QUESTIONS))
    qvecs = qvecs / np.linalg.norm(qvecs, axis=1, keepdims=True)
    ctx.note(f"{len(chunks)} chunks. Two files are stale on purpose: laptops-archive, passwords-faq-old.")

    for question, qvec in zip(QUESTIONS, qvecs):
        ctx.step(f"Question: {question}")
        scores = matrix @ qvec
        top = [int(i) for i in np.argsort(-scores)[:TOP_K]]
        for i in top:
            c = chunks[i]
            ctx.note(f"score {scores[i]:.2f}  [{c['source']}] updated {c['updated']}  {c['text'][:55]}...")
        plain = "\n\n".join(f"[{chunks[i]['source']}]\n{chunks[i]['text']}" for i in top)
        dated = "\n\n".join(
            f"[{chunks[i]['source']}] (updated {chunks[i]['updated']})\n{chunks[i]['text']}" for i in top
        )
        for name, system, context in (("naive prompt, no dates", NAIVE, plain), ("conflict-aware prompt, dated chunks", AWARE, dated)):
            ctx.note(f"--- {name} ---")
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": f"Context:\n\n{context}\n\nQuestion: {question}"},
            ]
            response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
            ctx.show_response(response)

    ctx.step("What to take away")
    ctx.note("Retrieval cannot tell which source is right; it ranks by similarity, and stale pages are similar.")
    ctx.note("Give the model what it needs to decide (dates, owners) and tell it what to do on a conflict.")
    ctx.note("Better still, fix the corpus: archive or delete stale pages, so there is nothing to conflict.")
    ctx.note("A model that is told to 'trust the newest' can still be wrong; keep the citations so a person can check.")


if __name__ == "__main__":
    main()
